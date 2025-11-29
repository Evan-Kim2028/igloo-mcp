"""Tests for QuartoRenderer functionality."""

from __future__ import annotations

import importlib.resources
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from igloo_mcp.living_reports.models import Insight, Section
from igloo_mcp.living_reports.quarto_renderer import (
    QuartoNotFoundError,
    QuartoRenderer,
    RenderResult,
)
from tests.helpers.outline_factory import create_test_outline


@pytest.fixture(autouse=True)
def reset_quarto_cache():
    """Reset QuartoRenderer cache before each test for isolation.

    This prevents cache pollution between tests where one test's
    cached_bin_path or cached_version affects another test's expectations.
    """
    # Reset cache before test
    QuartoRenderer._cached_bin_path = None
    QuartoRenderer._cached_version = None
    yield
    # Reset cache after test (cleanup)
    QuartoRenderer._cached_bin_path = None
    QuartoRenderer._cached_version = None


class TestQuartoRenderer:
    """Test QuartoRenderer class."""

    def test_detect_with_env_var(self):
        """Test detection using IGLOO_QUARTO_BIN environment variable."""
        with patch.dict(os.environ, {"IGLOO_QUARTO_BIN": "/custom/quarto"}):
            with patch("os.path.isfile", return_value=True):
                with patch("os.access", return_value=True):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(stdout="1.4.0\n", returncode=0)

                        renderer = QuartoRenderer.detect()

                        assert isinstance(renderer, QuartoRenderer)
                        assert QuartoRenderer._cached_bin_path == "/custom/quarto"
                        assert QuartoRenderer._cached_version == "1.4.0"

    def test_detect_with_path(self):
        """Test detection using PATH."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/quarto"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(stdout="1.3.0\n", returncode=0)

                    renderer = QuartoRenderer.detect()

                    assert isinstance(renderer, QuartoRenderer)
                    assert QuartoRenderer._cached_bin_path == "/usr/bin/quarto"
                    assert QuartoRenderer._cached_version == "1.3.0"

    def test_detect_quarto_not_found(self):
        """Test detection when Quarto is not found."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
                with pytest.raises(QuartoNotFoundError) as exc_info:
                    QuartoRenderer.detect()

                assert "Quarto not found" in str(exc_info.value)

    def test_detect_invalid_env_path(self):
        """Test detection with invalid IGLOO_QUARTO_BIN path."""
        with patch.dict(os.environ, {"IGLOO_QUARTO_BIN": "/invalid/path"}):
            with patch("os.path.isfile", return_value=False):
                with pytest.raises(QuartoNotFoundError) as exc_info:
                    QuartoRenderer.detect()

                assert "does not exist" in str(exc_info.value)

    def test_detect_non_executable_env_path(self):
        """Test detection with non-executable IGLOO_QUARTO_BIN path."""
        with patch.dict(os.environ, {"IGLOO_QUARTO_BIN": "/not/executable"}):
            with patch("os.path.isfile", return_value=True):
                with patch("os.access", return_value=False):
                    with pytest.raises(QuartoNotFoundError) as exc_info:
                        QuartoRenderer.detect()

                    assert "not executable" in str(exc_info.value)

    def test_render_success(self):
        """Test successful rendering."""
        # Create a mock renderer
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            outline_file = report_dir / "outline.json"
            qmd_file = report_dir / "report.qmd"

            # Create mock outline using proper Outline model
            import uuid

            from igloo_mcp.living_reports.models import Insight, Section

            sec_id = str(uuid.uuid4())
            insight_id = str(uuid.uuid4())

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Test Report",
                sections=[
                    Section(
                        section_id=sec_id,
                        title="Section 1",
                        order=0,
                        insight_ids=[insight_id],
                    )
                ],
                insights=[Insight(insight_id=insight_id, summary="Test insight", importance=5)],
                metadata={},
            )

            # Save as dict to file
            with open(outline_file, "w") as f:
                json.dump(outline.model_dump(), f)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Output created: report.html\n", stderr="")

                # Create the output file that Quarto would create
                # (renderer checks if file exists before adding to output_paths)
                (report_dir / "report.html").write_text("<html>Test</html>")

                result = renderer.render(
                    report_dir=str(report_dir),
                    format="html",
                    options={"toc": True},
                    outline=outline,
                    datasets={},
                    hints={},
                )

                assert isinstance(result, RenderResult)
                # Use resolved path to handle macOS /var -> /private/var symlink
                expected_path = str((report_dir / "report.html").resolve())
                assert result.output_paths == [expected_path]
                assert "Output created" in result.stdout
                assert result.warnings == []

                # Check that QMD file was generated
                assert qmd_file.exists()

                # Check subprocess call
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == "/mock/quarto"
                assert "render report.qmd --to html --toc" == " ".join(args[1:])

    def test_render_quarto_failure(self):
        """Test rendering when Quarto fails."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            outline_file = report_dir / "outline.json"

            import uuid

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Test Report",
                sections=[],
                insights=[],
                metadata={},
            )

            with open(outline_file, "w") as f:
                json.dump(outline.model_dump(), f)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: failed to render")

                with pytest.raises(RuntimeError) as exc_info:
                    renderer.render(
                        report_dir=str(report_dir),
                        format="html",
                        outline=outline,
                        datasets={},
                        hints={},
                    )

                assert "Quarto render failed" in str(exc_info.value)

    def test_render_timeout(self):
        """Test rendering timeout."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            outline_file = report_dir / "outline.json"

            outline = {
                "report_id": "test-report",
                "title": "Test Report",
                "sections": [],
                "insights": [],
                "metadata": {},
            }

            with open(outline_file, "w") as f:
                json.dump(outline, f)

            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("quarto render", 300),
            ):
                with pytest.raises(RuntimeError) as exc_info:
                    renderer.render(
                        report_dir=str(report_dir),
                        format="html",
                        outline=outline,
                        datasets={},
                        hints={},
                    )

                assert "timed out after 5 minutes" in str(exc_info.value)

    def test_render_with_version_warnings(self):
        """Test rendering with version warnings."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"
        QuartoRenderer._cached_version = "1.2.0"  # Old version

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            outline_file = report_dir / "outline.json"

            outline = {
                "report_id": "test-report",
                "title": "Test Report",
                "sections": [],
                "insights": [],
                "metadata": {},
            }

            with open(outline_file, "w") as f:
                json.dump(outline, f)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Output created: report.html\n", stderr="")

                result = renderer.render(
                    report_dir=str(report_dir),
                    format="html",
                    outline=outline,
                    datasets={},
                    hints={},
                )

                assert "Upgrade to Quarto 1.4+" in result.warnings[0]

    def test_render_with_missing_datasets_warning(self):
        """Test rendering with missing datasets warning."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"
        QuartoRenderer._cached_version = "1.4.0"

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            outline_file = report_dir / "outline.json"

            import uuid as uuid_mod

            from igloo_mcp.living_reports.models import (
                DatasetSource,
                Insight,
                Section,
            )

            report_id = str(uuid_mod.uuid4())
            sec_id = str(uuid_mod.uuid4())
            insight_id = str(uuid_mod.uuid4())

            outline = create_test_outline(
                report_id=report_id,
                title="Test Report",
                sections=[
                    Section(
                        section_id=sec_id,
                        title="Section 1",
                        order=0,
                        insight_ids=[insight_id],
                    )
                ],
                insights=[
                    Insight(
                        insight_id=insight_id,
                        summary="Test insight",
                        importance=5,
                        supporting_queries=[DatasetSource(execution_id="exec1")],
                    )
                ],
                metadata={},
            )

            with open(outline_file, "w") as f:
                json.dump(outline.model_dump(), f)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: dataset not found")

                with pytest.raises(RuntimeError):
                    renderer.render(
                        report_dir=str(report_dir),
                        format="html",
                        outline=outline,
                        datasets={},  # Empty datasets - should trigger warning
                        hints={},
                    )

    def test_render_invalid_report_dir(self):
        """Test rendering with invalid report directory."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"

        with pytest.raises(ValueError) as exc_info:
            renderer.render(
                report_dir="/nonexistent/directory",
                format="html",
                outline={
                    "report_id": "test",
                    "title": "Test",
                    "sections": [],
                    "insights": [],
                    "metadata": {},
                },
                datasets={},
                hints={},
            )

        assert "Report directory does not exist" in str(exc_info.value)

    def test_render_missing_outline_file(self):
        """Test rendering with missing outline.json."""
        renderer = QuartoRenderer()
        QuartoRenderer._cached_bin_path = "/mock/quarto"

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            # Don't create outline.json

            with pytest.raises(ValueError) as exc_info:
                renderer.render(
                    report_dir=str(report_dir),
                    format="html",
                    outline=None,  # Force loading from file
                    datasets={},
                    hints={},
                )

            assert "Outline file not found" in str(exc_info.value)

    def test_generate_qmd_with_complex_outline(self):
        """Test QMD generation with complex outline structure."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)

            import uuid as uuid_mod

            from igloo_mcp.living_reports.models import (
                DatasetSource,
                Insight,
                Section,
            )

            report_id = str(uuid_mod.uuid4())
            sec_id = str(uuid_mod.uuid4())
            insight1_id = str(uuid_mod.uuid4())
            insight2_id = str(uuid_mod.uuid4())

            outline = create_test_outline(
                report_id=report_id,
                title="Complex Test Report",
                metadata={
                    "summary": "A comprehensive report",
                    "author": "Test Author",
                },
                sections=[
                    Section(
                        section_id=sec_id,
                        title="Revenue Analysis",
                        order=1,
                        notes="Key revenue metrics and trends",
                        insight_ids=[insight1_id, insight2_id],
                    )
                ],
                insights=[
                    Insight(
                        insight_id=insight1_id,
                        importance=9,
                        summary="Revenue increased 15%",
                        supporting_queries=[DatasetSource(execution_id="exec1")],
                        draft_changes={"type": "chart"},
                    ),
                    Insight(
                        insight_id=insight2_id,
                        importance=7,
                        summary="Customer acquisition costs down",
                        supporting_queries=[DatasetSource(execution_id="exec2")],
                        draft_changes={"type": "table"},
                    ),
                ],
            )

            datasets = {
                insight1_id: {"data": "sample data"},
                insight2_id: {"data": "more data"},
            }

            renderer._generate_qmd_file(
                report_dir=report_dir,
                format="html",
                options={"toc": True, "code_folding": True},
                outline=outline,
                datasets=datasets,
                hints={"custom_hint": "value"},
            )

            qmd_file = report_dir / "report.qmd"
            assert qmd_file.exists()

            content = qmd_file.read_text()
            assert 'title: "Complex Test Report"' in content
            assert "toc: true" in content
            assert "code-fold: true" in content
            assert "A comprehensive report" in content
            assert "## Revenue Analysis" in content
            assert "Key revenue metrics and trends" in content
            assert "### Revenue increased 15%" in content
            assert "### Customer acquisition costs down" in content
            assert "```{python}" in content  # Chart and table placeholders

    def test_generate_qmd_file(self):
        """Test QMD file generation."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)

            insight_id = str(uuid.uuid4())
            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Test Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[
                    Section(
                        section_id=str(uuid.uuid4()),
                        title="Test Section",
                        order=1,
                        insight_ids=[insight_id],
                        notes="Some notes",
                    )
                ],
                insights=[
                    Insight(
                        insight_id=insight_id,
                        importance=8,
                        summary="Test insight",
                        supporting_queries=[],
                        status="active",
                        draft_changes={"type": "table"},
                    )
                ],
                metadata={"summary": "Report summary"},
            )

            renderer._generate_qmd_file(
                report_dir=report_dir,
                format="html",
                options={"toc": True},
                outline=outline,
                datasets={},
                hints={},
            )

            qmd_file = report_dir / "report.qmd"
            assert qmd_file.exists()

            content = qmd_file.read_text()
            assert 'title: "Test Report"' in content
            assert "format: html" in content
            assert "toc: true" in content
            assert "## Test Section" in content
            assert "### Test insight" in content
            assert "```{python}" in content  # Table placeholder


class TestRenderResult:
    """Test RenderResult namedtuple."""

    def test_render_result_creation(self):
        """Test RenderResult creation and access."""
        result = RenderResult(
            output_paths=["/path/to/output.html"],
            stdout="Success",
            stderr="",
            warnings=["Minor warning"],
        )

        assert result.output_paths == ["/path/to/output.html"]
        assert result.stdout == "Success"
        assert result.stderr == ""
        assert result.warnings == ["Minor warning"]

    def test_render_result_immutable(self):
        """Test that RenderResult is immutable."""
        result = RenderResult(
            output_paths=["/path/to/output.html"],
            stdout="Success",
            stderr="",
            warnings=[],
        )

        with pytest.raises(AttributeError):
            result.output_paths = ["new/path"]


class TestTemplateResolution:
    """Test template resolution strategies in QuartoRenderer."""

    def test_template_resolution_via_importlib_resources(self):
        """Test Strategy 1: Template resolution using importlib.resources (installed package)."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Test Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[],
                insights=[],
                metadata={},
            )

            # Let importlib.resources work normally (should find templates in package)
            # This tests Strategy 1 when package is installed or in development
            renderer._generate_qmd_file(
                report_dir=report_dir,
                format="html",
                options={},
                outline=outline,
                datasets={},
                hints={},
            )

            # Verify QMD file was created (template was found)
            qmd_file = report_dir / "report.qmd"
            assert qmd_file.exists()

            # Verify content was generated from template
            content = qmd_file.read_text()
            assert 'title: "Test Report"' in content
            assert "format: html" in content

    def test_template_resolution_via_repo_root(self):
        """Test Strategy 2: Template resolution using repo root (development mode)."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            # Create a mock repo structure
            repo_root = Path(temp_dir) / "repo"
            templates_dir = repo_root / "src" / "igloo_mcp" / "living_reports" / "templates"
            templates_dir.mkdir(parents=True, exist_ok=True)

            # Create a mock template file
            template_file = templates_dir / "report.qmd.j2"
            template_file.write_text(
                '---\ntitle: "{{ outline.title }}"\nformat: {{ format }}\n---\n\n# {{ outline.title }}\n'
            )

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Dev Mode Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[],
                insights=[],
                metadata={},
            )

            # Mock importlib.resources to fail (simulating not installed)
            with patch("igloo_mcp.living_reports.quarto_renderer.importlib.resources.files") as mock_resources:
                mock_resources.side_effect = ImportError("Package not installed")

                # Mock find_repo_root to return our test repo
                with patch("igloo_mcp.living_reports.quarto_renderer.find_repo_root") as mock_repo_root:
                    mock_repo_root.return_value = repo_root

                    renderer._generate_qmd_file(
                        report_dir=report_dir,
                        format="markdown",
                        options={},
                        outline=outline,
                        datasets={},
                        hints={},
                    )

                    # Verify QMD file was created using repo template
                    qmd_file = report_dir / "report.qmd"
                    assert qmd_file.exists()

                    content = qmd_file.read_text()
                    assert 'title: "Dev Mode Report"' in content
                    assert "format: markdown" in content

    def test_template_resolution_via_file_relative(self):
        """Test Strategy 3: Template resolution using file-relative path (fallback)."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            # Create templates directory relative to quarto_renderer.py location
            # We'll mock the __file__ to point to our test structure
            mock_renderer_dir = Path(temp_dir) / "mock_renderer"
            mock_renderer_dir.mkdir()
            templates_dir = mock_renderer_dir / "templates"
            templates_dir.mkdir()

            # Create a mock template file
            template_file = templates_dir / "report.qmd.j2"
            template_file.write_text('---\ntitle: "{{ outline.title }}"\n---\n\n# {{ outline.title }}\n')

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Fallback Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[],
                insights=[],
                metadata={},
            )

            # Mock importlib.resources to fail
            with patch("igloo_mcp.living_reports.quarto_renderer.importlib.resources.files") as mock_resources:
                mock_resources.side_effect = ImportError("Package not installed")

                # Mock find_repo_root to return non-existent path
                with patch("igloo_mcp.living_reports.quarto_renderer.find_repo_root") as mock_repo_root:
                    mock_repo_root.return_value = Path("/nonexistent/repo")

                    # Mock __file__ to point to our test structure
                    import igloo_mcp.living_reports.quarto_renderer as qr_module

                    original_file_attr = getattr(qr_module, "__file__", None)
                    try:
                        qr_module.__file__ = str(mock_renderer_dir / "quarto_renderer.py")

                        renderer._generate_qmd_file(
                            report_dir=report_dir,
                            format="html",
                            options={},
                            outline=outline,
                            datasets={},
                            hints={},
                        )

                        # Verify QMD file was created using file-relative template
                        qmd_file = report_dir / "report.qmd"
                        assert qmd_file.exists()

                        content = qmd_file.read_text()
                        assert 'title: "Fallback Report"' in content
                    finally:
                        if original_file_attr:
                            qr_module.__file__ = original_file_attr

    def test_template_resolution_all_strategies_fail(self):
        """Test error handling when all template resolution strategies fail."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Test Report",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[],
                insights=[],
                metadata={},
            )

            # Mock all strategies to fail
            with patch("igloo_mcp.living_reports.quarto_renderer.importlib.resources.files") as mock_resources:
                mock_resources.side_effect = ImportError("Package not installed")

                with patch("igloo_mcp.living_reports.quarto_renderer.find_repo_root") as mock_repo_root:
                    mock_repo_root.return_value = Path("/nonexistent/repo")

                    # Mock __file__ to point to non-existent location
                    import igloo_mcp.living_reports.quarto_renderer as qr_module

                    original_file_attr = getattr(qr_module, "__file__", None)
                    try:
                        qr_module.__file__ = "/nonexistent/quarto_renderer.py"

                        with pytest.raises(RuntimeError) as exc_info:
                            renderer._generate_qmd_file(
                                report_dir=report_dir,
                                format="html",
                                options={},
                                outline=outline,
                                datasets={},
                                hints={},
                            )

                        # Verify error message includes all attempted paths
                        error_msg = str(exc_info.value)
                        assert "Template directory not found" in error_msg
                        assert "Attempted paths" in error_msg or "Package location" in error_msg
                    finally:
                        if original_file_attr:
                            qr_module.__file__ = original_file_attr

    def test_template_resolution_with_real_package(self):
        """Test that template resolution works with actual installed package."""
        renderer = QuartoRenderer()

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)

            outline = create_test_outline(
                report_id=str(uuid.uuid4()),
                title="Real Package Test",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                sections=[],
                insights=[],
                metadata={},
            )

            # This should work with the actual package structure
            # (either installed or in development mode)
            renderer._generate_qmd_file(
                report_dir=report_dir,
                format="html",
                options={},
                outline=outline,
                datasets={},
                hints={},
            )

            # Verify QMD file was created
            qmd_file = report_dir / "report.qmd"
            assert qmd_file.exists()

            # Verify content matches expected template structure
            content = qmd_file.read_text()
            assert 'title: "Real Package Test"' in content
            assert "format: html" in content
            # Template uses YAML front matter, not markdown headers for title
            assert "---" in content  # YAML front matter delimiters

    def test_template_file_actually_exists_in_package(self):
        """Verify that report.qmd.j2 template actually exists and is accessible."""
        # Test that we can access the template via importlib.resources
        try:
            templates_ref = importlib.resources.files("igloo_mcp.living_reports.templates")
            template_file_ref = templates_ref / "report.qmd.j2"
            assert template_file_ref.exists(), "Template file should exist in package"

            # Verify we can read it
            template_content = template_file_ref.read_text(encoding="utf-8")
            assert len(template_content) > 0, "Template should have content"
            assert "outline.title" in template_content, "Template should contain outline.title"
        except (ImportError, ModuleNotFoundError):
            # If package isn't installed, check repo structure instead
            repo_root = Path(__file__).parent.parent
            template_path = repo_root / "src" / "igloo_mcp" / "living_reports" / "templates" / "report.qmd.j2"
            assert template_path.exists(), f"Template should exist at {template_path}"
            template_content = template_path.read_text(encoding="utf-8")
            assert len(template_content) > 0, "Template should have content"
