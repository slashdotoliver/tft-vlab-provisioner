import logging

from node_agent.application.commands.vm_commands import (
    CreateVMCommand,
    DestroyVMCommand,
    StartVMCommand,
    StopVMCommand,
    VMCommand,
)
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.domain.model.desired_state_entities import DesiredVmState
from node_agent.domain.model.entities import NodeID, VirtualMachine
from node_agent.domain.model.state_store import NodeStateStore

LOGGER = logging.getLogger(__name__)


class ReconcileStateUseCase:
    def __init__(self, db_port: DesiredStatePort, state_store: NodeStateStore, node_id: NodeID):
        self.db_port = db_port
        self.state_store = state_store
        self.node_id = node_id

    def evaluate(self) -> list[VMCommand]:
        """Compares desired state vs current state and decides what actions to take."""
        commands: list[VMCommand] = []

        desired_vms = self.db_port.get_desired_vms_for_node(self.node_id)
        actual_vms = self.state_store.get_actual_state()
        actual_map = {vm.uuid: vm for vm in actual_vms}

        for desired in desired_vms:
            actual: VirtualMachine | None = actual_map.get(desired.domain_uuid)

            if desired.target_state == DesiredVmState.ABSENT:
                if actual:
                    if actual.state == "running":
                        commands.append(StopVMCommand(domain_uuid=desired.domain_uuid))
                    commands.append(DestroyVMCommand(domain_uuid=desired.domain_uuid))
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

        for unmanaged_vm in unmanaged_vms_uuid:
            LOGGER.warning(f"Unmanaged VM: {unmanaged_vm}")
            # TODO: check if uuid exists in some previous lease and remove domain in that case
            # keep domains that are not controlled by this agent

        return commands
