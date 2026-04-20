import os
import platform

from returns.result import Result

from node_agent.application.ports.enviroment_provider import SystemEnvironmentPort
from node_agent.domain.attempt import attempt


class LinuxEnvironmentAdapter(SystemEnvironmentPort):
    def get_architecture(self) -> Result[str, Exception]:
        return attempt(platform.machine, (Exception,))

    def check_hw_virtualization(self) -> Result[bool, Exception]:
        def _check() -> bool:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()
                return "vmx" in content or "svm" in content

        return attempt(_check, (Exception,))

    def check_nested_virtualization(self) -> Result[bool, Exception]:
        def _check() -> bool:
            for vendor in ["kvm_intel", "kvm_amd"]:
                path = f"/sys/module/{vendor}/parameters/nested"
                if os.path.exists(path):
                    with open(path, "r") as f:
                        return f.read().strip() in ("Y", "y", "1")
            return False

        return attempt(_check, (Exception,))

    def check_selinux_active(self) -> Result[bool, Exception]:
        def _check() -> bool:
            path = "/sys/fs/selinux/enforce"
            # /enforce contains '1' if Enforcing, '0' if Permissive
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip() == "1"
            return False

        return attempt(_check, (Exception,), lambda e: Exception(f"SELinux check failed: {str(e)}"))

    def check_selinux_nfs(self) -> Result[bool, Exception]:
        def _check() -> bool:
            path = "/sys/fs/selinux/booleans/virt_use_nfs"
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().split() == "1"
            return False

        return attempt(_check, (Exception,), lambda e: Exception(f"SELinux check failed: {str(e)}"))
