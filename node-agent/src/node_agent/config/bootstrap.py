import logging

from node_agent.adapters.system.libvirt_environment_adapter import LibvirtEnvironmentAdapter
from node_agent.adapters.system.linux_environment_adapter import LinuxEnvironmentAdapter
from node_agent.application.ports.pool_storage_provider import PoolStorageProviderPort
from node_agent.application.ports.virtual_network_provider import NetworkProviderPort
from node_agent.application.use_cases.environment_validator import EnvironmentValidator
from node_agent.domain.attempt import raises
from node_agent.domain.model.environment_models import (
    EnvironmentConfig,
    NetFSPoolConfig,
    NetworkConfig,
    ValidationReport,
)

LOGGER = logging.getLogger(__name__)


class BootstrapError(Exception): ...


@raises(BootstrapError)
def bootstrap_storage(port: PoolStorageProviderPort, pools: tuple[NetFSPoolConfig, ...]) -> None:
    for pool_cfg in pools:
        res = port.initialize_pool(pool_cfg)
        if res.is_failure():
            raise BootstrapError(f"Error while initializing pool '{pool_cfg.name}': {res.get_error()}")


@raises(BootstrapError)
def bootstrap_networks(port: NetworkProviderPort, networks: tuple[NetworkConfig, ...]) -> None:
    for network_cfg in networks:
        res = port.initialize_network(network_cfg)
        if res.is_failure():
            raise BootstrapError(f"Error while initializing network '{network_cfg.name}': {res.get_error()}")


@raises(BootstrapError)
def validate_environment(config: EnvironmentConfig, uri: str) -> None:
    report = EnvironmentValidator(
        sys_port=LinuxEnvironmentAdapter(), libvirt_port=LibvirtEnvironmentAdapter(uri)
    ).validate_environment(config)

    if report.is_failure():
        raise BootstrapError(f"Failed to validate environment: {report.get_error()}")

    issues = report.value_or(ValidationReport()).issues
    if len(issues) > 0:
        raise BootstrapError(f"Could not satisfy configuration:\n{issues}")
