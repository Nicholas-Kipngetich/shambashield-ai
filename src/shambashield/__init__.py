"""ShambaShield AI: multi-agent climate resilience advisory for smallholder farmers."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("shambashield-ai")
except PackageNotFoundError:  # pragma: no cover - source tree without install
    __version__ = "0.1.0"

__all__ = ["__version__"]
