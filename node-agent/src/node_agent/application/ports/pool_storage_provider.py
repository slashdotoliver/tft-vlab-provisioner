from typing import Protocol

from node_agent.domain.model.environment_models import NetFSPoolConfig
from node_agent.domain.model.result import Result


class PoolStorageProviderPort(Protocol):
    def initialize_pool(self, config: NetFSPoolConfig) -> Result[None, Exception]:
        """Ensures a storage pool is defined, active, and set to autostart."""
        ...
