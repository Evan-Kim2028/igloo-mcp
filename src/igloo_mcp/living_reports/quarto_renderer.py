"""Quarto renderer for living reports.

This module provides functionality to render living reports into high-quality
artifacts (HTML, PDF, etc.) using Quarto. Quarto is treated as an optional
dependency that enhances the living reports system.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import shutil
import subprocess
from collections import namedtuple
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from igloo_mcp.path_utils import find_repo_root

# Define the RenderResult namedtuple
RenderResult = namedtuple("RenderResult", ["output_paths", "stdout", "stderr", "warnings"])


class QuartoNotFoundError(Exception):
    """Raised when Quarto binary cannot be found or is not installed."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize the error with a helpful message.

        Args:
            message: Custom error message (optional)
        """
        if message is None:
            message = (
                "Quarto not found. Install Quarto from https://quarto.org/docs/get-started/ "
                "or set IGLOO_QUARTO_BIN environment variable to the path of quarto executable."
            )
        super().__init__(message)


class QuartoRenderer:
    """Renderer for converting living reports to Quarto artifacts.

    This class handles the detection of Quarto installation and rendering
    of living reports into various output formats (HTML, PDF, Markdown).
    """

    # Class-level cache for Quarto version to avoid repeated subprocess calls
    _cached_version: str | None = None
    _cached_bin_path: str | None = None

    @classmethod
    def detect(cls) -> QuartoRenderer:
        """Detect Quarto installation and return a renderer instance.

        Checks for Quarto in the following order:
        1. IGLOO_QUARTO_BIN environment variable
        2. PATH using shutil.which('quarto')

        Returns:
            QuartoRenderer instance if Quarto is found

        Raises:
            QuartoNotFoundError: If Quarto cannot be detected
        """
        # Check environment variable first
        bin_path = os.environ.get("IGLOO_QUARTO_BIN")

        if bin_path:
            # Verify the specified path exists and is executable
            if not os.path.isfile(bin_path):
                raise QuartoNotFoundError(f"IGLOO_QUARTO_BIN path does not exist: {bin_path}")
            if not os.access(bin_path, os.X_OK):
                raise QuartoNotFoundError(f"IGLOO_QUARTO_BIN path is not executable: {bin_path}")
        else:
            # Check PATH
            bin_path = shutil.which("quarto")
            if not bin_path:
                raise QuartoNotFoundError

        # Cache the successful detection
        cls._cached_bin_path = bin_path

        # Get and cache version (only once)
        if cls._cached_version is None:
            try:
                result = subprocess.run(
                    [bin_path, "--version"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    cls._cached_version = result.stdout.strip()
                else:
                    cls._cached_version = "unknown"
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                cls._cached_version = "unknown"

        return cls()

    @property
    def bin_path(self) -> str:
        """Get the path to the Quarto binary."""
        if self._cached_bin_path is None:
            raise QuartoNotFoundError("Quarto not detected. Call detect() first.")
        return self._cached_bin_path

    @property
    def version(self) -> str:
        """Get the cached Quarto version."""
        return self._cached_version or "unknown"

    def _parse_version_tuple(self) -> tuple[int, int] | None:
        """Parse version string into (major, minor) tuple.

        Returns:
            Tuple of (major, minor) integers, or None if parsing fails
        """
        if self.version == "unknown" or not self.version.startswith("1."):
            return None
        try:
            parts = self.version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return (major, minor)
        except (ValueError, IndexError):
            return None

    def render(
        self,
        report_dir: str | Path,
        format: str,
        options: dict[str, Any] | None = None,
        outline: Any | None = None,
        datasets: dict[str, Any] | None = None,
        hints: dict[str, Any] | None = None,
    ) -> RenderResult:
        """Render a living report using Quarto.

        Args:
            report_dir: Directory containing the report outline.json
            format: Output format ('html', 'pdf', 'markdown', etc.)
            options: Additional Quarto options (toc, theme, etc.)
            outline: Outline object (if None, loaded from report_dir)
            datasets: Dataset sources dict (if None, loaded from report_dir)
            hints: Render hints from outline.metadata

        Returns:
            RenderResult with output paths, stdout, stderr, and warnings

        Raises:
            QuartoNotFoundError: If Quarto is not available
            RuntimeError: If rendering fails
        """
        report_dir = Path(report_dir).resolve()
        if not report_dir.exists():
            raise ValueError(f"Report directory does not exist: {report_dir}")

        # Load data if not provided
        if outline is None:
            outline_path = report_dir / "outline.json"
            if not outline_path.exists():
                raise ValueError(f"Outline file not found: {outline_path}")
            with open(outline_path, encoding="utf-8") as f:
                outline_data = json.load(f)
                # Convert back to Outline object if needed
                from .models import Outline

                outline = Outline(**outline_data)

        if datasets is None:
            datasets_path = report_dir / "dataset_sources.json"
            if datasets_path.exists():
                with open(datasets_path, encoding="utf-8") as f:
                    datasets = json.load(f)
            else:
                datasets = {}

        if hints is None:
            hints = outline.metadata.get("render_hints", {}) if hasattr(outline, "metadata") else {}

        # Generate the QMD file
        self._generate_qmd_file(report_dir, format, options or {}, outline, datasets, hints)

        # Build Quarto command
        cmd = [self.bin_path, "render", "report.qmd", "--to", format]

        # Add options
        if options:
            if options.get("toc"):
                cmd.append("--toc")
            if options.get("code_folding"):
                cmd.append("--code-fold")
            if "theme" in options:
                cmd.extend(["--theme", str(options["theme"])])

        # Run Quarto
        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=str(report_dir),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Quarto render timed out after 5 minutes") from None

        # Parse results
        warnings = []
        output_paths = []

        if result.returncode != 0:
            # Check for version warnings
            version_tuple = self._parse_version_tuple()
            if version_tuple is not None:
                major, minor = version_tuple
                if major < 1 or (major == 1 and minor < 4):
                    warnings.append("Quarto version < 1.4 detected; upgrade for better Python chunk support.")

            # Check for missing datasets
            if datasets and any(not datasets.get(insight_id) for insight_id in getattr(outline, "insights", [])):
                warnings.append("Some datasets are missing; charts/tables may not render properly.")

            raise RuntimeError(f"Quarto render failed: {result.stderr}")

        # Parse output paths from stdout (typically contains "Output created: path/to/file.html")
        for line in result.stdout.splitlines():
            if "Output created:" in line:
                path_part = line.split("Output created:", 1)[1].strip()
                # Resolve relative to report_dir
                output_path = (report_dir / path_part).resolve()
                if output_path.exists():
                    output_paths.append(str(output_path))

        # Generate warnings
        version_tuple = self._parse_version_tuple()
        if version_tuple is not None:
            major, minor = version_tuple
            if major < 1 or (major == 1 and minor < 4):
                warnings.append("Upgrade to Quarto 1.4+ for improved Python execution support.")

        return RenderResult(
            output_paths=output_paths,
            stdout=result.stdout,
            stderr=result.stderr,
            warnings=warnings,
        )

    def _generate_qmd_file(
        self,
        report_dir: Path,
        format: str,
        options: dict[str, Any],
        outline: Any,
        datasets: dict[str, Any],
        hints: dict[str, Any],
    ) -> None:
        """Generate the report.qmd file from the outline.

        Args:
            report_dir: Report directory
            format: Output format
            options: Render options
            outline: Outline object
            datasets: Dataset sources
            hints: Render hints
        """
        # Find the template directory - try multiple strategies
        template_dir: Path | None = None
        repo_root = find_repo_root()
        attempted_paths: list[str] = []

        # Strategy 1: Use importlib.resources (works when installed as package)
        try:
            templates_ref = importlib.resources.files("igloo_mcp.living_reports.templates")
            template_file_ref = templates_ref / "report.qmd.j2"
            # Check if the template file exists in the package
            if template_file_ref.is_file():
                # Use as_file() to get a real filesystem Path
                # For package files (not in zip), this returns a persistent Path
                try:
                    template_file_path = importlib.resources.as_file(template_file_ref)
                    # Enter context to get the Path, resolve to absolute path, then store outside context
                    # For normal package installations, the Path persists after context exit
                    with template_file_path as template_file:
                        candidate_dir = template_file.parent.resolve()
                        # Resolve to absolute path and verify it exists
                        if candidate_dir.exists() and (candidate_dir / "report.qmd.j2").exists():
                            # Store absolute path outside context (works for package files)
                            template_dir = candidate_dir
                            attempted_paths.append(f"Package location (importlib.resources): {template_dir}")
                except (OSError, ValueError, TypeError) as e:
                    attempted_paths.append(f"Package location (importlib.resources): Failed - {e}")
        except (ImportError, ModuleNotFoundError, AttributeError) as e:
            attempted_paths.append(f"Package location (importlib.resources): Not available - {e}")

        # Strategy 2: Use repo root (works in development)
        if template_dir is None or not template_dir.exists():
            candidate = repo_root / "src" / "igloo_mcp" / "living_reports" / "templates"
            attempted_paths.append(f"Repo root: {candidate}")
            if candidate.exists():
                template_dir = candidate

        # Strategy 3: Use current file location as fallback
        if template_dir is None or not template_dir.exists():
            candidate = Path(__file__).parent / "templates"
            attempted_paths.append(f"File-relative: {candidate}")
            if candidate.exists():
                template_dir = candidate

        if template_dir is None or not template_dir.exists():
            error_msg = (
                "Template directory not found. Attempted paths:\n"
                + "\n".join(f"  - {path}" for path in attempted_paths)
                + f"\nCurrent working directory: {Path.cwd()}\n"
                + f"Repo root: {repo_root}\n"
                + f"__file__ location: {Path(__file__)}"
            )
            raise RuntimeError(error_msg)

        # Set up Jinja2 environment
        env = Environment(loader=FileSystemLoader(str(template_dir)))  # noqa: S701 - QMD template, not HTML
        template = env.get_template("report.qmd.j2")

        # Prepare template context
        # Extract query_provenance from hints if provided
        query_provenance = hints.get("query_provenance", {}) if isinstance(hints, dict) else {}

        context = {
            "outline": outline,
            "datasets": datasets,
            "hints": hints,
            "format": format,
            "options": options,
            "query_provenance": query_provenance,
        }

        # Render template
        qmd_content = template.render(**context)

        # Write to report.qmd
        qmd_path = report_dir / "report.qmd"
        with open(qmd_path, "w", encoding="utf-8") as f:
            f.write(qmd_content)
