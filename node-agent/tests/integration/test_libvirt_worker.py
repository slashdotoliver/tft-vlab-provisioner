from time import sleep

import libvirt

from node_agent.adapters.workers.libvirt_monitor_worker import LibvirtMonitorWorker
from node_agent.adapters.workers.mock_lifecycle_event_handler import MockLifecycleEventHandler
from node_agent.application.ports.worker import Worker


def test_should_invoke_lifecycle_event():
    libvirt.virEventRegisterDefaultImpl()
    test_conn: libvirt.virConnect | None = libvirt.open("test:///default")
    assert test_conn is not None

    monitor_worker: Worker = LibvirtMonitorWorker(test_conn, MockLifecycleEventHandler())

    assert monitor_worker.run()
    sleep(0.15)
    # TODO: add an event in the test connection
    assert monitor_worker.stop()
