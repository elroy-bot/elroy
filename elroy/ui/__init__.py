"""UI package for Elroy's terminal application.

Expose only stable top-level entry points here.
Module-specific types should usually be imported from their defining module.
"""

from .app import ElroyApp, main, make_app

__all__ = ["ElroyApp", "main", "make_app"]
