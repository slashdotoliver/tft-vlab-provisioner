from dataclasses import dataclass, field
from typing import Literal, NewType
from uuid import UUID

DomainUUID = NewType("DomainUUID", UUID)
LeaseID = NewType("LeaseID", UUID)
NodeID = NewType("NodeID", str)


@dataclass(frozen=True)
class Volume:
    name: str
    pool_name: str # TODO: replace for path?
    capacity_bytes: int
    path: str


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


@dataclass(frozen=True)
class VirtualMachine:
    uuid: DomainUUID
    name: str
    state: Literal["running", "paused", "shutoff", "crashed"] # TODO: check libvirt docs and type_adapters
    vcpus: int
    memory_kb: int
    interfaces: tuple[NetworkInterface, ...] = field(default_factory=tuple)
    volumes: tuple[Volume, ...] = field(default_factory=tuple)
