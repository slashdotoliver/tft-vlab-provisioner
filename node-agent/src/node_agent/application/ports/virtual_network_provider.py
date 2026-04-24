from typing import Protocol

from node_agent.domain.model.environment_models import NetworkConfig
from node_agent.domain.model.result import Result


class NetworkProviderPort(Protocol):
    def initialize_network(self, config: NetworkConfig) -> Result[None, Exception]:
        """Ensures a network is defined, active, and set to autostart."""
        ...
