"""RevenueCat Metrics sensors."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RevenueCatSensorMetric
from .const import DOMAIN
from .coordinator import RevenueCatMetricsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RevenueCat Metrics sensors."""
    coordinator: RevenueCatMetricsCoordinator = entry.runtime_data
    entities: Sequence[RevenueCatMetricSensor] = [
        RevenueCatMetricSensor(coordinator, key)
        for key in sorted(coordinator.data or {})
    ]
    async_add_entities(entities)


class RevenueCatMetricSensor(
    CoordinatorEntity[RevenueCatMetricsCoordinator],
    SensorEntity,
):
    """Representation of one RevenueCat metric."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RevenueCatMetricsCoordinator, key: str) -> None:
        super().__init__(coordinator, context=key)
        self._key = key
        metric = self._metric
        self._attr_unique_id = f"{coordinator.project_id}_{key}"
        self.entity_description = SensorEntityDescription(
            key=key,
            name=metric.name,
            device_class=SensorDeviceClass.MONETARY
            if metric.metric_kind == "monetary"
            else None,
            native_unit_of_measurement=metric.native_unit,
        )

    @property
    def _metric(self) -> RevenueCatSensorMetric:
        return self.coordinator.data[self._key]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the RevenueCat project device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.project_id)},
            manufacturer="RevenueCat",
            name=f"RevenueCat {self.coordinator.project_id}",
            configuration_url=(
                f"https://app.revenuecat.com/projects/{self.coordinator.project_id}"
            ),
        )

    @property
    def native_value(self) -> float | int | None:
        """Return native sensor value."""
        return self._metric.value

    @property
    def available(self) -> bool:
        """Return whether this specific metric is available."""
        return super().available and self._metric.available

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return compact state attributes."""
        return self._metric.attributes
