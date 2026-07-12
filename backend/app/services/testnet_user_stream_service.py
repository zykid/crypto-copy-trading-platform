from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.exchange_account import AccountMode, ExchangeName
from app.db.models.observability import AuditLog
from app.exchanges.http_client import SignedExchangeHttpClient
from app.services.exchange_accounts import get_exchange_credentials, get_owned_account
from app.services.testnet_http_client import create_testnet_signed_http_client
from app.services.testnet_user_stream import build_testnet_user_stream_connection_plan
from app.services.testnet_user_stream_activation import (
    activate_testnet_user_stream_connection_plan,
)
from app.services.testnet_user_stream_consumer import (
    TestnetUserStreamConsumer,
    TestnetUserStreamConsumerResult,
    TestnetUserStreamTransportFactory,
)
from app.services.testnet_user_stream_event_handler import (
    PersistingTestnetUserStreamEventHandler,
)
from app.services.testnet_websocket_transport import TestnetWebSocketTransport


class TestnetUserStreamBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class TestnetUserStreamConsumeResult:
    exchange_account_id: str
    exchange_name: ExchangeName
    status: str
    messages_processed: int
    reconnect_attempts: int


def consume_bounded_testnet_user_stream(
    db: Session,
    *,
    user_id: str,
    exchange_account_id: str,
    testnet_adapters_enabled: bool,
    max_messages: int,
    transport_factory: TestnetUserStreamTransportFactory | None = None,
    http_client: SignedExchangeHttpClient | None = None,
) -> TestnetUserStreamConsumeResult:
    """Consume a bounded, manually requested TESTNET private-stream session.

    No stream starts unless this service is explicitly called. It does not
    change trading flags or submit orders.
    """
    if max_messages < 1 or max_messages > 20:
        raise TestnetUserStreamBlockedError("max_messages must be between 1 and 20")
    account = get_owned_account(db, user_id=user_id, account_id=exchange_account_id)
    if account is None or not account.is_active:
        raise TestnetUserStreamBlockedError("testnet exchange account was not found")
    if account.account_mode != AccountMode.TESTNET:
        raise TestnetUserStreamBlockedError("account mode must be TESTNET")
    if account.exchange_name == ExchangeName.MOCK:
        raise TestnetUserStreamBlockedError("mock exchange has no private user stream")
    if account.trading_enabled:
        raise TestnetUserStreamBlockedError("trading must remain disabled")
    if not testnet_adapters_enabled:
        raise TestnetUserStreamBlockedError("testnet adapters must be explicitly enabled")

    credentials = get_exchange_credentials(
        db,
        user_id=user_id,
        exchange_account_id=exchange_account_id,
    )
    if credentials is None:
        raise TestnetUserStreamBlockedError("testnet API credentials are not configured")

    client = http_client or create_testnet_signed_http_client(
        exchange_name=account.exchange_name,
    )
    plan = build_testnet_user_stream_connection_plan(
        exchange_account_id=account.id,
        exchange_name=account.exchange_name,
        credentials=credentials,
    )
    plan = activate_testnet_user_stream_connection_plan(
        plan=plan,
        http_client=client,
    )
    handler = PersistingTestnetUserStreamEventHandler(
        db=db,
        user_id=user_id,
        exchange_account_id=account.id,
    )
    consumer = TestnetUserStreamConsumer(
        transport_factory=transport_factory or _default_transport_factory,
        event_handler=handler,
        max_reconnect_attempts=1,
    )
    consumer_result = consumer.consume(plan, max_messages=max_messages)
    result = _result(account.id, account.exchange_name, consumer_result)
    _write_audit(db, user_id=user_id, result=result)
    return result


def _default_transport_factory(exchange_name: ExchangeName) -> TestnetWebSocketTransport:
    return TestnetWebSocketTransport(exchange_name=exchange_name)


def _result(
    exchange_account_id: str,
    exchange_name: ExchangeName,
    result: TestnetUserStreamConsumerResult,
) -> TestnetUserStreamConsumeResult:
    return TestnetUserStreamConsumeResult(
        exchange_account_id=exchange_account_id,
        exchange_name=exchange_name,
        status=result.status.value,
        messages_processed=result.messages_processed,
        reconnect_attempts=result.reconnect_attempts,
    )


def _write_audit(
    db: Session,
    *,
    user_id: str,
    result: TestnetUserStreamConsumeResult,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            exchange_account_id=result.exchange_account_id,
            action="testnet.user_stream.consume.completed",
            severity="INFO" if result.status != "RECONNECT_EXHAUSTED" else "WARNING",
            payload={
                "exchange_name": result.exchange_name.value,
                "account_mode": AccountMode.TESTNET.value,
                "status": result.status,
                "messages_processed": result.messages_processed,
                "reconnect_attempts": result.reconnect_attempts,
            },
        )
    )
    db.commit()
