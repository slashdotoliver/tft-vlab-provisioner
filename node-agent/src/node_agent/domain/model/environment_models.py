from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from node_agent.domain.model.result import Result


class EnvironmentCheckError(Exception): ...


@dataclass
class ValidationReport:
    issues: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return len(self.issues) == 0

    def add_issue(self, issue: str) -> None:
        self.issues.append(issue)


ValidationStepResult: TypeAlias = Result[str | None, EnvironmentCheckError]
"""
Represents the outcome of a single environment requirement check.
    - Success(None): The requirement is fully met.
    - Success(str): The requirement is NOT met. The string contains the validation issue.
    - Failure(EnvironmentCheckError): The system failed/crashed while trying to perform the check.
"""


@dataclass
class EnvironmentConfig:
    required_arch: str = "x86_64"
    requires_hw_virtualization: bool = True
    requires_nested_virtualization: bool = True
    required_guest_support: list[GuestSupport] = None
    required_pool_support: list[PoolSupport] = None

    def __post_init__(self):
        if self.required_guest_support is None:
            self.required_guest_support = [GuestSupport("hvm", "x86_64", "kvm")]
        if self.required_pool_support is None:
            self.required_pool_support = [PoolSupport("netfs", {"nfs"}, {"qcow2"})]


@dataclass(frozen=True)
class GuestSupport:
    os_type: Literal["hvm", "exe", "xen"]
    arch: str
    emulator: Literal["kvm", "qemu"]


@dataclass(frozen=True)
class PoolSupport:
    pool_type: str
    source_formats: set[str]
    target_formats: set[str]


@dataclass(frozen=True)
class PoolCapability:
    pool_type: str
    supported: bool
    source_formats: set[str]
    target_formats: set[str]


@dataclass(frozen=True)
class NetFSPoolConfig:
    name: str = "vms"
    source_host: str = "localhost"
    source_dir: str = "/export/vms"
    target_path: str = "/var/lib/libvirt/images/vms"
    is_readonly: bool = False

@dataclass(frozen=True)
class NetworkConfig:
    name: str
    mode: Literal["nat", "bridge"]
    bridge_name: str

    # only in 'nat' mode
    ip_address: str | None = None
    netmask: str | None = None
    dhcp_start: str | None = None
    dhcp_end: str | None = None
