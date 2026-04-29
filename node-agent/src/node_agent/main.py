import logging
from contextlib import ExitStack

from libvirt import virConnect

from node_agent.adapters.database.sqlalchemy_state_adapter import SqlAlchemyStateAdapter
from node_agent.adapters.executors.libvirt_command_executor import LibvirtCommandExecutor
from node_agent.adapters.system.libvirt_network_adapter import LibvirtNetworkAdapter
from node_agent.adapters.system.libvirt_pool_storage_adapter import LibvirtPoolStorageAdapter
from node_agent.adapters.system.libvirt_state_adapter import LibvirtStateAdapter
from node_agent.adapters.system.linux_environment_adapter import get_linux_hardware_node
from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.adapters.workers.postgres_event_listener import PostgresEventMonitorWorker
from node_agent.application.handlers.reconciliation_lifecycle_event_handler import ReconciliationTrigger
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.application.services.reconciliation_loop import ReconciliationLoop
from node_agent.application.use_cases.reconcile_state_evaluator import ReconcileStateEvaluatorUseCase
from node_agent.application.use_cases.report_node_status import ReportNodeStatusUseCase
from node_agent.config.bootstrap import BootstrapError, bootstrap_networks, bootstrap_storage, validate_environment
from node_agent.config.config_sqlalchemy import DatabaseConfig, generate_session_factory
from node_agent.config.lifecycle import ShutdownManager, managed_libvirt_connection, managed_runnable
from node_agent.config.logging_formatter import configure_logging
from node_agent.config.settings import AppConfig, ConfigParseError
from node_agent.domain.attempt import attempt, raises
from node_agent.domain.model.entities import Node
from node_agent.domain.model.environment_models import NetFSPoolConfig

LOGGER = logging.getLogger(__name__)


def main():
    attempt(_main).on_failure(lambda error: LOGGER.critical(error))


@raises(ConfigParseError, BootstrapError)
def _main():
    config = AppConfig.from_toml("config.toml")

    configure_logging(config.logging_level)
    LOGGER.info(f"Starting {config.service_name} service...")

    shutdown_manager = ShutdownManager()

    # noinspection PyAbstractClass
    exit_stack = ExitStack()
    with exit_stack as stack:
        connection = stack.enter_context(managed_libvirt_connection(config.libvirt_uri))

        validate_environment(config.environment.to_domain(), config.libvirt_uri)

        pools = _initialize_pools_and_networks(config, connection)

        db_adapter = SqlAlchemyStateAdapter(
            generate_session_factory(DatabaseConfig(database_url=config.database.sqlalchemy_url), False)
        )

        hardware_node = get_linux_hardware_node(config.node_name)

        db_adapter.register_or_update_node(hardware_node).on_failure(
            lambda error: LOGGER.critical(f"Could not register node '{config.node_name}': {error}")
        )

        reconciliation_loop = _create_main_loop(connection, db_adapter, hardware_node, pools[0], pools[1])

        _start_threads(config, connection, hardware_node, reconciliation_loop, stack)

        LOGGER.debug("Waiting for shutdown signal...")
        shutdown_manager.wait()


@raises(BootstrapError)
def _initialize_pools_and_networks(config: AppConfig, connection: virConnect) -> tuple[NetFSPoolConfig, ...]:
    networks = config.get_all_networks()
    bootstrap_networks(LibvirtNetworkAdapter(connection), networks)
    pools = config.get_all_pools()
    bootstrap_storage(LibvirtPoolStorageAdapter(connection), pools)
    return pools


def _create_main_loop(
    connection: virConnect,
    db_adapter: DesiredStatePort,
    hardware_node: Node,
    bases_pool: NetFSPoolConfig,
    vms_pool: NetFSPoolConfig,
) -> ReconciliationLoop:
    state_adapter = LibvirtStateAdapter(connection)
    return ReconciliationLoop(
        reconcile_state_evaluator=(
            ReconcileStateEvaluatorUseCase(db_port=db_adapter, state_port=state_adapter, node_id=hardware_node.node_id)
        ),
        node_status_reporter=ReportNodeStatusUseCase(
            db_port=db_adapter, state_port=state_adapter, node_id=hardware_node.node_id
        ),
        executor=LibvirtCommandExecutor(connection, bases_pool, vms_pool),
        min_interval_sec=5.0,
        nominal_interval_sec=120.0,
    )


@raises(RuntimeError)
def _start_threads(
    config: AppConfig,
    connection: virConnect,
    hardware_node: Node,
    reconciliation_loop: ReconciliationLoop,
    stack: ExitStack[bool | None],
):
    stack.enter_context(managed_runnable(reconciliation_loop))
    stack.enter_context(managed_runnable(LibvirtMonitorWorker(connection, ReconciliationTrigger(reconciliation_loop))))
    stack.enter_context(
        managed_runnable(
            PostgresEventMonitorWorker(config.database.psycopg_url, hardware_node.node_id, reconciliation_loop)
        )
    )
