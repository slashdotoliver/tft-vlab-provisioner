import logging
from threading import Event, Thread
from typing import Callable

from node_agent.domain.attempt import attempt

LoopAction = Callable[[Callable[[], bool]], None]


LOGGER = logging.getLogger(__name__)


class ThreadController:
    def __init__(self, name: str, loop_action: LoopAction, stop_timeout_sec: float, daemon: bool = True):
        self._name = name
        self._loop_action = loop_action
        self._stop_timeout_sec = stop_timeout_sec
        self._daemon = daemon

        self._stop_event = Event()
        self._thread: Thread | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _thread_target(self) -> None:
        self._loop_action(self._stop_event.is_set)

    def start(self) -> bool:
        def thread_start_exception_mapper(exception: Exception) -> RuntimeError:
            LOGGER.error(f"ThreadController [{self._name}] crashed on startup: {exception}")
            return RuntimeError(exception)

        if self.is_running():
            LOGGER.warning(f"Trying to start thread {self._name} that is already running")
            return False

        self._stop_event.clear()
        self._thread = Thread(
            target=self._thread_target,
            name=self._name,
            daemon=self._daemon,
        )

        return (
            attempt(
                lambda: self._thread.start(),
                exceptions=(RuntimeError,),
                exception_mapper=thread_start_exception_mapper,
            )
            .map(lambda _: True)
            .value_or(False)
        )

    def stop(self) -> bool:
        self._stop_event.set()

        if not self._thread:
            LOGGER.warning(f"Thread {self._name} is already stopped or never started")
            return True

        self._thread.join(timeout=self._stop_timeout_sec)

        if self._thread.is_alive():
            LOGGER.error(f"Error: The thread {self._name} did not stop within {self._stop_timeout_sec} seconds")
            return False

        LOGGER.debug(f"Thread {self._name} stopped cleanly")
        self._thread = None
        return True
