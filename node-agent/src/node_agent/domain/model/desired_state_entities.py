from dataclasses import dataclass, field
from enum import StrEnum, auto

from node_agent.domain.model.entities import DomainUUID, LeaseID


class DesiredVmState(StrEnum):
    RUNNING = auto()
    SHUTOFF = auto()
    ABSENT = auto()


@dataclass(frozen=True)
class DesiredNetworkInterface:
    mac_address: str
    network_type: str  # 'nat' | 'bridge'
    bridge_name: str
    model_type: str  # 'virtio'


@dataclass(frozen=True)
class DesiredDisk:
    target_dev: str  # 'vda'
    target_bus: str  # 'virtio'
    disk_driver: str  # 'qemu'
    disk_subdriver: str  # 'qcow2'
    volume_path: str  # copy-on-write volume path
    base_volume_path: str  # backing file volume path
    disk_size_gb: int


@dataclass(frozen=True)
class DesiredVirtualMachine:
    lease_id: LeaseID
    domain_uuid: DomainUUID
    vcpus: int
    ram_mb: int
    target_state: DesiredVmState
    instructions: str | None
    networks: tuple[DesiredNetworkInterface, ...] = field(default_factory=tuple)
    disks: tuple[DesiredDisk, ...] = field(default_factory=tuple)
