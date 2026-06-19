"""DataUpdateCoordinator for RevenueCat Metrics."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    RevenueCatApi,
    RevenueCatAuthError,
    RevenueCatError,
    RevenueCatRateLimitError,
    RevenueCatSensorMetric,
    RevenueCatTransientError,
    parse_chart_metric,
    parse_overview_metrics,
    parse_revenue_metric,
)
from .const import (
    CONF_CURRENCY,
    CONF_ENABLED_CHARTS,
    CONF_PROJECT_ID,
    CONF_REVENUE_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CURRENCY,
    DEFAULT_ENABLED_CHARTS,
    DEFAULT_REVENUE_TYPE,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MIN_UPDATE_INTERVAL_MINUTES,
    SUPPORTED_CHARTS,
)

_LOGGER = logging.getLogger(__name__)


class RevenueCatMetricsCoordinator(
    DataUpdateCoordinator[dict[str, RevenueCatSensorMetric]]
):
    """Coordinate RevenueCat polling for all sensors in one config entry."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: RevenueCatApi,
    ) -> None:
        self.api = api
        self.project_id = config_entry.data[CONF_PROJECT_ID]

        interval_minutes = max(
            MIN_UPDATE_INTERVAL_MINUTES,
            int(
                config_entry.options.get(
                    CONF_UPDATE_INTERVAL,
                    config_entry.data.get(
                        CONF_UPDATE_INTERVAL,
                        DEFAULT_UPDATE_INTERVAL_MINUTES,
                    ),
                )
            ),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(minutes=interval_minutes),
            always_update=False,
        )

    @property
    def currency(self) -> str:
        """Return the selected currency."""
        return self.config_entry.options.get(
            CONF_CURRENCY,
            self.config_entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        )

    @property
    def revenue_type(self) -> str:
        """Return the selected RevenueCat revenue definition."""
        return self.config_entry.options.get(
            CONF_REVENUE_TYPE,
            self.config_entry.data.get(CONF_REVENUE_TYPE, DEFAULT_REVENUE_TYPE),
        )

    @property
    def enabled_charts(self) -> tuple[str, ...]:
        """Return enabled chart IDs."""
        charts = self.config_entry.options.get(
            CONF_ENABLED_CHARTS,
            self.config_entry.data.get(CONF_ENABLED_CHARTS, DEFAULT_ENABLED_CHARTS),
        )
        return tuple(chart for chart in charts if chart in SUPPORTED_CHARTS)

    async def _async_update_data(self) -> dict[str, RevenueCatSensorMetric]:
        """Fetch data from RevenueCat."""
        try:
            data: dict[str, RevenueCatSensorMetric] = {}

            overview_payload = await self.api.async_get_overview_metrics(
                self.project_id,
                self.currency,
            )
            data.update(
                parse_overview_metrics(
                    overview_payload,
                    project_id=self.project_id,
                )
            )

            revenue_payload = await self.api.async_get_revenue_28d(
                self.project_id,
                self.currency,
                self.revenue_type,
            )
            revenue_metric = parse_revenue_metric(
                revenue_payload,
                project_id=self.project_id,
            )
            data[revenue_metric.key] = revenue_metric

            for chart_name in self.enabled_charts:
                chart_payload = await self.api.async_get_chart(
                    self.project_id,
                    chart_name,
                    self.currency,
                    self.revenue_type,
                )
                chart_metric = parse_chart_metric(
                    chart_payload,
                    chart_name=chart_name,
                    project_id=self.project_id,
                    currency=self.currency,
                    revenue_type=self.revenue_type,
                )
                data[chart_metric.key] = chart_metric

            return data
        except RevenueCatAuthError as err:
            raise ConfigEntryAuthFailed from err
        except RevenueCatRateLimitError as err:
            message = f"RevenueCat rate limit reached: {err}"
            if err.retry_after is not None:
                raise UpdateFailed(message, retry_after=err.retry_after) from err
            raise UpdateFailed(message) from err
        except RevenueCatTransientError as err:
            message = f"Temporary RevenueCat API error: {err}"
            if err.retry_after is not None:
                raise UpdateFailed(message, retry_after=err.retry_after) from err
            raise UpdateFailed(message) from err
        except RevenueCatError as err:
            raise UpdateFailed(f"RevenueCat API error: {err}") from err
