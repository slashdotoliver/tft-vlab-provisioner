import logging
import time
from threading import Event
from typing import Callable

from node_agent.application.controllers.thread_controller import ThreadController
from node_agent.application.ports.virtualization_command_executor import VirtualizationCommandExecutor
from node_agent.application.services.service import Service
from node_agent.application.use_cases.reconcile_state_evaluator import EvaluationPlan, ReconcileStateEvaluatorUseCase
from node_agent.application.use_cases.report_node_status import ReportNodeStatusUseCase

LOGGER = logging.getLogger(__name__)
RECONCILIATION_SERVICE_THREAD_NAME: str = "ReconciliationLoopService-Thread-0"


class ReconciliationLoop(Service):
    def __init__(
        self,
        reconcile_state_evaluator: ReconcileStateEvaluatorUseCase,
        node_status_reporter: ReportNodeStatusUseCase,
        executor: VirtualizationCommandExecutor,
        min_interval_sec: float,
        nominal_interval_sec: float,
    ):
        self.reconcile_state_evaluator = reconcile_state_evaluator
        self.node_status_reporter = node_status_reporter
        self.executor = executor
        self.min_interval_sec = min_interval_sec
        self.nominal_interval_sec = nominal_interval_sec
        self._wake_up_event = Event()
        self._last_run_time = 0.0

        assert self.min_interval_sec <= self.nominal_interval_sec
        assert self.min_interval_sec > 0

        stop_timeout_sec = min_interval_sec * 2
        self._controller = ThreadController(
            name=RECONCILIATION_SERVICE_THREAD_NAME,
            loop_action=self._run_loop,
            stop_timeout_sec=stop_timeout_sec,
            daemon=False,
        )

    def trigger(self) -> None:
        self._wake_up_event.set()

    def start(self) -> bool:
        return self._controller.start()

    def _run_loop(self, is_stop_requested: Callable[[], bool]) -> None:
        LOGGER.debug("Starting reconciliation loop thread...")

        while not is_stop_requested():
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
            (
                self.reconcile_state_evaluator.evaluate()
                .on_failure(lambda error: LOGGER.error(f"Skipping execution. Error during evaluation: {error}"))
                .on_success(lambda plan: LOGGER.info(f"Evaluation completed. Commands to execute: {plan.commands}"))
                .flat_tap(
                    lambda plan: (
                        self.executor.execute_all(commands=plan.commands)
                        .on_failure(lambda error: LOGGER.error(f"Error during execution: {error}"))
                        .on_success(lambda _: LOGGER.debug("Execution completed"))
                    )
                )
                .flat_map(
                    lambda plan: (
                        self.node_status_reporter.report(desired_vms=plan.desired_vms)
                        .on_failure(lambda error: LOGGER.error("Failed to report node status to the database"))
                        .on_success(lambda _: LOGGER.debug("Node status and heartbeat successfully reported"))
                    )
                )
            )
        finally:
            self._last_run_time = time.time()

    def stop(self) -> bool:
        self.trigger()
        return self._controller.stop()
