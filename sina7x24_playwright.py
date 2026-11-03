"""Legacy standalone command compatibility; the implementation is archived in legacy/."""

from pathlib import Path
from runpy import run_path

if __name__ == "__main__":
    run_path(str(Path(__file__).resolve().parent / "legacy" / "sina7x24_playwright.py"), run_name="__main__")
