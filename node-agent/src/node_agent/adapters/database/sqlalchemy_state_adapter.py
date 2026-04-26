import logging
from datetime import timedelta
from typing import Sequence
from uuid import UUID

from sqlalchemy import Executable, Row, func, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from node_agent.adapters.database.sqlalchemy_models import (
    LeaseDiskModel,
    LeaseModel,
    TemplateModel,
)
from node_agent.application.ports.desired_state_provider import DesiredStatePort
from node_agent.domain.model.desired_state_entities import (
    DesiredDisk,
    DesiredNetworkInterface,
    DesiredVirtualMachine,
    DesiredVmState,
)
from node_agent.domain.model.entities import DomainUUID, LeaseID, NodeID

LOGGER = logging.getLogger(__name__)


class SqlAlchemyStateAdapter(DesiredStatePort):
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def get_desired_vms_for_node(self, node_id: NodeID) -> list[DesiredVirtualMachine]:
        with self.session_factory() as session:
            results = self._leases_for_node(node_id, session, timedelta(days=1), timedelta(hours=8))

            desired_vms = []
            for lease, is_active_time in results:
                lease: LeaseModel
                is_active_time: bool

                is_valid_and_active = (lease.lease_status == "active") and is_active_time

                desired_vm = self._get_lease_vm(
                    self._get_lease_disks(lease),
                    self._get_lease_networks(lease),
                    self._get_desired_vm_state(is_valid_and_active, lease),
                    lease,
                )
                desired_vms.append(desired_vm)
                LOGGER.warning(f"Desired VM: {desired_vm}")
            return desired_vms

    def _leases_for_node(
        self, node_id: NodeID, session: Session, before_search_window: timedelta, after_search_window: timedelta
    ) -> Sequence[Row[tuple[LeaseModel, bool]]]:
        is_in_time_range = (func.now().op("<@")(LeaseModel.time_range)).label("is_active_time")
        search_window = func.tstzrange(
            func.now() - before_search_window,
            func.now() + after_search_window,
            "[]",
        )

        stmt: Executable = (
            select(LeaseModel, is_in_time_range)
            .options(
                joinedload(LeaseModel.template).joinedload(TemplateModel.network_interfaces),
                joinedload(LeaseModel.interfaces),
                joinedload(LeaseModel.disks).joinedload(LeaseDiskModel.template_disk),
            )
            .where(LeaseModel.node_id == str(node_id))
            .where(LeaseModel.time_range.op("&&")(search_window))
        )
        return session.execute(stmt).unique().all()

    def _get_lease_vm(
        self,
        disks: list[DesiredDisk],
        networks: list[DesiredNetworkInterface],
        target_state: DesiredVmState,
        lease: LeaseModel,
    ) -> DesiredVirtualMachine:
        return DesiredVirtualMachine(
            lease_id=LeaseID(lease.id),
            domain_uuid=DomainUUID(lease.domain_uuid),
            vcpus=lease.template.vcpus,
            ram_mb=lease.template.ram_mb,
            target_state=target_state,
            instructions=lease.instructions,
            disks=tuple(disks),
            networks=tuple(networks),
        )

    def _get_desired_vm_state(self, is_valid_and_active: bool, lease: LeaseModel) -> DesiredVmState:
        target_state: DesiredVmState = DesiredVmState.ABSENT
        if is_valid_and_active:
            target_state = DesiredVmState.RUNNING
        elif lease.is_permanent:
            target_state = DesiredVmState.SHUTOFF
        return target_state

    def _get_lease_disks(self, lease: LeaseModel) -> list[DesiredDisk]:
        disks = []
        for disk in lease.disks:
            td = disk.template_disk
            disks.append(
                DesiredDisk(
                    target_dev=disk.target_dev,
                    volume_path=disk.volume_path,
                    disk_driver=td.disk_driver if td else "",
                    disk_subdriver=td.disk_subdriver if td else "",
                    target_bus=td.target_bus if td else "",
                    base_volume_path=td.base_volume_path if td else "",
                    disk_size_gb=td.disk_size_gb if td else 0,
                )
            )
        return disks

    def _get_lease_networks(self, lease: LeaseModel) -> list[DesiredNetworkInterface]:
        networks = []
        for interface in lease.interfaces:
            networks.append(
                DesiredNetworkInterface(
                    mac_address=interface.mac_address,
                    network_type=interface.template_interface.network_type,
                    bridge_name=interface.template_interface.bridge_name,
                    model_type=interface.template_interface.model_type,
                )
            )
        return networks

    def report_actual_state(self, lease_id: LeaseID, state: str) -> None:
        with self.session_factory() as session:
            lease: LeaseModel | None = session.get(LeaseModel, lease_id)
            if not lease:
                LOGGER.warning("Trying to report vm state for a lease not found in database")
                return

            if lease.actual_state == state:
                return

            lease.actual_state = state
            session.commit()
