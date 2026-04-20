from dataclasses import dataclass, field
from typing import TypeAlias, Literal

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
    requires_hw_virt: bool = True
    requires_nested_virt: bool = True
    required_guest_support: list[GuestSupport] = None
    required_pool_support: list[PoolSupport] = None

    def __post_init__(self):
        if self.required_guest_support is None:
            self.required_guest_support = [
                GuestSupport("hvm", "x86_64", "kvm")
            ]
        if self.required_pool_support is None:
            self.required_pool_support = [
                PoolSupport("netfs", {"nfs"}, {"qcow2"})
            ]


@dataclass(frozen=True)
class GuestSupport:
    os_type: Literal['hvm', 'exe', 'xen']
    arch: str
    emulator: Literal['kvm', 'qemu']


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
