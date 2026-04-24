from typing import Protocol

from node_agent.application.commands.vm_commands import VMCommand
from node_agent.domain.model.result import Result


class VirtualizationCommandExecutor(Protocol):
    def execute_all(self, commands: list[VMCommand]) -> Result[None, Exception]: ...
