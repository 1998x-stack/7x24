# Contributing

Thanks for improving News24. Please keep contributions focused on the supported `src/news24` package; `legacy/` is frozen for comparisons and regression tests.

## Development setup

```bash
git clone https://github.com/1998x-stack/7x24.git
cd 7x24
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make lint typecheck test smoke
```

Canonical module owners and dependency rules are documented in [docs/architecture/overview.md](docs/architecture/overview.md). New features belong in domain/application/infrastructure/interfaces, **not** in a compatibility facade. Prefer focused PRs with a clear behavioral test and documentation updates over wholesale dependency or framework swaps.

Before opening a PR:
- Verify all offline tests, and run Playwright when changing the Web interface.
- Do not commit API keys, access tokens, local news databases, user data, or provider credentials.
- Add a migration and an upgrade test for schema changes; never mutate an existing migration.
- Explain impact, rollback, data provenance and any remaining production verification gaps.
- Add an ADR when changing a cross-module contract or deployment architecture.

For suspected security vulnerabilities, follow [SECURITY.md](SECURITY.md) rather than filing a public issue. For ordinary bugs, use the issue templates.
