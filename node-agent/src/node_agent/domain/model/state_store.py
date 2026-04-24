from threading import Lock

from node_agent.domain.model.entities import DomainUUID, VirtualMachine


class NodeStateStore:
    def __init__(self):
        self._lock = Lock()
        self._vms: dict[DomainUUID, VirtualMachine] = {}

    def update_vm(self, vm: VirtualMachine) -> None:
        with self._lock:
            self._vms[vm.uuid] = vm

    def get_actual_state(self) -> list[VirtualMachine]:
        with self._lock:
            return list(self._vms.values())
