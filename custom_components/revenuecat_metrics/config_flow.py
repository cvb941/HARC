"""Config flow for RevenueCat Metrics."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .api import RevenueCatApi, RevenueCatAuthError, RevenueCatError
from .const import (
    CONF_API_KEY,
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
    REVENUE_TYPES,
    SUPPORTED_CHARTS,
    SUPPORTED_CURRENCIES,
)

_LOGGER = logging.getLogger(__name__)


class RevenueCatMetricsConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a RevenueCat Metrics config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RevenueCatMetricsOptionsFlow:
        """Create the options flow."""
        return RevenueCatMetricsOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_CURRENCY] = user_input[CONF_CURRENCY].upper()
            errors = await _async_validate_input(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_PROJECT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"RevenueCat {user_input[CONF_PROJECT_ID]}",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_PROJECT_ID: user_input[CONF_PROJECT_ID],
                        CONF_CURRENCY: user_input[CONF_CURRENCY],
                        CONF_REVENUE_TYPE: user_input[CONF_REVENUE_TYPE],
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                        CONF_ENABLED_CHARTS: list(DEFAULT_ENABLED_CHARTS),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> FlowResult:
        """Handle reauthentication."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._reauth_entry = entry
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            data = dict(self._reauth_entry.data)
            data[CONF_API_KEY] = user_input[CONF_API_KEY]
            errors = await _async_validate_input(self.hass, data)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class RevenueCatMetricsOptionsFlow(config_entries.OptionsFlow):
    """Handle RevenueCat Metrics options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            interval = user_input[CONF_UPDATE_INTERVAL]
            if interval < MIN_UPDATE_INTERVAL_MINUTES:
                errors[CONF_UPDATE_INTERVAL] = "interval_too_low"
            else:
                user_input[CONF_CURRENCY] = user_input[CONF_CURRENCY].upper()
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry),
            errors=errors,
        )


async def _async_validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """Validate RevenueCat credentials and project."""
    api = RevenueCatApi(async_get_clientsession(hass), user_input[CONF_API_KEY])
    try:
        await api.async_validate_project(
            user_input[CONF_PROJECT_ID],
            user_input[CONF_CURRENCY],
            user_input[CONF_REVENUE_TYPE],
        )
    except RevenueCatAuthError:
        return {"base": "invalid_auth"}
    except RevenueCatError as err:
        _LOGGER.debug("RevenueCat validation failed: %s", err)
        return {"base": "cannot_connect"}
    return {}


def _user_schema() -> vol.Schema:
    """Return initial config flow schema."""
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_PROJECT_ID): str,
            vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): selector(
                {
                    "select": {
                        "mode": "dropdown",
                        "options": list(SUPPORTED_CURRENCIES),
                    }
                }
            ),
            vol.Required(CONF_REVENUE_TYPE, default=DEFAULT_REVENUE_TYPE): selector(
                {
                    "select": {
                        "mode": "dropdown",
                        "options": list(REVENUE_TYPES),
                    }
                }
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=DEFAULT_UPDATE_INTERVAL_MINUTES,
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)),
        }
    )


def _options_schema(config_entry: config_entries.ConfigEntry) -> vol.Schema:
    """Return options flow schema."""
    options = config_entry.options
    data = config_entry.data
    enabled_charts = options.get(
        CONF_ENABLED_CHARTS,
        data.get(CONF_ENABLED_CHARTS, DEFAULT_ENABLED_CHARTS),
    )

    return vol.Schema(
        {
            vol.Required(
                CONF_CURRENCY,
                default=options.get(
                    CONF_CURRENCY, data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
                ),
            ): selector(
                {
                    "select": {
                        "mode": "dropdown",
                        "options": list(SUPPORTED_CURRENCIES),
                    }
                }
            ),
            vol.Required(
                CONF_REVENUE_TYPE,
                default=options.get(
                    CONF_REVENUE_TYPE,
                    data.get(CONF_REVENUE_TYPE, DEFAULT_REVENUE_TYPE),
                ),
            ): selector(
                {
                    "select": {
                        "mode": "dropdown",
                        "options": list(REVENUE_TYPES),
                    }
                }
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=options.get(
                    CONF_UPDATE_INTERVAL,
                    data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES)),
            vol.Required(CONF_ENABLED_CHARTS, default=list(enabled_charts)): selector(
                {
                    "select": {
                        "mode": "list",
                        "multiple": True,
                        "options": list(SUPPORTED_CHARTS),
                    }
                }
            ),
        }
    )
