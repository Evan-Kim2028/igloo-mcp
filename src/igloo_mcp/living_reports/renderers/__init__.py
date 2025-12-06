"""Renderers for living reports.

This module provides different rendering backends for living reports.
"""

from __future__ import annotations

from .html_standalone import HTMLStandaloneRenderer
from .markdown import MarkdownRenderer

__all__ = ["HTMLStandaloneRenderer", "MarkdownRenderer"]
