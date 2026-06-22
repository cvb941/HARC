"""Tests for RevenueCat sensor properties."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.revenuecat_metrics.api import RevenueCatSensorMetric
from custom_components.revenuecat_metrics.const import (
    CONF_API_KEY,
    CONF_CURRENCY,
    CONF_PROJECT_ID,
    CONF_REVENUE_TYPE,
    DOMAIN,
)
from custom_components.revenuecat_metrics.coordinator import (
    RevenueCatMetricsCoordinator,
)
from custom_components.revenuecat_metrics.sensor import RevenueCatMetricSensor


def test_sensor_native_value_and_units(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "secret",
            CONF_PROJECT_ID: "proj_test",
            CONF_CURRENCY: "EUR",
            CONF_REVENUE_TYPE: "proceeds",
        },
        entry_id="test",
    )
    coordinator = RevenueCatMetricsCoordinator(hass, entry, _UnusedApi())
    coordinator.data = {
        "mrr": RevenueCatSensorMetric(
            key="mrr",
            name="MRR",
            value=1250.0,
            metric_kind="monetary",
            project_id="proj_test",
            source="chart",
            chart_id="mrr",
            currency="EUR",
            revenue_type="proceeds",
        )
    }

    entity = RevenueCatMetricSensor(coordinator, "mrr")

    assert entity.native_value == 1250.0
    assert entity.entity_description.native_unit_of_measurement == "EUR"
    assert entity.extra_state_attributes["chart_id"] == "mrr"


def test_sensor_uses_metric_availability(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "secret",
            CONF_PROJECT_ID: "proj_test",
            CONF_CURRENCY: "EUR",
            CONF_REVENUE_TYPE: "proceeds",
        },
        entry_id="test",
    )
    coordinator = RevenueCatMetricsCoordinator(hass, entry, _UnusedApi())
    coordinator.data = {
        "mrr_daily_history": RevenueCatSensorMetric(
            key="mrr_daily_history",
            name="MRR Daily History",
            value=None,
            metric_kind="monetary",
            project_id="proj_test",
            source="chart_history",
            chart_id="mrr",
            currency="EUR",
            revenue_type="proceeds",
            available=False,
            history_values=(),
            history_dates=(),
            days=0,
        )
    }

    entity = RevenueCatMetricSensor(coordinator, "mrr_daily_history")

    assert entity.available is False
    assert entity.extra_state_attributes["values"] == []


class _UnusedApi:
    pass
