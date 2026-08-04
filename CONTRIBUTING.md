# Contributing

Thank you for helping maintain this integration.

## Before opening an issue

- Confirm the latest release is installed and Home Assistant has been restarted.
- Search existing issues for the same province, login method and symptom.
- Describe whether the failure is login, account discovery, balance, daily
  usage or annual analysis.
- Redact every phone number, account number, name, address, QR code, token and
  raw response body.

## Development setup

```sh
uv sync --dev
uv run ruff check .
uv run pytest -q
```

Keep changes narrow and use conventional commit subjects such as `fix:`,
`feat:`, `test:` or `docs:`. Add a regression test for API routing or parsing
changes.

## Pull requests

1. Explain the observed current behavior and the intended behavior.
2. Identify the official client evidence or minimized response shape used to
   justify an API change without posting private payloads.
3. Preserve the `95598.csg.cn` destination allowlist.
4. Do not add password persistence, credential logging, full API dumps or local
   estimates presented as official charges.
5. Update `CHANGELOG.md` for user-visible changes.

By contributing, you agree that your contribution is licensed under GPL-3.0.
