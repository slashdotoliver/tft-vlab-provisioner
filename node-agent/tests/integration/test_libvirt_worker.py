import libvirt
import pytest

from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.application.handlers.domain_lifecycle_event_handler import DomainLifecycleEventHandler
from node_agent.application.ports.worker import Worker
from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType


class TestDomainLifecycleEventHandler(DomainLifecycleEventHandler):
    def handle_lifecycle_event(self, name: str, event: DomainEventType, detail) -> None:
        ... # TODO


def test_should_invoke_lifecycle_event():
    libvirt.virEventRegisterDefaultImpl()
    test_conn: libvirt.virConnect | None = libvirt.open('test:///default')
    assert test_conn is not None

    monitor_worker: Worker = LibvirtMonitorWorker(test_conn, )


    monitor_worker.run()
    shutdown_event.wait()
    monitor_worker.stop()