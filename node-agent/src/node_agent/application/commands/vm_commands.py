from dataclasses import dataclass
from typing import Protocol

from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine
from node_agent.domain.model.entities import DomainUUID


class VMCommand(Protocol): ...


@dataclass(frozen=True)
class CreateVMCommand(VMCommand):
    vm_spec: DesiredVirtualMachine


@dataclass(frozen=True)
class StartVMCommand(VMCommand):
    domain_uuid: DomainUUID


@dataclass(frozen=True)
class StopVMCommand(VMCommand):
    domain_uuid: DomainUUID


@dataclass(frozen=True)
class DestroyVMCommand(VMCommand):
    domain_uuid: DomainUUID
