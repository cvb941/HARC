"""Tests for the RevenueCat config flow."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.revenuecat_metrics.config_flow import (
    RevenueCatMetricsConfigFlow,
    RevenueCatMetricsOptionsFlow,
)
from custom_components.revenuecat_metrics.const import DOMAIN


def test_options_flow_can_be_constructed():
    """Options flow construction must not assign the read-only config_entry property."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="test")

    flow = RevenueCatMetricsConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, RevenueCatMetricsOptionsFlow)
