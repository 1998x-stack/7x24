"""Compatibility bridge; historical implementation lives under legacy/src.

Prefer `news24` for supported new workflows.
"""

from legacy.src.main import run_as_script

if __name__ == "__main__":
    run_as_script()
