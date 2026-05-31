"""Generator package — Module 2 of the Interstellar Essential pipeline."""

from .generate import generate
from .csharp_strategies import SPECS, list_specs

__all__ = ["generate", "SPECS", "list_specs"]
