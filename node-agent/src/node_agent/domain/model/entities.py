from dataclasses import dataclass, field
from typing import Literal, NewType
from uuid import UUID

DomainUUID = NewType("DomainUUID", UUID)
LeaseID = NewType("LeaseID", UUID)
NodeID = NewType("NodeID", str)


@dataclass(frozen=True)
class Node:
    node_id: str
    hostname: str
    total_cpus: int
    total_ram_mb: int
    is_active: bool = field(default=True)


@dataclass(frozen=True)
class Volume:
    name: str
    pool_name: str  # TODO: replace for path?
    capacity_bytes: int
    path: str


@dataclass(frozen=True)
class Disk:
    target_dev: str
    volume_path: str
    backing_file: str | None


@dataclass(frozen=True)
class StoragePool:
    uuid: str
    name: str
    state: Literal["active", "inactive"]
    available_bytes: int


@dataclass(frozen=True)
class NetworkInterface:
    mac_address: str
    network_name: str
    bridge_name: str
    ip_address: str | None


@dataclass(frozen=True)
class VirtualMachine:
    uuid: DomainUUID
    name: str
    state: Literal["running", "paused", "shutoff", "crashed", "unknown"]
    is_persistent: bool
    vcpus: int
    memory_kb: int
    interfaces: tuple[NetworkInterface, ...] = field(default_factory=tuple)
    disks: tuple[Disk, ...] = field(default_factory=tuple)
