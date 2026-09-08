# Changelog

All notable changes to this maintained fork are documented here. The format is
based on Keep a Changelog and releases follow semantic versioning where the
upstream component version permits it.

## [Unreleased]

### Fixed

- Route Shenzhen daily usage and exact-yesterday lookups through the regional
  electricity-calendar API used by the official client.

## [1.4.0] - 2026-08-05

### Added

- Expose a rolling four-year `history_by_month` attribute on the current-year
  usage sensor. Every row keeps the official month, usage and charge returned
  by annual analysis, allowing dashboards to switch between daily month views
  and historical year views without estimating missing daily charges.

## [1.3.1] - 2026-08-05

### Added

- Automatic QR status polling in the Home Assistant progress flow.
- Automatic linked-account discovery after QR login.
- Home Assistant reauthentication flow and a deduplicated persistent
  notification when the login session expires.
- Routing, encryption and response-shape regression tests for current Web APIs.

### Changed

- Route QR sessions through the maintained Web API profile and SMS sessions
  through the handheld profile.
- Update the current CSG App, WeChat and Alipay QR endpoints.
- Rotate an unscanned QR after five minutes as a local stale-code safeguard.
- Use the current annual-analysis request parameters and balance response shape.
- Read monthly usage from the maintained combined daily endpoint.

### Fixed

- Home Assistant 2025.12+ options-flow and Python 3.14 compatibility.
- Current Web AES response decryption and immutable config-entry updates.
- A crash when yesterday's usage has not yet been published.
- Sensitive phone, account and API payload logging.

### Removed

- Calls to retired daily-charge and dedicated-yesterday endpoints.
- Persistence of the interactive login password.

## [1.2.0] - 2024-09-18

Original upstream release. See the upstream Git history for earlier changes.

[1.4.0]: https://github.com/benj-tang/china_southern_power_grid_stat/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/benj-tang/china_southern_power_grid_stat/compare/v1.2.0...v1.3.1
[1.2.0]: https://github.com/CubicPill/china_southern_power_grid_stat/releases/tag/v1.2.0
