import logging

from node_agent.application.handlers.domain_lifecycle_event_handler import DomainLifecycleEventHandler
from node_agent.application.services.reconciliation_loop import ReconciliationLoop
from node_agent.domain.type_adapters.vir_domain_event_id import DomainEventType

LOGGER = logging.getLogger(__name__)


class ReconciliationTrigger(DomainLifecycleEventHandler):
    def __init__(self, reconciliation_loop: ReconciliationLoop) -> None:
        self.reconciliation_loop = reconciliation_loop

    def handle_lifecycle_event(self, name: str, event: DomainEventType, detail) -> None:
        LOGGER.info(f"Domain lifecycle event triggered. name: {name} event: {event.name} detail: {detail}")
        self.reconciliation_loop.trigger()
