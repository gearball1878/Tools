"""Structured compatibility pipeline for legacy Symbol Wizard updates.

Active function definitions are split by domain under ``functions/``. The replay order remains centralized in ``pipeline.py`` because it encodes the wrapper composition order required to derive final canonical methods.
"""

from __future__ import annotations
