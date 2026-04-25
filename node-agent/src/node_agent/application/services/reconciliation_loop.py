import logging
import time
from threading import Event, Thread

from node_agent.application.commands.vm_commands import VMCommand
from node_agent.application.ports.virtualization_command_executor import VirtualizationCommandExecutor
from node_agent.application.services.service import Service
from node_agent.application.use_cases.reconcile_state import ReconcileStateUseCase
from node_agent.domain.attempt import attempt
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)
RECONCILIATION_SERVICE_THREAD_NAME: str = "ReconciliationLoopServiceThread0"


class ReconciliationLoop(Service):
    def __init__(
        self,
        reconcile_state_evaluator: ReconcileStateUseCase,
        executor: VirtualizationCommandExecutor,
        min_interval_sec: float,
        nominal_interval_sec: float,
    ):
        self.reconcile_state_evaluator = reconcile_state_evaluator
        self.executor = executor
        self.min_interval_sec = min_interval_sec
        self.nominal_interval_sec = nominal_interval_sec
        self._wake_up_event = Event()
        self._stop_event = Event()
        self._service_thread: None | Thread = None
        self._last_run_time = 0.0
        self.stop_timeout_sec = min_interval_sec * 2

        assert self.min_interval_sec <= self.nominal_interval_sec
        assert self.min_interval_sec > 0

    @property
    def _thread_started(self) -> bool:
        return self._service_thread is not None and self._service_thread.is_alive()

    @property
    def _running(self) -> bool:
        return not self._stop_event.is_set()

    def trigger(self) -> None:
        self._wake_up_event.set()

    def start(self) -> bool:
        def thread_start_exception_mapper(exception: Exception) -> RuntimeError:
            LOGGER.error(exception)
            return RuntimeError(exception)

        if self._thread_started:
            LOGGER.warning(f"Trying to start {RECONCILIATION_SERVICE_THREAD_NAME} thread that has already started")
            return False

        LOGGER.debug("Starting reconciliation loop...")
        self._stop_event.clear()
        self._service_thread = Thread(target=self._event_loop, name=RECONCILIATION_SERVICE_THREAD_NAME, daemon=False)

        return (
            attempt(
                lambda: self._service_thread.start(),
                exceptions=(RuntimeError,),
                exception_mapper=thread_start_exception_mapper,
            )
            .map(lambda success: True)
            .value_or(False)
        )

    def _event_loop(self) -> None:
        while self._running:
            now: float = time.time()
            time_since_last_run = now - self._last_run_time

            if time_since_last_run < self.min_interval_sec:
                sleep_time = self.min_interval_sec - time_since_last_run
                time.sleep(sleep_time)
                continue

            if time_since_last_run > self.nominal_interval_sec:
                self.execute()
                self._wake_up_event.clear()
                continue

            event_triggered = self._wake_up_event.wait(timeout=self.min_interval_sec)
            if not event_triggered:
                continue

            self.execute()
            self._wake_up_event.clear()

    def execute(self) -> None:
        try:
            evaluation: Result[list[VMCommand], Exception] = Result.success(self.reconcile_state_evaluator.evaluate())
            if evaluation.is_success():
                LOGGER.debug("Evaluation completed")
            else:
                return LOGGER.error(f"Error during reconciliation: {evaluation.get_error()}")

            execution = self.executor.execute_all(commands=(evaluation.value_or([])))
            if execution.is_success():
                LOGGER.debug("Execution completed")
            else:
                return LOGGER.error(f"Error during reconciliation: {execution.get_error()}")
        finally:
            self._last_run_time = time.time()

    def stop(self) -> bool:
        self._stop_event.set()

        self._service_thread.join(timeout=self.stop_timeout_sec)

        if self._service_thread.is_alive():
            LOGGER.error(f"The thread {RECONCILIATION_SERVICE_THREAD_NAME} did not stop in time")
            return False
        LOGGER.debug(
            f"The thread {RECONCILIATION_SERVICE_THREAD_NAME} stopped"
            if self._service_thread
            else f"The thread {RECONCILIATION_SERVICE_THREAD_NAME} never started"
        )
        return True
