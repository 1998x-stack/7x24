# Legacy implementation (frozen)

This folder preserves the pre-V0.2 standalone scripts, the original pluggable src.* pipeline, and prototype reporting artifacts for historical comparison. It is not the supported News24 runtime and is not included in the standard installable distribution.

To execute legacy code from a repository checkout, install pip install -e '.[legacy]' and run python -m legacy.src.main or python legacy/sina7x24_playwright.py. Compatibility launchers remain at the repository root for existing operators.

Legacy code can have unresolved errors, old API assumptions and incomplete safety guards. Do not use as a production source and do not add new product features here. The primary CLI is news24; all new development belongs in src/news24.

The isolated legacy regression suite lives in tests/legacy/ and runs in CI separately.
