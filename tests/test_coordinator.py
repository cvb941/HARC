"""Tests for the RevenueCat coordinator."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.revenuecat_metrics.const import (
    CONF_API_KEY,
    CONF_CURRENCY,
    CONF_ENABLED_CHARTS,
    CONF_HISTORY_DAYS,
    CONF_PROJECT_ID,
    CONF_REVENUE_TYPE,
    DOMAIN,
    MRR_DAILY_HISTORY_SENSOR_KEY,
)
from custom_components.revenuecat_metrics.coordinator import (
    RevenueCatMetricsCoordinator,
)
from custom_components.revenuecat_metrics.api import RevenueCatError


@pytest.mark.asyncio
async def test_successful_coordinator_update(hass, load_fixture):
    api = _FakeApi(load_fixture)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "secret",
            CONF_PROJECT_ID: "proj_test",
            CONF_CURRENCY: "EUR",
            CONF_REVENUE_TYPE: "proceeds",
            CONF_ENABLED_CHARTS: ["mrr"],
        },
        options={CONF_HISTORY_DAYS: 7},
        entry_id="test",
    )
    coordinator = RevenueCatMetricsCoordinator(hass, entry, api)

    data = await coordinator._async_update_data()

    assert data["mrr"].value == 1250.0
    assert data["revenue_28d"].value == 3456.78
    assert data["overview_mrr"].native_unit == "EUR"
    assert data[MRR_DAILY_HISTORY_SENSOR_KEY].attributes["values"] == [980, 995, 1010]
    assert api.history_days == 7


@pytest.mark.asyncio
async def test_history_failure_preserves_existing_metrics(hass, load_fixture):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "secret",
            CONF_PROJECT_ID: "proj_test",
            CONF_CURRENCY: "EUR",
            CONF_REVENUE_TYPE: "proceeds",
            CONF_ENABLED_CHARTS: ["mrr"],
        },
        entry_id="test",
    )
    coordinator = RevenueCatMetricsCoordinator(
        hass,
        entry,
        _FakeApi(load_fixture, fail_history=True),
    )

    data = await coordinator._async_update_data()

    assert data["mrr"].value == 1250.0
    assert data["revenue_28d"].value == 3456.78
    assert data["overview_mrr"].native_unit == "EUR"
    assert data[MRR_DAILY_HISTORY_SENSOR_KEY].available is False
    assert data[MRR_DAILY_HISTORY_SENSOR_KEY].attributes["values"] == []


class _FakeApi:
    def __init__(self, load_fixture, *, fail_history=False) -> None:
        self._load_fixture = load_fixture
        self._fail_history = fail_history
        self.history_days = None

    async def async_get_overview_metrics(self, project_id, currency):
        return self._load_fixture("overview.json")

    async def async_get_revenue_28d(self, project_id, currency, revenue_type):
        return self._load_fixture("revenue_28d.json")

    async def async_get_chart(self, project_id, chart_name, currency, revenue_type):
        return self._load_fixture("chart_mrr_array.json")

    async def async_get_mrr_daily_history(
        self,
        project_id,
        currency,
        revenue_type,
        *,
        days,
    ):
        self.history_days = days
        if self._fail_history:
            raise RevenueCatError("history endpoint failed")
        return self._load_fixture("chart_mrr_history.json")
