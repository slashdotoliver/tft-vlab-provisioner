import json
import logging
import select
from typing import Callable

from psycopg import connect, sql

from node_agent.application.controllers.thread_controller import ThreadController
from node_agent.application.ports.worker import Worker
from node_agent.application.services.reconciliation_loop import ReconciliationLoop
from node_agent.domain.attempt import attempt, raises
from node_agent.domain.model.entities import NodeID
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)
MONITOR_WORKER_THREAD_NAME: str = "PostgresEventMonitorWorker-Thread-0"
EVENT_TIMEOUT_MS: int = 2_000
KEEPALIVE_CYCLE_PERIOD: int = 10


class PostgresEventMonitorWorker(Worker):
    def __init__(self, db_uri: str, node_id: NodeID, reconciliation_loop: ReconciliationLoop):
        self._db_uri = db_uri
        self._channel = f"events_{node_id}"
        self._reconciliation_loop = reconciliation_loop

        stop_timeout = (4 * EVENT_TIMEOUT_MS) / 1_000.0
        self._controller = ThreadController(
            name=MONITOR_WORKER_THREAD_NAME,
            loop_action=self._run_loop,
            stop_timeout_sec=stop_timeout,
            daemon=True,
        )

    def _run_loop(self, is_stop_requested: Callable[[], bool]) -> None:
        @raises(Exception)
        def loop() -> None:
            with connect(self._db_uri, autocommit=True) as connection:
                query = sql.SQL("LISTEN {}").format(sql.Identifier(self._channel))
                connection.execute(query)
                LOGGER.debug(f"Listening on postgres channel: {self._channel}. Waiting for events...")

                keepalive_counter = 0
                while not is_stop_requested():
                    timeout = EVENT_TIMEOUT_MS / 1_000
                    ready, _, _ = select.select([connection.pgconn.socket], [], [], timeout)

                    if not ready:
                        if keepalive_counter % KEEPALIVE_CYCLE_PERIOD == 0:
                            attempt(lambda: connection.execute("SELECT 1"), exceptions=(Exception,)).flat_map_error(
                                lambda e: Result.failure(LOGGER.error(f"Error sending keepalive ping: {e}"))
                            )
                        keepalive_counter = (keepalive_counter + 1) % KEEPALIVE_CYCLE_PERIOD
                        continue

                    connection.pgconn.consume_input()

                    while notify := connection.pgconn.notifies():
                        payload_str = notify.extra.decode("utf-8")
                        self._handle_payload(payload_str)

        LOGGER.debug(f"Thread {MONITOR_WORKER_THREAD_NAME} started")
        run_loop_result = attempt(loop)
        if run_loop_result.is_failure():
            LOGGER.error(
                f"Error while running {MONITOR_WORKER_THREAD_NAME}: "
                f"Closing thread with error: {run_loop_result.get_error()} "
                f"{type(run_loop_result.get_error())}"
            )
        return

    def _handle_payload(self, payload: str) -> None:
        event: dict[str, str] | None = attempt(
            lambda: json.loads(payload), exceptions=(json.JSONDecodeError,)
        ).value_or(None)
        if event is None:
            return
        LOGGER.debug(f"Received event: {event}")

        self._reconciliation_loop.trigger()

    def start(self) -> bool:
        return self._controller.start()

    def is_running(self) -> bool:
        return self._controller.is_running()

    def stop(self) -> bool:
        return self._controller.stop()
