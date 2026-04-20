from typing import Protocol

from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType


class DomainLifecycleEventHandler(Protocol):
    def handle_lifecycle_event(self, name: str, event: DomainEventType, detail) -> None: ...
