import logging

from node_agent.application.commands.vm_commands import CreateVMCommand, StartVMCommand, StopVMCommand, VMCommand
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.domain.model.entities import NodeID
from node_agent.domain.model.state_store import NodeStateStore

LOGGER = logging.getLogger(__name__)


class ReconcileStateUseCase:
    def __init__(self, db_port: DesiredStatePort, state_store: NodeStateStore, node_id: NodeID):
        self.db_port = db_port
        self.state_store = state_store
        self.node_id = node_id

    def evaluate(self) -> list[VMCommand]:
        """Compara estado deseado vs actual y decide qué acciones tomar."""
        commands: list[VMCommand] = []

        desired_vms = self.db_port.get_desired_vms_for_node(self.node_id)
        actual_vms = self.state_store.get_actual_state()
        actual_map = {vm.uuid: vm for vm in actual_vms}

        for desired in desired_vms:
            actual = actual_map.get(desired.domain_uuid)

            if not actual:
                commands.append(CreateVMCommand(vm_spec=desired))
                if desired.should_be_running:
                    commands.append(StartVMCommand(domain_uuid=desired.domain_uuid))
            else:
                is_running = actual.state == "running"

                if desired.should_be_running and not is_running:
                    commands.append(StartVMCommand(domain_uuid=desired.domain_uuid))
                elif not desired.should_be_running and is_running:
                    commands.append(StopVMCommand(domain_uuid=desired.domain_uuid))

        return commands
