from typing import Protocol

from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine, LeaseStateUpdate
from node_agent.domain.model.entities import NodeID
from node_agent.domain.model.result import Result


class DesiredStatePort(Protocol):
    def get_desired_vms_for_node(self, node_id: NodeID) -> list[DesiredVirtualMachine]: ...

    def report_node_status(self, node_id: NodeID, updates: list[LeaseStateUpdate]) -> Result[None, Exception]: ...
