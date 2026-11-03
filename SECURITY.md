# Security policy

## Supported scope

The maintained code is the packaged `news24` runtime in `src/news24`. Scripts in `legacy/` are frozen experimental prototypes and have no security support guarantee.

## Reporting a vulnerability

Please **do not create a public issue with exploit details, real credentials, or private user news data**. Use GitHub's private vulnerability reporting feature for this repository when available (Security → Report a vulnerability). If that option is unavailable, contact the repository maintainers through a private channel instead of publishing sensitive details.

Helpful reports include the affected version/commit, a minimal reproduction with synthetic data, impact, and whether the issue can be triggered without a local authenticated operator.

## Security model and caveats

- The Web workbench binds **127.0.0.1 only**. A static long review token is suitable only for a trusted local workstation; it is not public/multi-user authentication.
- Never expose it through tunnels, reverse proxies, or unreviewed cloud services.
- Source feeds and model outputs are untrusted data, not executable instructions. Review and rendering are deliberately source-revision fenced and HTML inert.
- Backups may contain raw news snapshots, source metadata and analyst review notes; protect their filesystem access.
- The provider SDK is an opt-in extra. Rotate keys and review usage/cost separately from offline tests.

Do not claim deployment or real-model verification on the basis of repository CI.
