import logging

from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.application.ports.virtualization_state_provider import VirtualizationStatePort
from node_agent.domain.model.desired_state_entities import DesiredVirtualMachine, DesiredVmState, LeaseStateUpdate
from node_agent.domain.model.entities import NodeID, VirtualMachine
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)


class ReportNodeStatusUseCase:
    def __init__(self, db_port: DesiredStatePort, state_port: VirtualizationStatePort, node_id: NodeID):
        self.db_port = db_port
        self.state_port = state_port
        self.node_id = node_id

    def report(self, desired_vms: list[DesiredVirtualMachine]) -> Result[None, Exception]:
        def _report_error_while_updating_status(error: Exception) -> Result[None, Exception]:
            LOGGER.error(f"Error while reporting node status: {error}")
            return Result.failure(error)

        actual_vms_result = self.state_port.get_actual_vms()
        if actual_vms_result.is_failure():
            LOGGER.error(f"Failed to fetch actual state for reporting: {actual_vms_result.get_error()}")
            return Result.failure(actual_vms_result.get_error())

        actual_vms = actual_vms_result.value_or([])
        actual_map = {vm.uuid: vm for vm in actual_vms}

        updates: list[LeaseStateUpdate] = []
        # TODO: report only updates that change values
        for desired in desired_vms:
            actual: VirtualMachine | None = actual_map.get(desired.domain_uuid, None)
            lease_actual_state = self._map_to_lease_actual_state(desired, actual)

            mac_to_ip_map: dict[str, str | None] = (
                {interface.mac_address: interface.ip_address for interface in actual.interfaces if interface.ip_address}
                if actual
                else dict()
            )
            updates.append(
                LeaseStateUpdate(
                    lease_id=desired.lease_id, actual_state=lease_actual_state, mac_to_ip_map=mac_to_ip_map
                )
            )

        return self.db_port.report_node_status(self.node_id, updates).flat_map_error(
            _report_error_while_updating_status
        )

    def _map_to_lease_actual_state(self, desired: DesiredVirtualMachine, actual: VirtualMachine | None) -> str:
        # TODO: add "terminated_by_user" and "error" states

        if desired.target_state == DesiredVmState.ABSENT:
            if actual is None:
                return "terminated"
            else:
                return "terminating"

        if desired.target_state == DesiredVmState.RUNNING:
            if actual is None:
                return "pending"
            if actual.state == "running":
                return "running"
            return "starting"

        if desired.target_state == DesiredVmState.SHUTOFF:
            if actual and actual.state == "shutoff":
                return "paused"
            return "terminating"

        return "unknown"
