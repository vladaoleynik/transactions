"""FX rate lookup for converting transaction amounts to USD."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from app.config import settings


class RateLookupError(Exception):
    """Frankfurter API unavailable or returned an unexpected response."""


@dataclass
class _CachedRate:
    rate: Decimal
    expires_at: datetime


class RateService:
    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        cache_ttl_seconds: int | None = None,
    ) -> None:
        self._base_url = base_url or settings.fx_api_base_url
        self._client = client or httpx.Client(timeout=5.0)
        ttl_seconds = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else settings.fx_rate_cache_ttl_seconds
        )
        self._cache_ttl = timedelta(seconds=ttl_seconds)
        self._rate_cache: dict[str, _CachedRate] = {}

    def convert_to_usd(self, amount: Decimal, currency: str) -> Decimal:
        currency = currency.upper()
        if currency == "USD":
            return amount

        rate = self._fetch_rate(currency)
        return (amount * rate).quantize(Decimal("0.000001"))

    def _fetch_rate(self, currency: str) -> Decimal:
        cached = self._rate_cache.get(currency)
        now = datetime.now(UTC)
        if cached is not None and cached.expires_at > now:
            return cached.rate

        rate = self._fetch_rate_from_api(currency)
        self._rate_cache[currency] = _CachedRate(rate=rate, expires_at=now + self._cache_ttl)
        return rate

    def _fetch_rate_from_api(self, currency: str) -> Decimal:
        url = f"{self._base_url}/latest"
        params = {"from": currency, "to": "USD"}

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            return Decimal(str(payload["rates"]["USD"]))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise RateLookupError(f"Failed to fetch rate for {currency}") from exc
