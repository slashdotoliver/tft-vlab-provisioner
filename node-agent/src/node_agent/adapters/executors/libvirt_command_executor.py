import logging
from functools import singledispatchmethod
from pathlib import Path

from libvirt import libvirtError, virConnect, virStorageVol

from node_agent.application.commands.vm_commands import (
    CreateVMCommand,
    DestroyVMCommand,
    StartVMCommand,
    StopVMCommand,
    VMCommand,
)
from node_agent.application.ports.virtualization_command_executor import VirtualizationCommandExecutor
from node_agent.domain.attempt import attempt, raises
from node_agent.domain.model.desired_state_entities import DesiredDisk, DesiredVirtualMachine
from node_agent.domain.model.environment_models import NetFSPoolConfig
from node_agent.domain.model.result import Result
from node_agent.templates.domain_xml import render_domain_xml
from node_agent.templates.volume_xml import render_volume_xml

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
        @raises(libvirtError)
        def _start() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            if not dom.isActive():
                dom.create()

        LOGGER.info(f"Starting VM {command.domain_uuid}...")
        return attempt(_start)

    @_execute_single.register
    def _(self, command: StopVMCommand) -> Result[None, Exception]:
        @raises(libvirtError)
        def _stop() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            if dom.isActive():
                dom.destroy()  # TODO: Use dom.shutdown() for graceful ACPI shutdown.

        LOGGER.info(f"Stopping VM {command.domain_uuid}...")
        return attempt(_stop)

    @_execute_single.register
    def _(self, command: DestroyVMCommand) -> Result[None, Exception]:
        @raises(libvirtError)
        def _undefine() -> None:
            dom = self._connection.lookupByUUIDString(str(command.domain_uuid))
            dom.undefine()

        @raises(libvirtError)
        def _try_delete_volume(disk: DesiredDisk) -> None:
            volume_file_path: Path = self._vms_path / disk.volume_name

            if not volume_file_path.exists():
                LOGGER.warning(f"Volume {volume_file_path} does not exist. Skipping deletion of volume")
                return

            vol: virStorageVol = self._connection.storageVolLookupByPath(str(volume_file_path))
            vol.delete()

        LOGGER.info(f"Destroying VM (undefine) {command.domain_uuid}...")
        return (
            attempt(_undefine)
            .flat_map(
                lambda _: attempt(lambda: [_try_delete_volume(disk) for disk in command.disks_to_delete]).on_failure(
                    lambda error: LOGGER.warning(f"Failed to delete volume: {error}")
                )
            )
            .map(lambda _: None)
        )

    def _create_disks(self, disks: tuple[DesiredDisk, ...]) -> Result[None, Exception]:
        """Creates the copy-on-write (COW) disks using qemu-img."""
        for disk in disks:
            if not disk.base_volume_name:
                return Result.failure(
                    Exception("Error while creating volumes: Found a disk definition without base volume path")
                )

            @raises(libvirtError)
            def _run_qemu_img() -> None:
                volume_file_path: Path = self._vms_path / disk.volume_name
                backing_vol_path: Path = self._bases_path / disk.base_volume_name

                if volume_file_path.exists():
                    LOGGER.debug(f"Volume {volume_file_path} already exists. Skipping creating volume")
                    return

                pool = self._connection.storagePoolLookupByTargetPath(str(self._vms_path))
                backing_vol: virStorageVol = self._connection.storageVolLookupByPath(str(backing_vol_path))

                # noinspection PyTypeChecker
                capacity_bytes: int = backing_vol.info()[1]
                assert capacity_bytes == disk.disk_size_gb * 2**30

                _: virStorageVol = pool.createXML(
                    render_volume_xml(config=disk, vms_pool_path=self._vms_path, bases_pool_path=self._bases_path),
                )

            LOGGER.debug(f"Creating COW disk {disk.volume_name} backed by {disk.base_volume_name}")
            res: Result[None, Exception] = attempt(_run_qemu_img)

            if res.is_failure():
                return res.flat_map_error(
                    lambda e: Result.failure(Exception(f"Failed creating volume {disk.volume_name}: {e}"))
                )
        return Result.success(None)

    def _define_domain(self, vm_spec: DesiredVirtualMachine) -> Result[None, Exception]:
        """Defines the domain in libvirt."""

        @raises(libvirtError, Exception)
        def _do_define() -> None:
            # TODO: add more emulators
            dom = self._connection.defineXML(
                render_domain_xml(vm_spec, self._bases_path, self._vms_path, emulator_path=None)
            )
            if dom is None:
                raise libvirtError(f"Libvirt returned None defining {vm_spec.domain_uuid}")

        LOGGER.debug(f"Defining XML for VM {vm_spec.domain_uuid}...")
        return attempt(_do_define)
