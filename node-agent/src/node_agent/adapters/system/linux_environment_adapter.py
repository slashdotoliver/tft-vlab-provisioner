import os
import platform
import socket

from returns.result import Result

from node_agent.application.ports.enviroment_provider import SystemEnvironmentPort
from node_agent.domain.attempt import attempt
from node_agent.domain.model.entities import Node, NodeID


def get_linux_hardware_node(node_id: str) -> Node:
    hostname = socket.gethostname()
    cpus = os.cpu_count() or 1

    page_size = os.sysconf("SC_PAGE_SIZE")
    phys_pages = os.sysconf("SC_PHYS_PAGES")
    ram_mb = (page_size * phys_pages) // (1024 * 1024)

    return Node(node_id=NodeID(node_id), hostname=hostname, total_cpus=cpus, total_ram_mb=ram_mb)


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
