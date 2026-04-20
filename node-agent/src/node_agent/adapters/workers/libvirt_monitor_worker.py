import logging
import threading
from threading import Thread
from typing import Any

import libvirt

from node_agent.application.handlers.domain_lifecycle_event_handler import DomainLifecycleEventHandler
from node_agent.application.ports.worker import Worker
from node_agent.domain.attempt import attempt
from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType

MONITOR_WORKER_THREAD_NAME: str = "LibvirtMonitorWorkerThread0"
EVENT_TIMEOUT_MS: int = 500


class LibvirtMonitorWorker(Worker):
    def __init__(
            self, connection: libvirt.virConnect,
            lifecycle_event_handler: DomainLifecycleEventHandler
    ):
        self._connection = connection
        self._lifecycle_event_handler = lifecycle_event_handler

        self.logger = logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._worker_thread: None | Thread = None
        self._timeout_id: int = -1
        self._lifecycle_event_id: int = -1

    @property
    def _thread_started(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    @property
    def _running(self) -> bool:
        return not self._stop_event.is_set()

    def _on_lifecycle_event(
            self, conn: libvirt.virConnect, dom: libvirt.virDomain, event: int, detail: int,
            opaque: Any
    ):
        event_type: DomainEventType | None = attempt(
            lambda: DomainEventType(event), exceptions=(ValueError,)
        ).value_or(None)
        if event_type is None:
            self.logger.error(f"The lifecycle event was triggered with an unknown lifecycle event type: {event_type}")
            return
        self._lifecycle_event_handler.handle_lifecycle_event(dom.name(), event_type, detail)

    def _dummy_timeout_cb(self, timer_id, opaque):
        pass

    def _event_loop(self):
        self.logger.debug(f"Thread {MONITOR_WORKER_THREAD_NAME} started")

        self._timeout_id = libvirt.virEventAddTimeout(
            EVENT_TIMEOUT_MS,
            self._dummy_timeout_cb,
            None
        )
        self._lifecycle_event_id = self._connection.domainEventRegisterAny(
            dom=None,
            eventID=libvirt.VIR_DOMAIN_EVENT_ID_LIFECYCLE,
            cb=self._on_lifecycle_event,
            opaque=None
        )

        while self._running:
            libvirt.virEventRunDefaultImpl()

        if self._timeout_id != -1:
            libvirt.virEventRemoveTimeout(self._timeout_id)
        if self._lifecycle_event_id != -1:
            self._connection.domainEventDeregisterAny(self._lifecycle_event_id)

    def run(self) -> bool:
        def thread_start_exception_mapper(exception: Exception) -> RuntimeError:
            self.logger.error(exception)
            return RuntimeError(exception)

        if self._thread_started:
            self.logger.warning(
                f"Trying to start {MONITOR_WORKER_THREAD_NAME} thread that has already started"
            )
            return False

        self._stop_event.clear()
        self._worker_thread = Thread(
            target=self._event_loop,
            name=MONITOR_WORKER_THREAD_NAME,
            daemon=True
        )

        return (
            attempt(
                lambda: self._worker_thread.start(),
                exceptions=(RuntimeError,),
                exception_mapper=thread_start_exception_mapper
            )
            .map(lambda success: True)
            .value_or(False)
        )

    def stop(self) -> bool:
        if self._worker_thread is None:
            self.logger.warning(f"Thread {MONITOR_WORKER_THREAD_NAME} has not started")
            return False

        self._stop_event.set()

        timeout_seconds = (4 * EVENT_TIMEOUT_MS) / 1000.0
        self._worker_thread.join(timeout=timeout_seconds)

        if self._worker_thread.is_alive():
            self.logger.error(f"The thread {MONITOR_WORKER_THREAD_NAME} did not stop in time")
            return False

        self.logger.debug(
            f"The thread {MONITOR_WORKER_THREAD_NAME} stopped" if self._worker_thread else
            f"The thread {MONITOR_WORKER_THREAD_NAME} never started"
        )
        self._worker_thread = None
        return True
