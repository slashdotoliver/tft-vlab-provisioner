import logging
import signal
import sys
from threading import Event
from types import FrameType
from typing import NoReturn

import libvirt

from node_agent.adapters.database.sqlalchemy_state_adapter import SqlAlchemyStateAdapter
from node_agent.adapters.executors.libvirt_command_executor import LibvirtCommandExecutor
from node_agent.adapters.system.libvirt_environment_adapter import LibvirtEnvironmentAdapter
from node_agent.adapters.system.libvirt_network_adapter import LibvirtNetworkAdapter
from node_agent.adapters.system.libvirt_pool_storage_adapter import LibvirtPoolStorageAdapter
from node_agent.adapters.system.libvirt_state_adapter import LibvirtStateAdapter
from node_agent.adapters.system.linux_environment_adapter import LinuxEnvironmentAdapter
from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.adapters.workers.mock_lifecycle_event_handler import MockLifecycleEventHandler
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.application.ports.pool_storage_provider import PoolStorageProviderPort
from node_agent.application.ports.virtual_network_provider import NetworkProviderPort
from node_agent.application.ports.worker import Worker
from node_agent.application.services.reconciliation_loop import ReconciliationLoop
from node_agent.application.use_cases.environment_validator import EnvironmentValidator
from node_agent.application.use_cases.reconcile_state import ReconcileStateUseCase
from node_agent.config.config_sqlalchemy import DatabaseConfig, generate_local_session_factory
from node_agent.config.logging_formatter import configure_logging
from node_agent.domain.attempt import attempt
from node_agent.domain.model.entities import NodeID
from node_agent.domain.model.environment_models import (
    EnvironmentCheckError,
    EnvironmentConfig,
    NetFSPoolConfig,
    NetworkConfig,
    ValidationReport,
)
from node_agent.domain.model.result import Result

shutdown_event: Event = Event()
SERVICE_NAME = "node-agent"
NODE_NAME = NodeID("testnode-01")
LOGGER = logging.getLogger(__name__)


def shutdown_handler(signum: int, frame: FrameType | None) -> None:
    LOGGER.debug(f"Received signal: {signal.Signals(signum).name}")
    LOGGER.info(f"Stopping {SERVICE_NAME} service...")
    shutdown_event.set()


def leave() -> NoReturn:
    LOGGER.info(f"All threads terminated. Stopped {SERVICE_NAME}.")
    # TODO: check exit errors
    sys.exit(0)


def bootstrap_storage(
    pool_storage_port: PoolStorageProviderPort, pools: tuple[NetFSPoolConfig, ...]
) -> None | NoReturn:
    for pool_cfg in pools:
        res = pool_storage_port.initialize_pool(pool_cfg)
        if res.is_failure():
            LOGGER.critical(f"Error while initializing pool '{pool_cfg.name}': {res.get_error()}")
            return leave()


def bootstrap_networks(
    virtual_network_port: NetworkProviderPort, networks: tuple[NetworkConfig, ...]
) -> None | NoReturn:
    for network_cfg in networks:
        res = virtual_network_port.initialize_network(network_cfg)
        if res.is_failure():
            LOGGER.critical(f"Error while initializing network '{network_cfg.name}': {res.get_error()}")
            return leave()


def main():
    # Parse config
    # TODO: parse config file
    configure_logging(logging.DEBUG)
    uri = "qemu:///system"
    lab_network = NetworkConfig(name="lab_network", mode="bridge", bridge_name="br0")
    bases_pool = NetFSPoolConfig(
        name="bases",
        source_host="localhost",
        source_dir="/export/bases",
        target_path="/var/lib/libvirt/images/bases",
        is_readonly=True,
    )
    vms_pool = NetFSPoolConfig(
        name="vms",
        source_host="localhost",
        source_dir="/export/vms",
        target_path="/run/media/oliver/D03/ISOS/vms/tfglabpool",
        is_readonly=False,
    )
    database_url = "postgresql+psycopg://manager_db_user:PASSWD@localhost:5432/lab_db"

    LOGGER.info(f"Starting {SERVICE_NAME} service...")

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    LOGGER.debug("Signal handlers registered.")

    # Validate environment
    validate_environment(EnvironmentConfig(), uri)

    # Start connection
    libvirt.virEventRegisterDefaultImpl()
    connection: libvirt.virConnect | None = attempt(
        lambda: libvirt.open(uri), exceptions=(libvirt.libvirtError,)
    ).value_or(None)
    if connection is None:
        LOGGER.critical(f"Failed to open connection to libvirt with URI: {uri}")
        leave()

    # Initialize networks
    bootstrap_networks(LibvirtNetworkAdapter(connection), (lab_network,))

    # Initialize pools
    bootstrap_storage(
        LibvirtPoolStorageAdapter(connection),
        (
            bases_pool,
            vms_pool,
        ),
    )

    # Start workers/services
    db_config: DatabaseConfig = DatabaseConfig(database_url=database_url)
    db_adapter: DesiredStatePort = SqlAlchemyStateAdapter(generate_local_session_factory(db_config, False))

    reconcile_state_evaluator = ReconcileStateUseCase(
        db_port=db_adapter, state_port=LibvirtStateAdapter(connection), node_id=NODE_NAME
    )
    reconciliation_loop = ReconciliationLoop(
        reconcile_state_evaluator=reconcile_state_evaluator,
        executor=LibvirtCommandExecutor(connection, bases_pool, vms_pool),
        min_interval_sec=5.0,
        nominal_interval_sec=120.0,
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
