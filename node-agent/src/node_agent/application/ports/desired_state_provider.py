from typing import Protocol

from node_agent.domain.model.desired_state import DesiredVirtualMachine
from node_agent.domain.model.entities import LeaseID, NodeID


class DesiredStatePort(Protocol):
    def get_desired_vms_for_node(self, node_id: NodeID) -> list[DesiredVirtualMachine]: ...

    def report_actual_state(self, lease_id: LeaseID, state: str) -> None: ...

    def update_heartbeat(self, node_id: NodeID) -> None: ...
