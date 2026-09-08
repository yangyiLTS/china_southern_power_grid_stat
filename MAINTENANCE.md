# Maintenance policy

This repository is a community-maintained derivative of
`CubicPill/china_southern_power_grid_stat` under GPL-3.0. It is not an official
China Southern Power Grid integration and is not presented as an official
continuation by the original maintainer.

## Source and attribution

- Preserve the original Git history, license and author attribution.
- Keep the original repository configured as `upstream` and review its changes.
- Cherry-pick narrow fixes with original authorship when importing from forks.
- Record user-visible behavior changes in `CHANGELOG.md`.

Imported maintenance work currently includes:

| Source | Purpose |
| --- | --- |
| `elvinsophus@3837bc4` | Current HA options flow, reauth and Python 3.14 compatibility |
| `seagaruda@b67718d` | Request timeout and explicit client imports |
| `L1yp@2657254` | Graceful handling when yesterday's data is not published |

## Security boundary

- Network destinations stay on the fixed `95598.csg.cn` allowlist.
- Never persist an interactive login password.
- Never log tokens, full account numbers, names, addresses or API bodies.
- Mask account-like identifiers before diagnostics leave the process.
- Browser sessions may be used to validate the official UI, but cookies,
  browser storage and login tokens must not be extracted.
- New endpoints require evidence from the current official client and a
  minimized request/response contract test before production use.

## API maintenance

The current implementation separates handheld and Web session profiles. QR
sessions use the Web profile and the current online-hall encryption material;
SMS sessions use the handheld profile. Callers persist only an allowlisted
profile name, never a caller-supplied URL.

The retired `queryDayElectricChargeByMPoint` and
`queryDayElectricByMPointYesterday` routes are intentionally absent. Shenzhen
accounts whose area code begins with `09` use the official client's
`charge/queryElectricityCalendar` route; other regions continue to use
`queryDayElectricByMPoint`. Yesterday's value is derived only from an exact date
match in the corresponding monthly response. Annual totals and monthly
annual-analysis rows come from `getAnalyzeFeeDetails`.

Missing fields remain unavailable by default. The optional Shenzhen residential
tariff model may fill a missing charge only when the user enables it, and every
calculated value must remain distinguishable from an official value through
explicit estimate and source attributes. It must never overwrite official
current or historical charges.

## Release gate

1. `uv run ruff check .` and `uv run pytest -q` pass.
2. HACS and hassfest validation pass.
3. The component imports in the target Home Assistant image.
4. A fresh QR flow completes automatically and discovers linked accounts.
5. Real balance, usage and annual-analysis calls succeed without sensitive logs.
6. A production backup and executable rollback exist before deployment.
7. The release contains no credentials, private account data or captured API
   response bodies.
