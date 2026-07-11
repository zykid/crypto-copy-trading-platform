from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.exchange_account import ExchangeName
from app.db.models.user import User
from app.services.gexbot_market_data import (
    GexbotConfigurationError,
    GexbotMarketDataClient,
    GexbotMarketDataError,
    GexbotValidationError,
)
from app.services.public_market_data import (
    PublicCandleResult,
    PublicMarketDataError,
    get_public_candles,
    get_public_candles_with_fallback,
)

router = APIRouter()


@router.get("/public/candles")
def get_exchange_candles(
    exchange: ExchangeName,
    symbol: str,
    interval: str = "1m",
    limit: int = 200,
    allow_fallback: bool = True,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        if allow_fallback:
            result = get_public_candles_with_fallback(
                exchange_name=exchange,
                symbol=symbol,
                interval=interval,
                limit=limit,
            )
        else:
            result = PublicCandleResult(
                requested_exchange=exchange,
                source_exchange=exchange,
                candles=get_public_candles(
                    exchange_name=exchange,
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                ),
            )
    except PublicMarketDataError as exc:
        raise HTTPException(
            status_code=502 if exc.failure_type != "invalid_response" else 422,
            detail={"reason": str(exc), "failure_type": exc.failure_type},
        ) from exc
    return {
        "exchange": exchange.value,
        "source_exchange": result.source_exchange.value,
        "fallback_used": result.fallback_used,
        "symbol": symbol.upper(),
        "interval": interval,
        "candles": result.candles,
    }


@router.get("/providers")
def list_market_data_providers(_: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "providers": [
            {
                "id": "gexbot",
                "name": "GEXBot",
                "base_url": settings.gexbot_api_base_url,
                "configured": bool(settings.gexbot_api_key.strip()),
                "auth_required": True,
                "read_only": True,
                "supports": ["tickers", "classic", "state", "orderflow"],
            }
        ]
    }


@router.get("/gexbot/tickers")
def list_gexbot_tickers(_: User = Depends(get_current_user)) -> dict[str, Any]:
    try:
        payload = _client().list_tickers()
    except GexbotMarketDataError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "failure_type": exc.failure_type,
                "provider_status_code": exc.status_code,
            },
        ) from exc
    return _provider_payload(endpoint="tickers", authenticated=False, data=payload)


@router.get("/gexbot/{package_name}/{ticker}/{category}")
def get_gexbot_package_category(
    package_name: str,
    ticker: str,
    category: str,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        payload = _client().get_package_category(
            ticker=ticker,
            package=package_name,
            category=category,
        )
    except GexbotConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="GEXBot API key is not configured",
        ) from exc
    except GexbotValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GexbotMarketDataError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "failure_type": exc.failure_type,
                "provider_status_code": exc.status_code,
            },
        ) from exc
    return _provider_payload(
        endpoint=f"{package_name.lower()}/{ticker.upper()}/{category.lower()}",
        authenticated=True,
        data=payload,
    )


@router.get("/gexbot/orderflow/{ticker}")
def get_gexbot_orderflow(ticker: str, _: User = Depends(get_current_user)) -> dict[str, Any]:
    try:
        payload = _client().get_orderflow(ticker=ticker)
    except GexbotConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="GEXBot API key is not configured",
        ) from exc
    except GexbotValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GexbotMarketDataError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "failure_type": exc.failure_type,
                "provider_status_code": exc.status_code,
            },
        ) from exc
    return _provider_payload(
        endpoint=f"orderflow/{ticker.upper()}",
        authenticated=True,
        data=payload,
    )


def _client() -> GexbotMarketDataClient:
    return GexbotMarketDataClient(
        base_url=settings.gexbot_api_base_url,
        api_key=settings.gexbot_api_key,
        timeout_seconds=settings.gexbot_timeout_seconds,
    )


def _provider_payload(
    *,
    endpoint: str,
    authenticated: bool,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "provider": "gexbot",
        "endpoint": endpoint,
        "authenticated": authenticated,
        "data": data,
    }
