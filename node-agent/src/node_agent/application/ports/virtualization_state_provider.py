from typing import Protocol

from node_agent.domain.model.entities import VirtualMachine
from node_agent.domain.model.result import Result


class VirtualizationStatePort(Protocol):
    """Port to query the hypervisor for the actual state of the infrastructure."""

    def get_actual_vms(self) -> Result[list[VirtualMachine], Exception]:
        """Returns a list of all currently defined virtual machines and their states."""
        ...
