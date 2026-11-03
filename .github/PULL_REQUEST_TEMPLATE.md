## Summary

Describe the user-facing or engineering change and which canonical module owns it.

## Verification

- [ ] `make lint typecheck test smoke`
- [ ] `make browser` (for web/API changes) or explain why not applicable
- [ ] Wheel resources checked (for packaging/migration changes)
- [ ] Schema compatibility and rollback considered
- [ ] No user data, API keys, credentials or source secrets committed

## Risk and data provenance

What might regress? How can this be rolled back? Which source/model limitations remain unverified?

## Related issue / ADR

Issue # / ADR link:
