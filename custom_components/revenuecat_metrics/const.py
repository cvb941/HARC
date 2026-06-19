"""Constants for the RevenueCat Metrics integration."""

from __future__ import annotations

DOMAIN = "revenuecat_metrics"
NAME = "RevenueCat Metrics"
VERSION = "0.1.2"

API_BASE_URL = "https://api.revenuecat.com/v2"
API_TIMEOUT_SECONDS = 30

CONF_API_KEY = "api_key"
CONF_PROJECT_ID = "project_id"
CONF_CURRENCY = "currency"
CONF_REVENUE_TYPE = "revenue_type"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ENABLED_CHARTS = "enabled_charts"

DEFAULT_CURRENCY = "EUR"
DEFAULT_REVENUE_TYPE = "revenue"
DEFAULT_UPDATE_INTERVAL_MINUTES = 60
MIN_UPDATE_INTERVAL_MINUTES = 15
CHART_LOOKBACK_DAYS = 90
REVENUE_WINDOW_DAYS = 28

REVENUE_TYPES = ("revenue", "revenue_net_of_taxes", "proceeds")

SUPPORTED_CURRENCIES = (
    "USD",
    "EUR",
    "GBP",
    "AUD",
    "CAD",
    "JPY",
    "BRL",
    "KRW",
    "CNY",
    "MXN",
    "SEK",
    "PLN",
    "NZD",
    "CHF",
)

SUPPORTED_CHARTS = (
    "mrr",
    "arr",
    "mrr_movement",
    "revenue",
    "actives",
    "actives_movement",
    "actives_new",
    "customers_new",
    "customers_active",
    "trials",
    "trials_new",
    "trials_movement",
    "churn",
    "refund_rate",
    "trial_conversion_rate",
    "conversion_to_paying",
)

DEFAULT_ENABLED_CHARTS = (
    "mrr",
    "arr",
    "revenue",
    "actives",
    "customers_new",
    "customers_active",
    "trials",
    "trial_conversion_rate",
    "churn",
    "refund_rate",
    "conversion_to_paying",
)

REVENUE_TYPE_CHARTS = {"arr", "mrr", "mrr_movement", "revenue"}

CHART_SENSOR_KEYS = {
    "actives": "active_subscriptions",
    "actives_movement": "active_subscriptions_movement",
    "actives_new": "new_subscriptions",
    "arr": "arr",
    "churn": "churn_rate",
    "conversion_to_paying": "conversion_to_paying_rate",
    "customers_active": "active_customers",
    "customers_new": "new_customers",
    "mrr": "mrr",
    "mrr_movement": "mrr_movement",
    "refund_rate": "refund_rate",
    "revenue": "revenue_latest_period",
    "trial_conversion_rate": "trial_conversion_rate",
    "trials": "active_trials",
    "trials_movement": "trials_movement",
    "trials_new": "new_trials",
}

CHART_DISPLAY_NAMES = {
    "actives": "Active Subscriptions",
    "actives_movement": "Active Subscriptions Movement",
    "actives_new": "New Subscriptions",
    "arr": "ARR",
    "churn": "Churn Rate",
    "conversion_to_paying": "Conversion To Paying",
    "customers_active": "Active Customers",
    "customers_new": "New Customers",
    "mrr": "MRR",
    "mrr_movement": "MRR Movement",
    "refund_rate": "Refund Rate",
    "revenue": "Revenue Latest Period",
    "trial_conversion_rate": "Trial Conversion Rate",
    "trials": "Active Trials",
    "trials_movement": "Trials Movement",
    "trials_new": "New Trials",
}

MONETARY_CHARTS = {"arr", "mrr", "mrr_movement", "revenue"}
PERCENTAGE_CHARTS = {
    "churn",
    "conversion_to_paying",
    "refund_rate",
    "trial_conversion_rate",
}

OVERVIEW_SENSOR_PREFIX = "overview"

ATTR_PROJECT_ID = "project_id"
ATTR_CHART_ID = "chart_id"
ATTR_CURRENCY = "currency"
ATTR_REVENUE_TYPE = "revenue_type"
ATTR_PERIOD_START = "period_start"
ATTR_PERIOD_END = "period_end"
ATTR_LAST_UPDATED_FROM_REVENUECAT = "last_updated_from_revenuecat"
ATTR_SOURCE = "source"
