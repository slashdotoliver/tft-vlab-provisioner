import logging
from typing import Literal
from uuid import UUID
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from libvirt import (
    VIR_DOMAIN_CRASHED,
    VIR_DOMAIN_PAUSED,
    VIR_DOMAIN_RUNNING,
    VIR_DOMAIN_SHUTDOWN,
    VIR_DOMAIN_SHUTOFF,
    libvirtError,
    virConnect,
    virDomain,
)

from node_agent.application.ports.virtualization_state_provider import VirtualizationStatePort
from node_agent.domain.attempt import attempt, raises
from node_agent.domain.model.entities import Disk, DomainUUID, NetworkInterface, VirtualMachine
from node_agent.domain.model.result import Result

LOGGER = logging.getLogger(__name__)


class ParseError(Exception): ...


class LibvirtStateAdapter(VirtualizationStatePort):
    def __init__(self, connection: virConnect):
        self._connection = connection

    def get_actual_vms(self) -> Result[list[VirtualMachine], Exception]:
        @raises(ParseError)
        def _parse_xml(
            root: Element[str],
        ) -> tuple[int, int, tuple[NetworkInterface, ...], tuple[Disk, ...]]:
            vcpus = self._parse_vcpus(root)
            memory_kb = self._parse_memory(root)
            interfaces = self._parse_interfaces(root)
            disks = self._parse_disks(root)
            return vcpus, memory_kb, interfaces, disks

        @raises(libvirtError, ParseError)
        def _fetch_state() -> list[VirtualMachine]:
            actual_vms = []
            domains: list[virDomain] = self._connection.listAllDomains(0)

            for domain in domains:
                dom_uuid = UUID(domain.UUIDString())
                dom_name = domain.name()
                is_persistent = domain.isPersistent() == 1
                # noinspection PyTypeChecker
                state_info: list[int] = domain.state()
                actual_state = self._map_libvirt_state(state_info[0])

                root = ElementTree.fromstring(domain.XMLDesc(0))
                # TODO: make ParseError raise explicit
                parse_result = _parse_xml(root)
                vcpus, memory_kb, interfaces, disks = parse_result

                actual_vms.append(
                    VirtualMachine(
                        uuid=DomainUUID(dom_uuid),
                        name=dom_name,
                        state=actual_state,
                        is_persistent=is_persistent,
                        vcpus=vcpus,
                        memory_kb=memory_kb,
                        interfaces=interfaces,
                        disks=disks,
                    )
                )
            return actual_vms

        return attempt(_fetch_state)

    def _map_libvirt_state(self, libvirt_state: int) -> Literal["running", "paused", "shutoff", "crashed", "unknown"]:
        if libvirt_state == VIR_DOMAIN_RUNNING:
            return "running"
        elif libvirt_state == VIR_DOMAIN_PAUSED:
            return "paused"
        elif libvirt_state in (VIR_DOMAIN_SHUTOFF, VIR_DOMAIN_SHUTDOWN):
            return "shutoff"
        elif libvirt_state == VIR_DOMAIN_CRASHED:
            return "crashed"
        return "unknown"

    @raises(ParseError)
    def _parse_vcpus(self, root: ElementTree.Element) -> int:
        vcpu_elem = root.find("./vcpu")
        if vcpu_elem is not None and vcpu_elem.text:
            return int(vcpu_elem.text)
        raise ParseError(f"Error while parsing vcpus: {vcpu_elem.text}")

    @raises(ParseError)
    def _parse_memory(self, root: ElementTree.Element) -> int:
        mem_elem = root.find("./memory")
        if mem_elem is not None and mem_elem.text:
            return int(mem_elem.text)
        raise ParseError(f"Error while parsing memory: {mem_elem.text}")

    def _parse_interfaces(self, root: ElementTree.Element) -> tuple[NetworkInterface, ...]:
        interfaces = []
        for iface in root.findall("./devices/interface"):
            mac_elem = iface.find("./mac")
            mac_address = mac_elem.get("address") if mac_elem is not None else ""
            source_elem = iface.find("./source")
            network_name = source_elem.get("network") if source_elem is not None else ""
            bridge_name = source_elem.get("bridge") if source_elem is not None else ""
            ip_elem = iface.find("./ip")
            ip_address = ip_elem.get("address") if ip_elem is not None else None

            interfaces.append(
                NetworkInterface(
                    mac_address=mac_address,
                    network_name=network_name,
                    bridge_name=bridge_name,
                    ip_address=ip_address,
                )
            )

        return tuple(interfaces)

    def _parse_disks(self, root: ElementTree.Element) -> tuple[Disk, ...]:
        disks = []
        for disk in root.findall("./devices/disk"):
            if disk.get("device") == "disk":
                target_elem = disk.find("./target")
                target_dev = target_elem.get("dev") if target_elem is not None else ""
                source_elem = disk.find("./source")
                source_file = source_elem.get("file") if source_elem is not None else ""
                backing_elem = disk.find("./backingStore/source")
                backing_file = backing_elem.get("file") if backing_elem is not None else None

                disks.append(
                    Disk(
                        target_dev=target_dev,
                        volume_path=source_file,
                        backing_file=backing_file,
                    )
                )

        return tuple(disks)
