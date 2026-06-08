from decimal import Decimal
from unittest.mock import MagicMock

import httpx
from app.rates import RateLookupError, RateService


def _mock_client_with_rate(rate: str) -> MagicMock:
    mock_client = MagicMock()
    mock_response = mock_client.get.return_value
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"rates": {"USD": rate}}
    return mock_client


def test_usd_skips_fx_lookup() -> None:
    mock_client = _mock_client_with_rate("1.25")
    rate_service = RateService(client=mock_client)

    assert rate_service.convert_to_usd(Decimal("10.00"), "USD") == Decimal("10.00")
    mock_client.get.assert_not_called()


def test_reuses_cached_rate_for_same_currency() -> None:
    mock_client = _mock_client_with_rate("1.25")
    rate_service = RateService(client=mock_client, cache_ttl_seconds=3600)

    assert rate_service.convert_to_usd(Decimal("10.00"), "EUR") == Decimal("12.500000")
    assert rate_service.convert_to_usd(Decimal("20.00"), "EUR") == Decimal("25.000000")

    mock_client.get.assert_called_once()


def test_refetches_rate_after_cache_expires() -> None:
    mock_client = _mock_client_with_rate("1.25")
    rate_service = RateService(client=mock_client, cache_ttl_seconds=0)

    rate_service.convert_to_usd(Decimal("10.00"), "EUR")
    rate_service.convert_to_usd(Decimal("10.00"), "EUR")

    assert mock_client.get.call_count == 2


def test_caches_rates_per_currency() -> None:
    mock_client = MagicMock()

    def response_for(params: dict[str, str]) -> MagicMock:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        currency = params["from"]
        rates = {"EUR": "1.25", "GBP": "1.30"}
        mock_response.json.return_value = {"rates": {"USD": rates[currency]}}
        return mock_response

    mock_client.get.side_effect = lambda url, params: response_for(params)
    rate_service = RateService(client=mock_client, cache_ttl_seconds=3600)

    assert rate_service.convert_to_usd(Decimal("10.00"), "EUR") == Decimal("12.500000")
    assert rate_service.convert_to_usd(Decimal("10.00"), "GBP") == Decimal("13.000000")
    assert rate_service.convert_to_usd(Decimal("10.00"), "EUR") == Decimal("12.500000")

    assert mock_client.get.call_count == 2


def test_raises_when_rate_lookup_fails() -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.HTTPError("service unavailable")
    rate_service = RateService(client=mock_client)

    try:
        rate_service.convert_to_usd(Decimal("10.00"), "EUR")
    except RateLookupError as exc:
        assert "Failed to fetch rate for EUR" in str(exc)
    else:
        raise AssertionError("expected RateLookupError")
