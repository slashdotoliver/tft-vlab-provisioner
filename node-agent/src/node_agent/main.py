import logging
import signal
import sys
from threading import Event
from types import FrameType
from typing import NoReturn, Any

import libvirt

from node_agent.adapters.system.libvirt_environment_adapter import LibvirtEnvironmentAdapter
from node_agent.adapters.system.linux_environment_adapter import LinuxEnvironmentAdapter
from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.adapters.workers.mock_lifecycle_event_handler import MockLifecycleEventHandler
from node_agent.application.ports.worker import Worker
from node_agent.application.use_cases.environment_validator import EnvironmentValidator
from node_agent.domain.attempt import attempt
from node_agent.domain.model.environment_models import EnvironmentConfig, ValidationReport, EnvironmentCheckError
from node_agent.domain.model.result import Result

shutdown_event: Event = Event()
SERVICE_NAME = "node-agent"
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
    LOGGER.info(f"Starting {SERVICE_NAME} service...")

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    LOGGER.debug("Signal handlers registered.")

    # Parse config
    uri = 'qemu:///system'

    # Validate environment
    validate_environment(EnvironmentConfig(), uri)

    libvirt.virEventRegisterDefaultImpl()
    connection: libvirt.virConnect | None = attempt(
        lambda: libvirt.open(uri),
        exceptions=(libvirt.libvirtError,)
    ).value_or(None)
    if connection is None:
        LOGGER.error(f"Failed to open connection to libvirt.")
    else:
        monitor_worker: Worker = LibvirtMonitorWorker(connection, MockLifecycleEventHandler())
        monitor_worker.run()
        shutdown_event.wait()
        monitor_worker.stop()


def validate_environment(config: EnvironmentConfig, uri: str) -> None | NoReturn:
    report: Result[ValidationReport, EnvironmentCheckError] = (
        EnvironmentValidator(sys_port=LinuxEnvironmentAdapter(), libvirt_port=LibvirtEnvironmentAdapter(uri))
        .validate_environment(config)
    )
    if report.is_failure():
        LOGGER.error(f"Failed to validate environment: {report.get_error()}")
        leave()
    issues = report.value_or(ValidationReport()).issues
    if len(issues) > 0:
        LOGGER.error(f"Could not satisfy configuration:\n{issues}")
        leave()
