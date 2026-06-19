"""RevenueCat API client and response parsers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    API_BASE_URL,
    API_TIMEOUT_SECONDS,
    ATTR_CHART_ID,
    ATTR_CURRENCY,
    ATTR_LAST_UPDATED_FROM_REVENUECAT,
    ATTR_PERIOD_END,
    ATTR_PERIOD_START,
    ATTR_PROJECT_ID,
    ATTR_REVENUE_TYPE,
    ATTR_SOURCE,
    CHART_DISPLAY_NAMES,
    CHART_LOOKBACK_DAYS,
    CHART_SENSOR_KEYS,
    CONF_REVENUE_TYPE,
    DEFAULT_CURRENCY,
    MONETARY_CHARTS,
    OVERVIEW_SENSOR_PREFIX,
    PERCENTAGE_CHARTS,
    REVENUE_TYPE_CHARTS,
    REVENUE_WINDOW_DAYS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RevenueCatSensorMetric:
    """A parsed metric ready for a Home Assistant sensor."""

    key: str
    name: str
    value: float | int | None
    metric_kind: str
    project_id: str
    source: str
    chart_id: str | None = None
    currency: str | None = None
    revenue_type: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    last_updated_from_revenuecat: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def native_unit(self) -> str | None:
        """Return the Home Assistant native unit for this metric."""
        if self.metric_kind == "monetary":
            return self.currency or DEFAULT_CURRENCY
        if self.metric_kind == "percentage":
            return "%"
        return None

    @property
    def attributes(self) -> dict[str, Any]:
        """Return stable Home Assistant state attributes."""
        attrs: dict[str, Any] = {
            ATTR_PROJECT_ID: self.project_id,
            ATTR_SOURCE: self.source,
        }
        if self.chart_id is not None:
            attrs[ATTR_CHART_ID] = self.chart_id
        if self.currency is not None:
            attrs[ATTR_CURRENCY] = self.currency
        if self.revenue_type is not None:
            attrs[ATTR_REVENUE_TYPE] = self.revenue_type
        if self.period_start is not None:
            attrs[ATTR_PERIOD_START] = self.period_start
        if self.period_end is not None:
            attrs[ATTR_PERIOD_END] = self.period_end
        if self.last_updated_from_revenuecat is not None:
            attrs[ATTR_LAST_UPDATED_FROM_REVENUECAT] = self.last_updated_from_revenuecat
        if self.summary:
            attrs["summary"] = self.summary
        return attrs


class RevenueCatError(Exception):
    """Base class for RevenueCat errors."""


class RevenueCatAuthError(RevenueCatError):
    """Authentication or authorization failed."""


class RevenueCatRateLimitError(RevenueCatError):
    """RevenueCat rate limit was reached."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RevenueCatPayloadError(RevenueCatError):
    """RevenueCat returned an unexpected payload shape."""


class RevenueCatTransientError(RevenueCatError):
    """RevenueCat returned a retryable server-side error."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RevenueCatApi:
    """Small async client for RevenueCat REST API v2."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        *,
        base_url: str = API_BASE_URL,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def async_validate_project(
        self,
        project_id: str,
        currency: str,
        revenue_type: str,
    ) -> None:
        """Validate credentials by fetching overview and chart payloads."""
        await self.async_get_overview_metrics(project_id, currency)
        await self.async_get_chart(project_id, "mrr", currency, revenue_type)

    async def async_get_overview_metrics(
        self,
        project_id: str,
        currency: str,
    ) -> dict[str, Any]:
        """Fetch RevenueCat overview metrics."""
        return await self._request(
            f"/projects/{project_id}/metrics/overview",
            params={"currency": currency},
        )

    async def async_get_revenue_28d(
        self,
        project_id: str,
        currency: str,
        revenue_type: str,
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Fetch authoritative revenue for the most recent 28-day window."""
        end_date = today or datetime.now(UTC).date()
        start_date = end_date - timedelta(days=REVENUE_WINDOW_DAYS - 1)
        return await self._request(
            f"/projects/{project_id}/metrics/revenue",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "currency": currency,
                CONF_REVENUE_TYPE: revenue_type,
            },
        )

    async def async_get_chart(
        self,
        project_id: str,
        chart_name: str,
        currency: str,
        revenue_type: str,
        *,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Fetch one RevenueCat chart over a modest lookback window."""
        end_date = today or datetime.now(UTC).date()
        start_date = end_date - timedelta(days=CHART_LOOKBACK_DAYS)
        params: dict[str, str] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "currency": currency,
        }
        if chart_name in REVENUE_TYPE_CHARTS:
            params["selectors"] = json.dumps(
                {CONF_REVENUE_TYPE: revenue_type},
                separators=(",", ":"),
            )

        return await self._request(
            f"/projects/{project_id}/charts/{chart_name}",
            params=params,
        )

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a RevenueCat GET request."""
        url = f"{self._base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        _LOGGER.debug("Requesting RevenueCat API path %s params %s", path, params)

        try:
            async with asyncio.timeout(API_TIMEOUT_SECONDS):
                async with self._session.get(
                    url,
                    headers=headers,
                    params=params,
                ) as response:
                    payload = await _json_payload(response)
                    if response.status < 400:
                        return payload
                    _raise_response_error(response.status, response.headers, payload)
        except TimeoutError as err:
            raise RevenueCatTransientError(
                "Timed out communicating with RevenueCat"
            ) from err
        except ClientError as err:
            raise RevenueCatTransientError(
                f"Error communicating with RevenueCat: {err}"
            ) from err

        raise RevenueCatTransientError("Unexpected RevenueCat response")


async def _json_payload(response: Any) -> dict[str, Any]:
    """Return response JSON, tolerating missing content-type headers."""
    try:
        payload = await response.json(content_type=None)
    except (ClientError, ValueError, json.JSONDecodeError) as err:
        raise RevenueCatPayloadError("RevenueCat returned non-JSON data") from err
    if not isinstance(payload, dict):
        raise RevenueCatPayloadError("RevenueCat returned a non-object payload")
    return payload


def _raise_response_error(
    status: int,
    headers: Any,
    payload: dict[str, Any],
) -> None:
    """Raise a typed exception for an unsuccessful response."""
    message = str(payload.get("message") or payload.get("type") or f"HTTP {status}")
    retry_after = _retry_after(headers, payload)

    if status in (401, 403):
        raise RevenueCatAuthError(message)
    if status == 429:
        raise RevenueCatRateLimitError(message, retry_after)
    if status in (423, 500, 502, 503, 504):
        raise RevenueCatTransientError(message, retry_after)
    raise RevenueCatError(message)


def parse_overview_metrics(
    payload: dict[str, Any],
    *,
    project_id: str,
) -> dict[str, RevenueCatSensorMetric]:
    """Parse the documented `/metrics/overview` response."""
    if payload.get("object") != "overview_metrics":
        raise RevenueCatPayloadError("Overview payload has unexpected object type")

    currency = _required_string(payload, "currency")
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, list):
        raise RevenueCatPayloadError("Overview payload is missing metrics")

    metrics: dict[str, RevenueCatSensorMetric] = {}
    for raw_metric in raw_metrics:
        if not isinstance(raw_metric, dict):
            raise RevenueCatPayloadError("Overview metric item is not an object")
        metric_id = _required_string(raw_metric, "id")
        name = _required_string(raw_metric, "name")
        value = _required_number(raw_metric, "value")
        unit = _required_string(raw_metric, "unit", allow_empty=True)
        period = _required_string(raw_metric, "period")
        key = f"{OVERVIEW_SENSOR_PREFIX}_{_slug(metric_id)}"
        kind = _metric_kind_from_unit(unit, currency)
        metrics[key] = RevenueCatSensorMetric(
            key=key,
            name=f"Overview {name}",
            value=value,
            metric_kind=kind,
            project_id=project_id,
            source="overview",
            currency=currency if kind == "monetary" else None,
            period_start=None,
            period_end=period,
            last_updated_from_revenuecat=raw_metric.get("last_updated_at_iso8601")
            or _millis_to_iso(raw_metric.get("last_updated_at")),
        )
    return metrics


def parse_revenue_metric(
    payload: dict[str, Any],
    *,
    project_id: str,
) -> RevenueCatSensorMetric:
    """Parse the documented `/metrics/revenue` response."""
    if payload.get("object") != "revenue_metric":
        raise RevenueCatPayloadError("Revenue payload has unexpected object type")

    currency = _required_string(payload, "currency")
    revenue_type = _required_string(payload, CONF_REVENUE_TYPE)
    return RevenueCatSensorMetric(
        key="revenue_28d",
        name="Revenue 28d",
        value=_required_number(payload, "value"),
        metric_kind="monetary",
        project_id=project_id,
        source="revenue_metric",
        currency=currency,
        revenue_type=revenue_type,
        period_start=_required_string(payload, "start_date"),
        period_end=_required_string(payload, "end_date"),
    )


def parse_chart_metric(
    payload: dict[str, Any],
    *,
    chart_name: str,
    project_id: str,
    currency: str,
    revenue_type: str,
) -> RevenueCatSensorMetric:
    """Parse latest summary value from a documented chart response."""
    if payload.get("object") != "chart_data":
        raise RevenueCatPayloadError(f"{chart_name} payload has unexpected object type")

    value, period_start, period_end = _latest_value_from_chart(chart_name, payload)
    kind = _chart_metric_kind(chart_name, payload)
    chart_currency = payload.get("yaxis_currency")
    metric_currency = (
        str(chart_currency) if kind == "monetary" and chart_currency else currency
    )
    selected_revenue_type = revenue_type if chart_name in REVENUE_TYPE_CHARTS else None

    return RevenueCatSensorMetric(
        key=CHART_SENSOR_KEYS[chart_name],
        name=CHART_DISPLAY_NAMES[chart_name],
        value=value,
        metric_kind=kind,
        project_id=project_id,
        source="chart",
        chart_id=chart_name,
        currency=metric_currency if kind == "monetary" else None,
        revenue_type=selected_revenue_type,
        period_start=period_start or _millis_to_iso(payload.get("start_date")),
        period_end=period_end or _millis_to_iso(payload.get("end_date")),
        last_updated_from_revenuecat=_millis_to_iso(payload.get("last_computed_at")),
        summary=_small_summary(payload.get("summary")),
    )


def _latest_value_from_chart(
    chart_name: str,
    payload: dict[str, Any],
) -> tuple[float | int | None, str | None, str | None]:
    """Extract the latest primary value from OpenAPI-declared chart shapes."""
    raw_values = payload.get("values")
    if not isinstance(raw_values, list):
        raise RevenueCatPayloadError(f"{chart_name} chart values are not a list")

    for point in reversed(raw_values):
        parsed = _value_from_point(chart_name, point, payload.get("measures"))
        if parsed is not None:
            return parsed

    summary_value = _numeric_from_summary(payload.get("summary"))
    if summary_value is not None:
        return (
            summary_value,
            _millis_to_iso(payload.get("start_date")),
            _millis_to_iso(payload.get("end_date")),
        )

    return (
        None,
        _millis_to_iso(payload.get("start_date")),
        _millis_to_iso(payload.get("end_date")),
    )


def _value_from_point(
    chart_name: str,
    point: Any,
    measures: Any,
) -> tuple[float | int, str | None, str | None] | None:
    """Parse one chart point."""
    if isinstance(point, dict):
        return _value_from_object_point(chart_name, point)
    if isinstance(point, list):
        return _value_from_array_point(chart_name, point, measures)
    raise RevenueCatPayloadError(f"{chart_name} chart point has unknown shape")


def _value_from_object_point(
    chart_name: str,
    point: dict[str, Any],
) -> tuple[float | int, str | None, str | None] | None:
    aliases = _primary_aliases(chart_name)
    for key in aliases:
        value = point.get(key)
        if _is_number(value):
            return value, _point_period_start(point), _point_period_end(point)

    for key, value in point.items():
        if key in _TIME_KEYS:
            continue
        if _is_number(value):
            return value, _point_period_start(point), _point_period_end(point)
    return None


def _value_from_array_point(
    chart_name: str,
    point: list[Any],
    measures: Any,
) -> tuple[float | int, str | None, str | None] | None:
    values = [value for value in point if _is_number(value)]
    if not values:
        return None

    period_start: str | None = None
    if _looks_like_timestamp(values[0]):
        period_start = _millis_or_seconds_to_iso(values[0])
        numeric_values = values[1:]
    else:
        numeric_values = values

    if not numeric_values:
        return None

    measure_index = _measure_index(chart_name, measures, len(numeric_values))
    if measure_index is not None:
        return numeric_values[measure_index], period_start, None

    if chart_name in PERCENTAGE_CHARTS:
        return numeric_values[-1], period_start, None
    return numeric_values[0], period_start, None


def _measure_index(chart_name: str, measures: Any, value_count: int) -> int | None:
    """Find a primary measure index when v3 chart measures are present."""
    if not isinstance(measures, list) or len(measures) != value_count:
        return None

    aliases = _primary_aliases(chart_name)
    for index, raw_measure in enumerate(measures):
        if not isinstance(raw_measure, dict):
            continue
        measure_text = " ".join(
            str(raw_measure.get(key, ""))
            for key in ("id", "name", "display_name", "key")
        ).lower()
        if any(alias.replace("_", " ") in measure_text for alias in aliases):
            return index
    return None


def _primary_aliases(chart_name: str) -> tuple[str, ...]:
    aliases = {
        "actives": ("value", "actives", "active_subscriptions", "count"),
        "actives_movement": ("value", "movement", "net_change", "count"),
        "actives_new": ("value", "new_subscriptions", "count"),
        "arr": ("value", "arr", "revenue", "proceeds"),
        "churn": ("churn_rate", "rate", "percentage", "value"),
        "conversion_to_paying": ("conversion_rate", "rate", "percentage", "value"),
        "customers_active": ("value", "customers_active", "active_customers", "count"),
        "customers_new": ("value", "customers_new", "new_customers", "count"),
        "mrr": ("value", "mrr", "revenue", "proceeds"),
        "mrr_movement": ("value", "movement", "mrr_movement", "net_change"),
        "refund_rate": ("refund_rate", "rate", "percentage", "value"),
        "revenue": ("value", "revenue", "proceeds"),
        "trial_conversion_rate": (
            "trial_conversion_rate",
            "rate",
            "percentage",
            "value",
        ),
        "trials": ("value", "trials", "active_trials", "count"),
        "trials_movement": ("value", "movement", "net_change", "count"),
        "trials_new": ("value", "trials_new", "new_trials", "count"),
    }
    return aliases.get(chart_name, ("value",))


_TIME_KEYS = {
    "date",
    "end",
    "end_date",
    "period",
    "start",
    "start_date",
    "time",
    "timestamp",
    "x",
}


def _numeric_from_summary(summary: Any) -> float | int | None:
    if not isinstance(summary, dict):
        return None
    for key in ("total", "average", "value"):
        value = summary.get(key)
        if _is_number(value):
            return value
    for value in summary.values():
        if _is_number(value):
            return value
    return None


def _small_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    small: dict[str, Any] = {}
    for key, value in summary.items():
        if _is_scalar(value):
            small[str(key)] = value
        if len(small) >= 8:
            break
    return small


def _point_period_start(point: dict[str, Any]) -> str | None:
    for key in ("period", "date", "start_date", "start", "time", "timestamp", "x"):
        value = point.get(key)
        period = _period_value(value)
        if period is not None:
            return period
    return None


def _point_period_end(point: dict[str, Any]) -> str | None:
    for key in ("end_date", "end"):
        value = point.get(key)
        period = _period_value(value)
        if period is not None:
            return period
    return None


def _period_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if _is_number(value) and _looks_like_timestamp(value):
        return _millis_or_seconds_to_iso(value)
    return None


def _required_string(
    payload: dict[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value):
        raise RevenueCatPayloadError(f"Payload is missing string field {key}")
    return value


def _required_number(payload: dict[str, Any], key: str) -> float | int:
    value = payload.get(key)
    if not _is_number(value):
        raise RevenueCatPayloadError(f"Payload is missing numeric field {key}")
    return value


def _chart_metric_kind(chart_name: str, payload: dict[str, Any]) -> str:
    if chart_name in MONETARY_CHARTS:
        return "monetary"
    if chart_name in PERCENTAGE_CHARTS or payload.get("yaxis") == "%":
        return "percentage"
    return "count"


def _metric_kind_from_unit(unit: str, currency: str) -> str:
    if unit == "%" or unit.lower() in {"percent", "percentage"}:
        return "percentage"
    if unit == "$" or unit.upper() == currency.upper():
        return "monetary"
    return "count"


def _retry_after(headers: Any, payload: dict[str, Any]) -> int | None:
    header_value = headers.get("Retry-After") if headers is not None else None
    if header_value is not None:
        try:
            return max(1, int(float(header_value)))
        except (TypeError, ValueError):
            pass

    backoff_ms = payload.get("backoff_ms")
    if _is_number(backoff_ms):
        return max(1, int(backoff_ms / 1000))
    return None


def _millis_to_iso(value: Any) -> str | None:
    if not _is_number(value):
        return None
    return datetime.fromtimestamp(value / 1000, UTC).isoformat()


def _millis_or_seconds_to_iso(value: float | int) -> str:
    divisor = 1000 if abs(value) > 10_000_000_000 else 1
    return datetime.fromtimestamp(value / divisor, UTC).isoformat()


def _looks_like_timestamp(value: float | int) -> bool:
    return abs(value) >= 946_684_800


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None
