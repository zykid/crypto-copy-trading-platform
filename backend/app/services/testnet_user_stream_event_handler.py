from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.testnet_account_state_sync import sync_testnet_account_state_event
from app.services.testnet_order_lifecycle import (
    TestnetOrderLifecycleProcessor,
    TestnetOrderLifecycleResult,
)
from app.services.testnet_user_stream_runtime import (
    TestnetUserStreamEvent,
    TestnetUserStreamEventType,
)


@dataclass(frozen=True)
class TestnetUserStreamEventHandlingResult:
    order_result: TestnetOrderLifecycleResult | None
    state_event_processed: bool


class PersistingTestnetUserStreamEventHandler:
    """Persist one event from an already-authorized private TESTNET stream.

    This handler does not create a websocket connection or submit an order.
    """

    def __init__(
        self,
        *,
        db: Session,
        user_id: str,
        exchange_account_id: str,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._exchange_account_id = exchange_account_id
        self._order_processor = TestnetOrderLifecycleProcessor(
            db=db,
            user_id=user_id,
            exchange_account_id=exchange_account_id,
        )

    def __call__(
        self,
        event: TestnetUserStreamEvent,
    ) -> TestnetUserStreamEventHandlingResult:
        if event.event_type == TestnetUserStreamEventType.ORDER:
            return TestnetUserStreamEventHandlingResult(
                order_result=self._order_processor.handle_user_stream_event(event),
                state_event_processed=False,
            )

        state_result = sync_testnet_account_state_event(
            self._db,
            user_id=self._user_id,
            exchange_account_id=self._exchange_account_id,
            event=event,
        )
        if state_result.status.value == "SYNCED":
            self._db.commit()
        return TestnetUserStreamEventHandlingResult(
            order_result=None,
            state_event_processed=state_result.status.value == "SYNCED",
        )
