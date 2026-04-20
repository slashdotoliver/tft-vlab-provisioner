import logging

from node_agent.application.ports.enviroment_provider import LibvirtEnvironmentPort, SystemEnvironmentPort
from node_agent.domain.model.environment_models import (
    EnvironmentCheckError,
    EnvironmentConfig,
    GuestSupport,
    PoolCapability,
    PoolSupport,
    ValidationReport,
    ValidationStepResult,
)
from node_agent.domain.model.result import Failure, Result


class EnvironmentValidator:
    LOGGER = logging.getLogger(__name__)

    def __init__(self, sys_port: SystemEnvironmentPort, libvirt_port: LibvirtEnvironmentPort):
        self.sys_port = sys_port
        self.libvirt_port = libvirt_port

    def validate_environment(self, config: EnvironmentConfig) -> Result[ValidationReport, EnvironmentCheckError]:
        def _report_failure_of(
            step: ValidationStepResult, rep: ValidationReport
        ) -> None | Failure[EnvironmentCheckError]:
            if step.is_failure():
                return Result.failure(step.get_error())
            if issue := step.value_or(None):
                rep.add_issue(issue)
            return None

        self.LOGGER.debug("Starting environment validation...")
        report = ValidationReport()

        for validation_step in [
            # system
            lambda: self._check_architecture(config.required_arch),
            lambda: self._check_hw_virt() if config.requires_hw_virtualization else Result.success(None),
            lambda: self._check_nested_virt() if config.requires_nested_virtualization else Result.success(None),
            lambda: self._check_selinux_nfs(),
            # libvirt
            lambda: self._check_libvirt_presence(),
            lambda: self._check_libvirt_guest_capabilities(config.required_guest_support),
            lambda: self._check_libvirt_pool_capabilities(config.required_pool_support),
        ]:
            step_failure: Failure[EnvironmentCheckError] | None = _report_failure_of(validation_step(), report)
            if step_failure is not None:
                return step_failure

        self.LOGGER.debug("Environment validation finished")
        return Result.success(report)

    def _check_architecture(self, required: str) -> ValidationStepResult:
        res = self.sys_port.get_architecture()
        if res.is_failure():
            return Result.failure(EnvironmentCheckError(f"System error reading arch: {res.get_error()}"))

        found_arch = res.value_or("")
        if found_arch != required:
            return Result.success(f"Architecture mismatch: required '{required}', found '{found_arch}'.")
        return Result.success(None)

    def _check_hw_virt(self) -> ValidationStepResult:
        res = self.sys_port.check_hw_virtualization()
        if res.is_failure():
            return Result.failure(
                EnvironmentCheckError(f"System error checking hardware virtualization support: {res.get_error()}")
            )

        if not res.value_or(False):
            return Result.success("Hardware virtualization is not supported or disabled in BIOS.")
        return Result.success(None)

    def _check_nested_virt(self) -> ValidationStepResult:
        res = self.sys_port.check_nested_virtualization()
        if res.is_failure():
            return Result.failure(EnvironmentCheckError(f"System error checking nested virt: {res.get_error()}"))

        if not res.value_or(False):
            return Result.success("Nested virtualization is required but disabled in kernel modules.")
        return Result.success(None)

    def _check_selinux_nfs(self) -> ValidationStepResult:
        active_res = self.sys_port.check_selinux_active()
        if active_res.is_failure():
            return Result.failure(
                EnvironmentCheckError(f"System error checking SELinux state: {active_res.get_error()}")
            )

        if active_res.value_or(False):
            nfs_res = self.sys_port.check_selinux_nfs()
            if nfs_res.is_failure():
                return Result.failure(
                    EnvironmentCheckError(f"System error reading virt_use_nfs boolean: {nfs_res.get_error()}")
                )

            if not nfs_res.value_or(False):
                return Result.success("SELinux is enforcing but 'virt_use_nfs' is set to off. Cannot mount NFS.")
        return Result.success(None)

    def _check_libvirt_presence(self) -> ValidationStepResult:
        res = self.libvirt_port.check_presence()
        if res.is_failure():
            return Result.failure(EnvironmentCheckError(f"Libvirt connection error: {res.get_error()}"))

        if not res.value_or(False):
            return Result.success("Libvirt daemon is not responding or not installed.")
        return Result.success(None)

    def _check_libvirt_guest_capabilities(self, required_guest_support: list[GuestSupport]) -> ValidationStepResult:
        res = self.libvirt_port.get_guest_capabilities()
        if res.is_failure():
            return Result.failure(
                EnvironmentCheckError(f"Failed to fetch libvirt guest capabilities: {res.get_error()}")
            )

        supported = res.value_or([])
        missing = [supported_guest for supported_guest in required_guest_support if supported_guest not in supported]
        if missing:
            return Result.success(
                f"Missing required guest support: {', '.join(map(lambda m: str(m), missing))}. Available: {
                    ', '.join(map(lambda s: str(s), supported))
                }"
            )
        return Result.success(None)

    def _check_libvirt_pool_capabilities(self, required_pool_support: list[PoolSupport]) -> ValidationStepResult:
        def _get_missing_details(required: PoolSupport) -> str | None:
            supported_pool_cap: PoolCapability | None = supported_map.get(required.pool_type)
            if not supported_pool_cap:
                return f"'{required.pool_type}' (missing pool type)"
            supported_pool: PoolSupport = PoolSupport(
                supported_pool_cap.pool_type, supported_pool_cap.source_formats, supported_pool_cap.target_formats
            )
            missing_sources = set(required.source_formats) - set(supported_pool.source_formats)
            missing_targets = set(required.target_formats) - set(supported_pool.target_formats)

            if not missing_sources and not missing_targets:
                return None
            errs = [
                f"{k}: {', '.join(v)}" for k, v in [("sources", missing_sources), ("targets", missing_targets)] if v
            ]
            return f"'{required.pool_type}' missing {', and '.join(errs)}"

        res = self.libvirt_port.get_pool_capabilities()
        if res.is_failure():
            return Result.failure(
                EnvironmentCheckError(f"Failed to fetch storage pool capabilities: {res.get_error()}")
            )

        supported_map: dict[str, PoolCapability] = {
            capability.pool_type: capability for capability in res.value_or([]) if capability.supported is True
        }
        missing = [detail for req in required_pool_support if (detail := _get_missing_details(req))]
        if missing:
            return Result.success(f"Missing required pool support: {'; '.join(missing)}")
        return Result.success(None)
