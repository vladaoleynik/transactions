"""FX rate lookup for converting transaction amounts to USD."""

from decimal import Decimal

import httpx

from app.config import settings


class RateLookupError(Exception):
    """Frankfurter API unavailable or returned an unexpected response."""


class RateService:
    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        self._base_url = base_url or settings.fx_api_base_url
        self._client = client

    def convert_to_usd(self, amount: Decimal, currency: str) -> Decimal:
        currency = currency.upper()
        if currency == "USD":
            return amount

        rate = self._fetch_rate(currency)
        return (amount * rate).quantize(Decimal("0.000001"))

    def _fetch_rate(self, currency: str) -> Decimal:
        url = f"{self._base_url}/latest"
        params = {"from": currency, "to": "USD"}

        try:
            if self._client is not None:
                response = self._client.get(url, params=params)
            else:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            return Decimal(str(payload["rates"]["USD"]))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise RateLookupError(f"Failed to fetch rate for {currency}") from exc
