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

LOGGER = logging.getLogger(__name__)


class EnvironmentValidator:
    def __init__(self, sys_port: SystemEnvironmentPort, libvirt_port: LibvirtEnvironmentPort):
        self.sys_port = sys_port
        self.libvirt_port = libvirt_port

    def validate_environment(self, config: EnvironmentConfig) -> Result[ValidationReport, EnvironmentCheckError]:
        def _report_failure_of(
            step_result: ValidationStepResult, rep: ValidationReport
        ) -> None | Failure[EnvironmentCheckError]:
            if step_result.is_failure():
                return Result.failure(step_result.get_error())
            if issue := step_result.value_or(None):
                rep.add_issue(issue)
            return None

        LOGGER.debug("Starting environment validation...")
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

        LOGGER.debug("Environment validation finished")
        return Result.success(report)

    def _check_architecture(self, required: str) -> ValidationStepResult:
        return (
            self.sys_port.get_architecture()
            .map_error(lambda error: EnvironmentCheckError(f"System error reading arch: {error}"))
            .map(
                lambda arch: (
                    None if arch == required else f"Architecture mismatch: required '{required}', found '{arch}'."
                )
            )
        )

    def _check_hw_virt(self) -> ValidationStepResult:
        return (
            self.sys_port.check_hw_virtualization()
            .map_error(
                lambda error: EnvironmentCheckError(f"System error checking hardware virtualization support: {error}")
            )
            .map(
                lambda is_supported: (
                    None if is_supported else "Hardware virtualization is not supported or disabled in BIOS."
                )
            )
        )

    def _check_nested_virt(self) -> ValidationStepResult:
        return (
            self.sys_port.check_nested_virtualization()
            .map_error(lambda error: EnvironmentCheckError(f"System error checking nested virt: {error}"))
            .map(
                lambda is_enabled: (
                    None if is_enabled else "Nested virtualization is required but disabled in kernel modules."
                )
            )
        )

    def _check_selinux_nfs(self) -> ValidationStepResult:
        return (
            self.sys_port.check_selinux_active()
            .map_error(lambda e: EnvironmentCheckError(f"System error checking SELinux state: {e}"))
            .flat_map(
                lambda is_active: (
                    (
                        self.sys_port.check_selinux_nfs()
                        .map_error(
                            lambda error: EnvironmentCheckError(f"System error reading virt_use_nfs boolean: {error}")
                        )
                        .map(
                            lambda nfs_enabled: (
                                None
                                if nfs_enabled
                                else "SELinux is enforcing but 'virt_use_nfs' is set to off. Cannot mount NFS."
                            )
                        )
                    )
                    if is_active
                    else Result.success(None)
                )
            )
        )

    def _check_libvirt_presence(self) -> ValidationStepResult:
        return (
            self.libvirt_port.check_presence()
            .map_error(lambda error: EnvironmentCheckError(f"Libvirt connection error: {error}"))
            .map(lambda is_present: None if is_present else "Libvirt daemon is not responding or not installed.")
        )

    def _check_libvirt_guest_capabilities(self, required_guest_support: list[GuestSupport]) -> ValidationStepResult:
        def _find_missing(supported: list[GuestSupport]) -> str | None:
            missing = [guest for guest in required_guest_support if guest not in supported]
            if not missing:
                return None
            return (
                f"Missing required guest support: {', '.join(map(str, missing))}. "
                f"Available: {', '.join(map(str, supported))}"
            )

        return (
            self.libvirt_port.get_guest_capabilities()
            .map_error(lambda error: EnvironmentCheckError(f"Failed to fetch libvirt guest capabilities: {error}"))
            .map(_find_missing)
        )

    def _check_libvirt_pool_capabilities(self, required_pool_support: list[PoolSupport]) -> ValidationStepResult:
        def _find_missing(capabilities: list[PoolCapability]) -> str | None:
            supported_map = {cap.pool_type: cap for cap in capabilities if cap.supported is True}
            missing = [
                detail for req in required_pool_support if (detail := self._get_missing_details(req, supported_map))
            ]
            return f"Missing required pool support: {'; '.join(missing)}" if missing else None

        return (
            self.libvirt_port.get_pool_capabilities()
            .map_error(lambda error: EnvironmentCheckError(f"Failed to fetch storage pool capabilities: {error}"))
            .map(_find_missing)
        )

    @staticmethod
    def _get_missing_details(required: PoolSupport, supported_map: dict[str, PoolCapability]) -> str | None:
        supported_pool_cap: PoolCapability | None = supported_map.get(required.pool_type)
        if not supported_pool_cap:
            return f"'{required.pool_type}' (missing pool type)"

        supported_pool = PoolSupport(
            supported_pool_cap.pool_type, supported_pool_cap.source_formats, supported_pool_cap.target_formats
        )
        missing_sources = set(required.source_formats) - set(supported_pool.source_formats)
        missing_targets = set(required.target_formats) - set(supported_pool.target_formats)

        if not missing_sources and not missing_targets:
            return None

        errs = [f"{k}: {', '.join(v)}" for k, v in [("sources", missing_sources), ("targets", missing_targets)] if v]
        return f"'{required.pool_type}' missing {', and '.join(errs)}"
