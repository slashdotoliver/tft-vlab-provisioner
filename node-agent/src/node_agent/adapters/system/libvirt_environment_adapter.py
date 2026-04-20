import logging
from typing import Callable, TypeVar
from xml.etree import ElementTree

import libvirt

from node_agent.application.ports.enviroment_provider import LibvirtEnvironmentPort
from node_agent.domain.attempt import attempt
from node_agent.domain.model.environment_models import GuestSupport, PoolCapability
from node_agent.domain.model.result import Result

T = TypeVar("T")


class LibvirtEnvironmentAdapter(LibvirtEnvironmentPort):
    LOGGER = logging.getLogger(__name__)

    def __init__(self, uri: str = "qemu:///system"):
        self.uri = uri

    def _execute_with_connection(self, operation: Callable[[libvirt.virConnect], T]) -> Result[T, Exception]:
        def _runner() -> T:
            conn = libvirt.openReadOnly(self.uri)
            try:
                return operation(conn)
            finally:
                conn.close()

        return attempt(_runner, (Exception,))

    def check_presence(self) -> Result[bool, Exception]:
        return Result.success(self._execute_with_connection(lambda conn: True).value_or(False))

    def get_guest_capabilities(self) -> Result[list[GuestSupport], Exception]:
        def _extract_capabilities(conn: libvirt.virConnect) -> list[GuestSupport]:
            root = ElementTree.fromstring(conn.getCapabilities())

            supported_guests = set()

            for guest in root.findall("guest"):
                os_type_elem = guest.find("os_type")
                os_type = os_type_elem.text if os_type_elem is not None else "unknown"

                arch_elem = guest.find("arch")
                if arch_elem is not None:
                    arch_name = arch_elem.get("name", "unknown")

                    for domain in arch_elem.findall(".//domain"):
                        domain_type = domain.get("type")
                        if domain_type:
                            supported_guests.add((os_type, arch_name, domain_type))

            return list(map(lambda supported_guest: GuestSupport(*supported_guest), supported_guests))

        return self._execute_with_connection(_extract_capabilities)

    def get_pool_capabilities(self) -> Result[list[PoolCapability], Exception]:
        def _extract_capabilities(conn: libvirt.virConnect) -> list[PoolCapability]:
            root = ElementTree.fromstring(conn.getStoragePoolCapabilities())

            pools = []

            for pool in root.findall("pool"):
                pool_type = pool.get("type") or "unknown"
                supported = pool.get("supported") == "yes"
                source_formats: set[str] = set()
                src_enum = pool.find(".//poolOptions/enum[@name='sourceFormatType']")
                if src_enum is not None:
                    source_formats = {val.text for val in src_enum.findall("value") if val.text}
                target_formats: set[str] = set()
                vol_enum = pool.find(".//volOptions/enum[@name='targetFormatType']")
                if vol_enum is not None:
                    target_formats = {val.text for val in vol_enum.findall("value") if val.text}

                pools.append(
                    PoolCapability(
                        pool_type=pool_type,
                        supported=supported,
                        source_formats=source_formats,
                        target_formats=target_formats,
                    )
                )
            return pools

        return self._execute_with_connection(_extract_capabilities)
