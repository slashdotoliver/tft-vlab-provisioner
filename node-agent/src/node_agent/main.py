import logging
import signal
import sys
from threading import Event
from types import FrameType
from typing import NoReturn
from uuid import NIL

import libvirt

from node_agent.adapters.executors.libvirt_command_executor import LibvirtCommandExecutor
from node_agent.adapters.system.libvirt_environment_adapter import LibvirtEnvironmentAdapter
from node_agent.adapters.system.linux_environment_adapter import LinuxEnvironmentAdapter
from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.adapters.workers.mock_lifecycle_event_handler import MockLifecycleEventHandler
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.application.ports.worker import Worker
from node_agent.application.services.reconciliation_loop import ReconciliationLoop
from node_agent.application.use_cases.environment_validator import EnvironmentValidator
from node_agent.application.use_cases.reconcile_state import ReconcileStateUseCase
from node_agent.config.logging_formatter import LoggingColoredFormatter, configure_logging
from node_agent.domain.attempt import attempt
from node_agent.domain.model.desired_state import DesiredVirtualMachine
from node_agent.domain.model.entities import DomainUUID, LeaseID, NodeID
from node_agent.domain.model.environment_models import EnvironmentCheckError, EnvironmentConfig, ValidationReport
from node_agent.domain.model.result import Result
from node_agent.domain.model.state_store import NodeStateStore

shutdown_event: Event = Event()
SERVICE_NAME = "node-agent"
NODE_NAME = NodeID("node-01")
LOGGER = logging.getLogger(__name__)


def shutdown_handler(signum: int, frame: FrameType | None) -> None:
    LOGGER.debug(f"Received signal: {signal.Signals(signum).name}")
    LOGGER.info(f"Stopping {SERVICE_NAME} service...")
    shutdown_event.set()


def leave() -> NoReturn:
    LOGGER.info(f"All threads terminated. Stopped {SERVICE_NAME}.")
    # TODO: check exit errors
    sys.exit(0)


def main():
    # TODO: parse config file
    configure_logging(logging.DEBUG)
    uri = "qemu:///system"

    LOGGER.info(f"Starting {SERVICE_NAME} service...")

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    LOGGER.debug("Signal handlers registered.")

    # Validate environment
    validate_environment(EnvironmentConfig(), uri)

    # Start workers
    libvirt.virEventRegisterDefaultImpl()
    connection: libvirt.virConnect | None = attempt(
        lambda: libvirt.open(uri), exceptions=(libvirt.libvirtError,)
    ).value_or(None)
    if connection is None:
        LOGGER.critical(f"Failed to open connection to libvirt with URI: {uri}")
        leave()

    class MockDB(DesiredStatePort):
        def get_desired_vms_for_node(self, n) -> list[DesiredVirtualMachine]:
            test_vm = DesiredVirtualMachine(
                lease_id=LeaseID(NIL),
                domain_uuid=DomainUUID(NIL),
                vcpus=4,
                ram_mb=512,
                should_be_defined=False,
                should_be_running=True,
                networks=tuple(),
                disks=tuple(),
            )

            return [test_vm]

    node_store = NodeStateStore()
    reconcile_state_evaluator = ReconcileStateUseCase(db_port=(MockDB()), state_store=node_store, node_id=NODE_NAME)
    reconciliation_loop = ReconciliationLoop(
        reconcile_state_evaluator=reconcile_state_evaluator,
        executor=LibvirtCommandExecutor(connection),
        min_interval_sec=1.0,
        max_interval_sec=5.0,
    )

    # =============

    monitor_worker: Worker = LibvirtMonitorWorker(connection, MockLifecycleEventHandler(reconciliation_loop))
    monitor_worker.run()
    reconciliation_loop.start()

    LOGGER.debug("Waiting for shutdown event...")
    shutdown_event.wait()

    monitor_worker.stop()
    reconciliation_loop.stop()


def validate_environment(config: EnvironmentConfig, uri: str) -> None | NoReturn:
    report: Result[ValidationReport, EnvironmentCheckError] = EnvironmentValidator(
        sys_port=LinuxEnvironmentAdapter(), libvirt_port=LibvirtEnvironmentAdapter(uri)
    ).validate_environment(config)
    if report.is_failure():
        LOGGER.critical(f"Failed to validate environment: {report.get_error()}")
        leave()
    issues = report.value_or(ValidationReport()).issues
    if len(issues) > 0:
        LOGGER.critical(f"Could not satisfy configuration:\n{issues}")
        leave()
