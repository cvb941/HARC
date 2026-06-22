"""Tests for RevenueCat API parsing and errors."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.revenuecat_metrics.api import (
    RevenueCatApi,
    RevenueCatAuthError,
    RevenueCatRateLimitError,
    parse_mrr_daily_history,
    parse_chart_metric,
    parse_overview_metrics,
    parse_revenue_metric,
)


def test_parse_array_chart_latest_value(load_fixture):
    metric = parse_chart_metric(
        load_fixture("chart_mrr_array.json"),
        chart_name="mrr",
        project_id="proj_test",
        currency="EUR",
        revenue_type="proceeds",
    )

    assert metric.key == "mrr"
    assert metric.value == 1250.0
    assert metric.native_unit == "EUR"
    assert metric.attributes["chart_id"] == "mrr"
    assert metric.attributes["revenue_type"] == "proceeds"


def test_parse_object_chart_percentage(load_fixture):
    metric = parse_chart_metric(
        load_fixture("chart_trial_conversion_object.json"),
        chart_name="trial_conversion_rate",
        project_id="proj_test",
        currency="EUR",
        revenue_type="revenue",
    )

    assert metric.key == "trial_conversion_rate"
    assert metric.value == 42.25
    assert metric.native_unit == "%"
    assert metric.attributes["period_start"] == "2026-06-18"


def test_parse_overview_metrics(load_fixture):
    metrics = parse_overview_metrics(
        load_fixture("overview.json"),
        project_id="proj_test",
    )

    assert metrics["overview_active_subscriptions"].value == 99
    assert metrics["overview_mrr"].value == 1250.0
    assert metrics["overview_mrr"].native_unit == "EUR"


def test_parse_revenue_metric(load_fixture):
    metric = parse_revenue_metric(
        load_fixture("revenue_28d.json"),
        project_id="proj_test",
    )

    assert metric.key == "revenue_28d"
    assert metric.value == 3456.78
    assert metric.native_unit == "EUR"
    assert metric.attributes["revenue_type"] == "proceeds"


def test_parse_mrr_daily_history_orders_attributes(load_fixture):
    metric = parse_mrr_daily_history(
        load_fixture("chart_mrr_history.json"),
        project_id="proj_test",
        currency="USD",
        revenue_type="proceeds",
    )

    assert metric.key == "mrr_daily_history"
    assert metric.value == 1010
    assert metric.available is True
    assert metric.native_unit == "EUR"
    assert metric.attributes["currency"] == "EUR"
    assert metric.attributes["values"] == [980, 995, 1010]
    assert metric.attributes["dates"] == [
        "2026-06-17",
        "2026-06-18",
        "2026-06-19",
    ]
    assert metric.attributes["days"] == 3
    assert metric.attributes["updated_at"] == "2026-06-19T10:00:00+00:00"


def test_parse_mrr_daily_history_empty_is_unavailable(load_fixture):
    metric = parse_mrr_daily_history(
        load_fixture("chart_mrr_history_empty.json"),
        project_id="proj_test",
        currency="EUR",
        revenue_type="proceeds",
    )

    assert metric.value is None
    assert metric.available is False
    assert metric.attributes["values"] == []
    assert metric.attributes["dates"] == []
    assert metric.attributes["days"] == 0
    assert metric.attributes["currency"] == "EUR"


@pytest.mark.asyncio
async def test_mrr_daily_history_request_uses_daily_resolution_and_days():
    session = _FakeSession(_FakeResponse(200, {"object": "chart_data"}))
    api = RevenueCatApi(session, "secret")

    await api.async_get_mrr_daily_history(
        "proj_test",
        "EUR",
        "proceeds",
        days=14,
        today=date(2026, 6, 22),
    )

    request = session.requests[0]
    assert request["params"]["start_date"] == "2026-06-09"
    assert request["params"]["end_date"] == "2026-06-22"
    assert request["params"]["currency"] == "EUR"
    assert request["params"]["resolution"] == "day"
    assert request["params"]["selectors"] == '{"revenue_type":"proceeds"}'


@pytest.mark.asyncio
async def test_auth_failure_raises_auth_error():
    api = RevenueCatApi(
        _FakeSession(_FakeResponse(401, {"message": "Unauthorized"})),
        "secret",
    )

    with pytest.raises(RevenueCatAuthError):
        await api.async_get_overview_metrics("proj_test", "EUR")


@pytest.mark.asyncio
async def test_rate_limit_includes_retry_after():
    api = RevenueCatApi(
        _FakeSession(
            _FakeResponse(
                429,
                {"message": "Rate limit exceeded", "backoff_ms": 4000},
                headers={"Retry-After": "5"},
            )
        ),
        "secret",
    )

    with pytest.raises(RevenueCatRateLimitError) as err:
        await api.async_get_overview_metrics("proj_test", "EUR")
    assert err.value.retry_after == 5


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.requests = []

    def get(self, *args, **kwargs):
        self.requests.append(kwargs)
        return self.response


class _FakeResponse:
    def __init__(
        self,
        status: int,
        payload: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def json(self, content_type=None):
        return self._payload
