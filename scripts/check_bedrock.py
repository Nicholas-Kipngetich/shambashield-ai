"""Thin wrapper so the diagnostic can be run as `python scripts/check_bedrock.py`."""

from shambashield.bedrock_check import main

if __name__ == "__main__":
    raise SystemExit(main())
