import logging
import subprocess
from functools import singledispatchmethod
from pathlib import Path

from libvirt import libvirtError, virConnect

from node_agent.application.commands.vm_commands import (
    CreateVMCommand,
    DestroyVMCommand,
    StartVMCommand,
    StopVMCommand,
    VMCommand,
)
from node_agent.application.ports.virtualization_command_executor import VirtualizationCommandExecutor
from node_agent.domain.attempt import attempt
from node_agent.domain.model.desired_state_entities import DesiredDisk, DesiredVirtualMachine
from node_agent.domain.model.environment_models import NetFSPoolConfig
from node_agent.domain.model.result import Result
from node_agent.templates.domain_xml import render_domain_xml

LOGGER = logging.getLogger(__name__)


class LibvirtCommandExecutor(VirtualizationCommandExecutor):
    """Receives commands and executes the actual actions in libvirt."""

    def __init__(self, connection: virConnect, bases_pool: NetFSPoolConfig, vms_pool: NetFSPoolConfig):
        self._connection = connection
        self._bases_path = Path(bases_pool.target_path)
        self._vms_path = Path(vms_pool.target_path)

    def execute_all(self, commands: list[VMCommand]) -> Result[None, Exception]:
        """Executes a list of commands sequentially.
        Fails fast: stops execution and returns the error if any command fails.
        """
        for command in commands:
            result = self._execute_single(command)
            if result.is_failure():
                # LOGGER.error(f"Error while executing {type(command).__name__}: {result.get_error()}")
                return result
        return Result.success(None)

    @singledispatchmethod
    def _execute_single(self, command: VMCommand) -> Result[None, Exception]:
        """Fallback method if an unknown command type is passed."""
        return Result.failure(NotImplementedError(f"Handler for {type(command)} not implemented"))

    @_execute_single.register
    def _(self, command: CreateVMCommand) -> Result[None, Exception]:
        LOGGER.info(f"Creating VM {command.vm_spec.domain_uuid}...")
        return self._create_disks(command.vm_spec.disks).flat_map(lambda _: self._define_domain(command.vm_spec))

    @_execute_single.register
    def _(self, command: StartVMCommand) -> Result[None, Exception]:
        def _start() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            if not dom.isActive():
                dom.create()

        LOGGER.info(f"Starting VM {command.domain_uuid}...")
        return attempt(_start, exceptions=(libvirtError,))

    @_execute_single.register
    def _(self, command: StopVMCommand) -> Result[None, Exception]:
        def _stop() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            if dom.isActive():
                dom.destroy()  # TODO: Use dom.shutdown() for graceful ACPI shutdown.

        LOGGER.info(f"Stopping VM {command.domain_uuid}...")
        return attempt(_stop, exceptions=(libvirtError,))

    @_execute_single.register
    def _(self, command: DestroyVMCommand) -> Result[None, Exception]:
        def _undefine() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            dom.undefine()
            # FIXME: We should probably also delete the copy-on-write disks from the filesystem
            #  here using os.remove() or another subprocess call.

        LOGGER.info(f"Destroying VM (undefine) {command.domain_uuid}...")
        return attempt(_undefine, exceptions=(libvirtError,))

    def _create_disks(self, disks: tuple[DesiredDisk, ...]) -> Result[None, Exception]:
        """Creates the copy-on-write (COW) disks using qemu-img."""
        for disk in disks:
            if not disk.base_volume_path:
                return Result.failure(
                    Exception("Error while creating volumes: Found a disk definition without base volume path")
                )

            def _run_qemu_img() -> None:
                volume_file_path: Path = self._vms_path / disk.volume_path
                backing_vol_file: str = str(self._bases_path / disk.base_volume_path)
                volume_file: str = str(volume_file_path)

                if volume_file_path.exists():
                    LOGGER.debug(f"Volume {volume_file} already exists. Skipping creating volume")
                    return

                # TODO: intentarlo con virsh vol-create-as
                # qemu-img create -f qcow2 -F qcow2 -b <backing_file> <target_file>
                subprocess.run(
                    [
                        "qemu-img",
                        "create",
                        "-f",
                        disk.disk_subdriver,
                        "-F",
                        disk.disk_subdriver,
                        "-b",
                        backing_vol_file,
                        volume_file,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            LOGGER.debug(f"Creating COW disk {disk.volume_path} backed by {disk.base_volume_path}")
            res: Result[None, Exception] = attempt(_run_qemu_img, exceptions=(subprocess.CalledProcessError, Exception))
            if res.is_failure():
                return res.map_error(
                    lambda e: Result.failure(
                        Exception(
                            f"Failed to create disk {disk.volume_path}: {e}"
                            f"{e.stderr.strip() if isinstance(e, subprocess.CalledProcessError) else str(e)}"
                        )
                    )
                )
        return Result.success(None)

    def _define_domain(self, vm_spec: DesiredVirtualMachine) -> Result[None, Exception]:
        """Defines the domain in libvirt."""

        def _do_define() -> None:
            # TODO: add more emulators
            dom = self._connection.defineXML(
                render_domain_xml(vm_spec, self._bases_path, self._vms_path, emulator_path=None)
            )
            if dom is None:
                raise libvirtError(f"Libvirt returned None defining {vm_spec.domain_uuid}")

        LOGGER.debug(f"Defining XML for VM {vm_spec.domain_uuid}...")
        return attempt(_do_define, exceptions=(libvirtError, Exception))
