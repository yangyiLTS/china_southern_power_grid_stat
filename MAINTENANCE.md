# Benjamin maintained CSG integration

This branch is a locally maintained derivative of
`CubicPill/china_southern_power_grid_stat` v1.2.0 under GPL-3.0. It is not an
official China Southern Power Grid integration and is not yet deployed to the
Home Assistant production instance.

## Source policy

- Keep `origin` fetch-only and pin every production deployment to a reviewed
  commit.
- Cherry-pick narrow fixes with original authorship instead of replacing the
  component with an unreviewed fork.
- Never add a network destination outside the fixed `95598.csg.cn` allowlist.
- Never persist the user's login password or write tokens, full account
  numbers, names, addresses, or API response bodies to logs.
- Treat the browser session as validation evidence only; never extract cookies,
  browser storage, or login tokens.

## Imported fixes

| Source commit | Purpose |
| --- | --- |
| `elvinsophus@3837bc4` | Home Assistant 2025.12+ options flow, reauth and Python 3.14 compatibility |
| `seagaruda@b67718d` | 30-second HTTP timeout and explicit client imports |
| `L1yp@2657254` | Original graceful handling when yesterday's usage is not published; superseded locally by removal of the retired endpoint |

## Local fixes

- Route SMS sessions through the handheld API and QR sessions through the web
  API instead of mixing the two session channels.
- Keep WeChat on the legacy QR endpoint, while the CSG App and Alipay use the
  current `/mp/w2/wx/userauth/user/manage/*` QR service found in the official
  South Grid web client `1.6.230`.
- Persist an allowlisted API profile name, never a caller-supplied URL.
- Stop persisting the interactive login password and stop logging API payloads
  and full response bodies.
- Copy nested config-entry mappings before modification for current Home
  Assistant immutable config-entry data.
- Use the current online-hall AES material for web-profile requests and decrypt
  responses when the service marks them with `need-decrypto`.
- Route current user, metering-point, monthly usage, balance and annual-analysis
  calls according to the encryption flags in the official web client.
- Remove the retired `queryDayElectricChargeByMPoint` and
  `queryDayElectricByMPointYesterday` calls. Monthly cost now comes from
  `queryDayElectricByMPoint.totalElectricity`; yesterday is derived by matching
  the exact date in that endpoint's daily results.
- Accept both the current object-shaped balance response and the legacy
  one-item-list response during migration.
- Send the metering-point number required by the current annual-analysis call.
- Mask phone numbers and electricity-account identifiers in integration logs.

## Current data limitations

- South Grid documents daily data as publishing within T+3 days. A missing
  yesterday value is normal and must not be replaced by the latest available
  day's value.
- The current web client no longer exposes a dedicated daily-cost API. Monthly
  total cost remains supported, while per-day cost and the latest-day-cost
  sensor stay unavailable unless the maintained monthly response supplies a
  `charge` field.
- Ladder fields are treated as optional because the current web UI uses a
  separate advisory endpoint rather than the retired daily-cost response.

## Acceptance gate before production

1. Unit tests and static checks pass.
2. The component imports in the exact Home Assistant production image.
3. A backup and executable rollback are prepared.
4. A fresh QR login returns exactly one bound electricity account.
5. At least one real usage request succeeds and creates valid energy sensors.
6. Home Assistant restarts cleanly and the account still refreshes.
