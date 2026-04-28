import logging
from typing import Any, Callable

from libvirt import (
    VIR_DOMAIN_EVENT_ID_LIFECYCLE,
    virConnect,
    virDomain,
    virEventAddTimeout,
    virEventRemoveTimeout,
    virEventRunDefaultImpl,
)

from node_agent.application.controllers.thread_controller import ThreadController
from node_agent.application.handlers.domain_lifecycle_event_handler import DomainLifecycleEventHandler
from node_agent.application.ports.worker import Worker
from node_agent.domain.attempt import attempt
from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType

LOGGER = logging.getLogger(__name__)
MONITOR_WORKER_THREAD_NAME: str = "LibvirtMonitorWorker-Thread-0"
EVENT_TIMEOUT_MS: int = 500


class LibvirtMonitorWorker(Worker):
    def __init__(self, connection: virConnect, lifecycle_event_handler: DomainLifecycleEventHandler):
        self._connection = connection
        self._lifecycle_event_handler = lifecycle_event_handler

        self._timeout_id: int = -1
        self._lifecycle_event_id: int = -1

        stop_timeout = (4 * EVENT_TIMEOUT_MS) / 1_000.0
        self._controller = ThreadController(
            name=MONITOR_WORKER_THREAD_NAME,
            loop_action=self._run_loop,
            stop_timeout_sec=stop_timeout,
            daemon=True,
        )

    def _on_lifecycle_event(self, conn: virConnect, dom: virDomain, event: int, detail: int, opaque: Any):
        (
            attempt(lambda: DomainEventType(event), exceptions=(ValueError,))
            .on_success(
                lambda event_type: self._lifecycle_event_handler.handle_lifecycle_event(dom.name(), event_type, detail)
            )
            .on_failure(
                lambda error: LOGGER.error(
                    f"The lifecycle event was triggered with an unknown lifecycle event type: {error}"
                )
            )
        )

    def _dummy_timeout_cb(self, timer_id, opaque):
        pass

    def _run_loop(self, is_stop_requested: Callable[[], bool]) -> None:
        LOGGER.debug(f"Thread {MONITOR_WORKER_THREAD_NAME} started")

        self._timeout_id = virEventAddTimeout(EVENT_TIMEOUT_MS, self._dummy_timeout_cb, None)
        self._lifecycle_event_id = self._connection.domainEventRegisterAny(
            dom=None, eventID=VIR_DOMAIN_EVENT_ID_LIFECYCLE, cb=self._on_lifecycle_event, opaque=None
        )

        try:
            while not is_stop_requested():
                virEventRunDefaultImpl()
        finally:
            if self._timeout_id != -1:
                virEventRemoveTimeout(self._timeout_id)
            if self._lifecycle_event_id != -1:
                self._connection.domainEventDeregisterAny(self._lifecycle_event_id)

    def start(self) -> bool:
        return self._controller.start()

    def is_running(self) -> bool:
        return self._controller.is_running()

    def stop(self) -> bool:
        return self._controller.stop()
