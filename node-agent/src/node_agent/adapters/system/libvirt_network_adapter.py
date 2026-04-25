import logging

from libvirt import VIR_ERR_NO_NETWORK, libvirtError, virConnect, virNetwork

from node_agent.application.ports.virtual_network_provider import NetworkProviderPort
from node_agent.domain.attempt import attempt
from node_agent.domain.model.environment_models import NetworkConfig
from node_agent.domain.model.result import Result
from node_agent.templates.network_xml import render_network_xml

LOGGER = logging.getLogger(__name__)


class LibvirtNetworkAdapter(NetworkProviderPort):
    def __init__(self, connection: virConnect):
        self._connection = connection

    def initialize_network(self, config: NetworkConfig) -> Result[None, Exception]:
        def _ensure_running(network: virNetwork) -> Result[None, Exception]:
            def _do_ensure() -> None:
                if not network.isActive():
                    LOGGER.info(f"Starting network '{config.name}'...")
                    network.create()
                if not network.autostart():
                    network.setAutostart(1)

            return attempt(_do_ensure, (Exception,))

        return (
            self._get_network(config)
            .map_error(lambda error: self._create_if_missing(config, error))
            .flat_map(_ensure_running)
        )

    def _get_network(self, config: NetworkConfig) -> Result[virNetwork, Exception]:
        return attempt(lambda: self._connection.networkLookupByName(config.name), exceptions=(libvirtError,))

    def _create_if_missing(self, config: NetworkConfig, error: Exception) -> Result[virNetwork, Exception]:
        if isinstance(error, libvirtError) and error.get_error_code() == VIR_ERR_NO_NETWORK:
            LOGGER.info(f"Network '{config.name}' not found. Defining network...")
            return self._define_network(config)

        LOGGER.error(f"Unexpected error looking up network '{config.name}'")
        return Result.failure(error)

    def _define_network(self, config: NetworkConfig) -> Result[virNetwork, Exception]:
        def _do_define() -> virNetwork:
            xml_str = render_network_xml(config)

            network = self._connection.networkDefineXML(xml_str)
            if network is None:
                raise Exception(f"Libvirt returned None while defining network '{config.name}'")

            return network

        return attempt(_do_define, (Exception,))
