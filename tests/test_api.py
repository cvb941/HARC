"""Tests for RevenueCat API parsing and errors."""

from __future__ import annotations

import pytest

from custom_components.revenuecat_metrics.api import (
    RevenueCatApi,
    RevenueCatAuthError,
    RevenueCatRateLimitError,
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

    def get(self, *args, **kwargs):
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
