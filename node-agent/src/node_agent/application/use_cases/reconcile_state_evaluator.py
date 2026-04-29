import logging
from dataclasses import dataclass

from node_agent.application.commands.vm_commands import (
    CreateVMCommand,
    DestroyVMCommand,
    StartVMCommand,
    StopVMCommand,
    VMCommand,
)
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.application.ports.virtualization_state_provider import VirtualizationStatePort
from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine, DesiredVmState
from node_agent.domain.model.entities import NodeID, VirtualMachine
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationPlan:
    commands: list[VMCommand]
    desired_vms: list[DesiredVirtualMachine]


class ReconcileStateEvaluatorUseCase:
    def __init__(self, db_port: DesiredStatePort, state_port: VirtualizationStatePort, node_id: NodeID):
        self.db_port = db_port
        self.state_port = state_port
        self.node_id = node_id

    def evaluate(self) -> Result[EvaluationPlan, Exception]:
        """Compares desired state vs current state and decides what actions to take."""

        return self.db_port.get_desired_vms_for_node(self.node_id).flat_map(
            lambda desired_vms: (
                self.state_port.get_actual_vms()
                .on_failure(lambda error: LOGGER.error(f"Error while getting current virtual machines: {error}"))
                .map(
                    lambda actual_vms: EvaluationPlan(
                        commands=self._evaluate(actual_vms, desired_vms), desired_vms=desired_vms
                    )
                )
            )
        )

    def _evaluate(self, actual_vms: list[VirtualMachine], desired_vms: list[DesiredVirtualMachine]) -> list[VMCommand]:
        commands: list[VMCommand] = []
        actual_map = {vm.uuid: vm for vm in actual_vms}

        for desired in desired_vms:
            actual: VirtualMachine | None = actual_map.get(desired.domain_uuid)

            if desired.target_state == DesiredVmState.ABSENT:
                if actual:
                    if actual.state == "running":
                        commands.append(StopVMCommand(domain_uuid=desired.domain_uuid))
                    commands.append(DestroyVMCommand(domain_uuid=desired.domain_uuid, disks_to_delete=desired.disks))
                continue

            if desired.target_state == DesiredVmState.SHUTOFF:
                if not actual:
                    commands.append(CreateVMCommand(vm_spec=desired))
                elif actual.state == "running":
                    commands.append(StopVMCommand(domain_uuid=desired.domain_uuid))
                continue

            if desired.target_state == DesiredVmState.RUNNING:
                if not actual:
                    commands.append(CreateVMCommand(vm_spec=desired))
                    commands.append(StartVMCommand(domain_uuid=desired.domain_uuid))
                elif actual.state != "running":
                    commands.append(StartVMCommand(domain_uuid=desired.domain_uuid))
        unmanaged_vms_uuid = set(actual_map.keys()) - {node.domain_uuid for node in desired_vms}

        # TODO: check if uuid exists in some previous lease and remove domain and volumes in that case
        #  keep domains that are not controlled by this agent
        LOGGER.debug(f"Unmanaged VMs: {unmanaged_vms_uuid}") if unmanaged_vms_uuid else None
        return commands
