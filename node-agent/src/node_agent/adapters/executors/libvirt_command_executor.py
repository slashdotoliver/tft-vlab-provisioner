import logging

import libvirt

from node_agent.application.commands.vm_commands import CreateVMCommand, StartVMCommand, StopVMCommand, VMCommand
from node_agent.application.ports.virtualization_command_executor import VirtualizationCommandExecutor
from node_agent.domain.attempt import attempt
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)


class LibvirtCommandExecutor(VirtualizationCommandExecutor):

    def __init__(self, connection: libvirt.virConnect):
        self._connection = connection

    def execute_all(self, commands: list[VMCommand]) -> Result[None, Exception]:
        error: Exception | None = None
        for command in commands:
            result = attempt(lambda: self._execute_single(command), exceptions=(Exception,))
            if result.is_failure():
                error = result.get_error()
                LOGGER.error(f"Error while executing {type(command).__name__}: {error}")
                break
        return Result.success(None) if error is None else Result.failure(error)

    def _execute_single(self, command: VMCommand) -> None:
        if isinstance(command, CreateVMCommand):
            LOGGER.info(f"Creando VM {command.vm_spec.domain_uuid}...")

        elif isinstance(command, StartVMCommand):
            LOGGER.info(f"Arrancando VM {command.domain_uuid}...")

        elif isinstance(command, StopVMCommand):
            LOGGER.info(f"Deteniendo VM {command.domain_uuid}...")
