from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine
from node_agent.domain.model.entities import LeaseID, NodeID


class MockDesiredStateAdapter(DesiredStatePort):
    def __init__(self, desired_vms: list[DesiredVirtualMachine]):
        self.desired_vms = desired_vms

    def get_desired_vms_for_node(self, node_id: NodeID) -> list[DesiredVirtualMachine]:
        return self.desired_vms

    def report_actual_state(self, lease_id: LeaseID, state: str) -> None:
        return

    def update_heartbeat(self, node_id: NodeID) -> None:
        return
