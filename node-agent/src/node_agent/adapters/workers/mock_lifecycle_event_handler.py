from node_agent.application.handlers.domain_lifecycle_event_handler import DomainLifecycleEventHandler
from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType


class MockLifecycleEventHandler(DomainLifecycleEventHandler):
    def handle_lifecycle_event(self, name: str, event: DomainEventType, detail) -> None:
        print(f"Domain lifecycle event triggered. name: {name} event: {event.name} detail: {detail}")
