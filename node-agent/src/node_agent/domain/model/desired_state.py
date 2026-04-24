from dataclasses import dataclass, field
from typing import Literal

from node_agent.domain.model.entities import DomainUUID, LeaseID


@dataclass(frozen=True)
class DesiredNetwork:
    mac_address: str
    network_name: str
    bridge_name: str


@dataclass(frozen=True)
class DesiredDisk:
    base_volume_name: str
    volume_name: str
    target_dev: str
    target_bus: str
    driver: Literal["qemu"]
    subdriver: Literal["qcow2"]


@dataclass(frozen=True)
class DesiredVirtualMachine:
    lease_id: LeaseID
    domain_uuid: DomainUUID
    vcpus: int
    ram_mb: int
    should_be_running: bool
    should_be_defined: bool
    networks: tuple[DesiredNetwork, ...] = field(default_factory=tuple)
    disks: tuple[DesiredDisk, ...] = field(default_factory=tuple)
