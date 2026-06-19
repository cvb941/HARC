# HARC

Home Assistant RevenueCat metrics custom integration.

`revenuecat_metrics` exposes RevenueCat API v2 Charts and Overview metrics as Home Assistant sensor entities. The repository is named HARC to avoid conflicting with the separate HAHA project. It is built for HACS-style installation and intentionally has no dependency on AWTRIX or any display-specific integration.

## Status

This is an early custom integration. RevenueCat's Charts API supports chart-specific response shapes, so the parser is intentionally conservative and may need updates if RevenueCat changes chart payloads.

## Features

- UI config flow. No YAML setup.
- One Home Assistant device per RevenueCat project.
- Uses Home Assistant's async HTTP session and `DataUpdateCoordinator`.
- Supports currency selection, RevenueCat revenue type selection, update interval, and enabled chart selection.
- Handles RevenueCat authentication failures with Home Assistant reauth.
- Handles rate limiting without logging or exposing the API key.
- Redacts the API key from diagnostics.

## RevenueCat requirements

Create a RevenueCat API v2 secret key with these permissions:

- `charts_metrics:overview:read`
- `charts_metrics:charts:read`

The project ID is visible in RevenueCat dashboard URLs such as:

```text
https://app.revenuecat.com/projects/proj_XXXXXXXXXXXX/apps
```

Do not put the secret key in source files, README examples, dashboards, or browser-side code.

## Installation

### HACS custom repository

1. Add `cvb941/HARC` in HACS as a custom repository.
2. Select category `Integration`.
3. Install `RevenueCat Metrics`.
4. Restart Home Assistant.
5. Go to Settings > Devices & services > Add integration.
6. Search for `RevenueCat Metrics`.

### Manual

Copy the integration directory into Home Assistant:

```text
/config/custom_components/revenuecat_metrics
```

The source path in this repository is:

```text
custom_components/revenuecat_metrics
```

Restart Home Assistant, then add the integration from Settings > Devices & services.

## Configuration

The config flow asks for:

- RevenueCat API v2 secret key
- Project ID
- Currency, default `EUR`
- Revenue type, default `revenue`
- Update interval, default 60 minutes, minimum 15 minutes

Options can later change:

- Currency
- Revenue type: `revenue`, `revenue_net_of_taxes`, or `proceeds`
- Update interval
- Enabled chart set

## Example sensors

Entity IDs depend on Home Assistant's entity registry, but the default names produce sensors such as:

- `sensor.revenuecat_mrr`
- `sensor.revenuecat_arr`
- `sensor.revenuecat_revenue_28d`
- `sensor.revenuecat_active_subscriptions`
- `sensor.revenuecat_new_customers`
- `sensor.revenuecat_active_customers`
- `sensor.revenuecat_trial_conversion_rate`
- `sensor.revenuecat_churn_rate`
- `sensor.revenuecat_refund_rate`

Attributes include the project ID, chart ID where applicable, currency, revenue type, period boundaries, and RevenueCat's last computed timestamp.

## AWTRIX automation example

This integration only exposes sensors. To show MRR on AWTRIX, use a Home Assistant automation against your AWTRIX entity, for example:

```yaml
alias: AWTRIX RevenueCat MRR
mode: single
triggers:
  - trigger: state
    entity_id: sensor.revenuecat_mrr
actions:
  - action: awtrix.custom_app
    target:
      entity_id: light.awtrix
    data:
      name: revenuecat_mrr
      text: "MRR {{ states('sensor.revenuecat_mrr') }} {{ state_attr('sensor.revenuecat_mrr', 'currency') }}"
      icon: "1234"
```

## Notes on chart parsing

RevenueCat's OpenAPI schema documents chart data as chart-specific time series where `values` can contain arrays of numbers or objects with timestamps and values. The integration parses documented object values, timestamped numeric arrays, summary fallback values, and RevenueCat v3 measures when present. Unknown shapes fail closed so Home Assistant does not publish invented metric values.

## Development

Install test dependencies and run tests:

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest
```

Run a basic syntax check:

```bash
python3 -m compileall custom_components tests
```
