import logging
import signal
from contextlib import contextmanager
from threading import Event
from types import FrameType
from typing import Generator

from libvirt import libvirtError, open, registerErrorHandler, virConnect, virEventRegisterDefaultImpl

from node_agent.application.services.service import Service
from node_agent.domain.attempt import attempt, raises

LOGGER = logging.getLogger(__name__)


class ShutdownManager:
    def __init__(self):
        self._shutdown_event = Event()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        sig_name = signal.Signals(signum).name
        LOGGER.info(f"Received signal: {sig_name}. Stopping service...")
        self._shutdown_event.set()

    def wait(self):
        self._shutdown_event.wait()


@contextmanager
@raises(RuntimeError)
def managed_runnable(runnable: Service) -> Generator[Service, None, None]:
    if not runnable.start():
        raise RuntimeError(f"Failed to start {runnable.__class__.__name__}")
    try:
        yield runnable
    finally:
        runnable.stop()


@contextmanager
@raises(RuntimeError)
def managed_libvirt_connection(uri: str) -> Generator[virConnect, None, None]:
    def libvirt_quiet_error_handler(ctx, err):
        pass

    registerErrorHandler(libvirt_quiet_error_handler, None)
    virEventRegisterDefaultImpl()

    connection = attempt(lambda: open(uri), exceptions=(libvirtError,)).value_or(None)
    if connection is None:
        raise RuntimeError(f"Failed to open connection to libvirt with URI: {uri}")
    try:
        yield connection
    finally:
        connection.close()
