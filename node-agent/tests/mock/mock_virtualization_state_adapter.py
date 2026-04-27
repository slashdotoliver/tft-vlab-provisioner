from node_agent.application.ports.virtualization_state_provider import VirtualizationStatePort
from node_agent.domain.model.entities import VirtualMachine
from node_agent.domain.model.result import Result


class MockStateAdapter(VirtualizationStatePort):
    def __init__(self, virtual_machines: list[VirtualMachine]):
        self.virtual_machines = virtual_machines

    def get_actual_vms(self) -> Result[list[VirtualMachine], Exception]:
        return Result.success(self.virtual_machines)
