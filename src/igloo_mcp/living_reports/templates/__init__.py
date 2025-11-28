"""Templates directory for living reports Quarto rendering.

This package contains Jinja2 templates used by the Quarto renderer
to generate report.qmd files from report outlines.

Also re-exports the report template functions for convenience.
"""

# Re-export the template functions from the sibling module
# This avoids the namespace collision issue
import importlib.util
import sys
from pathlib import Path

# Load templates.py directly since it shares namespace with this directory
_templates_file = Path(__file__).parent.parent / "templates.py"
_spec = importlib.util.spec_from_file_location(
    "igloo_mcp.living_reports._templates_mod",
    _templates_file,
    submodule_search_locations=[],
)
_templates_mod = importlib.util.module_from_spec(_spec)

# Set up the __package__ attribute to enable relative imports
_templates_mod.__package__ = "igloo_mcp.living_reports"

# Add parent package to sys.modules if needed
if "igloo_mcp.living_reports" not in sys.modules:
    import igloo_mcp.living_reports

    sys.modules["igloo_mcp.living_reports"] = igloo_mcp.living_reports

_spec.loader.exec_module(_templates_mod)

# Re-export
TEMPLATES = _templates_mod.TEMPLATES
get_template = _templates_mod.get_template
default = _templates_mod.default
monthly_sales = _templates_mod.monthly_sales
quarterly_review = _templates_mod.quarterly_review
deep_dive = _templates_mod.deep_dive
analyst_v1 = _templates_mod.analyst_v1

__all__ = [
    "TEMPLATES",
    "get_template",
    "default",
    "monthly_sales",
    "quarterly_review",
    "deep_dive",
    "analyst_v1",
]
