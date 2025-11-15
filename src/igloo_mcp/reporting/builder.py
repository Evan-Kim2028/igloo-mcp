from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..path_utils import resolve_history_path
from .history_index import DatasetResolutionError, HistoryIndex, ResolvedDataset
from .manifest import ReportManifest, ReportOutput, load_manifest


@dataclass
class LintIssue:
    code: str
    message: str
    dataset_name: Optional[str] = None
    detail: Optional[str] = None


def _select_output(manifest: ReportManifest, name: Optional[str]) -> ReportOutput:
    if name is None:
        if not manifest.outputs:
            raise ValueError("Report manifest defines no outputs")
        return manifest.outputs[0]
    for output in manifest.outputs:
        if output.name == name:
            return output
    raise ValueError(f"Unknown output name {name!r} in report manifest")


def _compute_manifest_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _build_provenance(
    *,
    manifest_path: Path,
    manifest: ReportManifest,
    datasets: Dict[str, ResolvedDataset],
) -> Dict[str, Any]:
    manifest_hash = _compute_manifest_hash(manifest_path)
    dataset_meta: Dict[str, Any] = {}
    for name, resolved in datasets.items():
        dataset_meta[name] = dict(resolved.provenance)
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "report_id": manifest.id,
        "datasets": dataset_meta,
    }


def _render_json_payload(
    *, manifest: ReportManifest, datasets: Dict[str, ResolvedDataset]
) -> str:
    serialised_datasets: Dict[str, Any] = {}
    for name, resolved in datasets.items():
        serialised_datasets[name] = {
            "rows": resolved.rows,
            "columns": resolved.columns,
            "key_metrics": resolved.key_metrics,
            "insights": resolved.insights,
            "provenance": resolved.provenance,
        }
    payload = {
        "manifest": manifest.model_dump(),
        "datasets": serialised_datasets,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _render_markdown_with_jinja(
    *,
    template_path: Path,
    manifest: ReportManifest,
    datasets: Dict[str, ResolvedDataset],
) -> str:
    try:  # Import lazily so jinja2 is an optional runtime dependency
        import jinja2
    except Exception as exc:  # pragma: no cover - exercised via integration
        raise RuntimeError(
            "Template engine 'jinja' requested but jinja2 is not available. "
            "Install jinja2 or change templates.engine in the manifest."
        ) from exc

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        autoescape=False,
    )
    template = env.get_template(template_path.name)
    context = {
        "manifest": manifest,
        "datasets": datasets,
    }
    return template.render(context)


def build_report(
    manifest_path: Path | str,
    *,
    output_name: Optional[str] = None,
    refresh: bool = False,  # noqa: ARG001 - reserved for future use
) -> Dict[str, Any]:
    """Build a report from a manifest.

    For this initial implementation, *refresh* is accepted but ignored; the
    builder reads only existing history/cache artifacts and does not re-run
    queries.

    Returns a dictionary with keys:
        format: Output format string ("markdown" or "json").
        body: Rendered text payload.
        provenance: Provenance metadata for audit (manifest hash, execution IDs).
    """

    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    output = _select_output(manifest, output_name)

    history_path = resolve_history_path()
    index = HistoryIndex(history_path)

    datasets: Dict[str, ResolvedDataset] = {}
    for ds in manifest.datasets:
        try:
            resolved = index.resolve_dataset(ds)
        except DatasetResolutionError as exc:
            raise DatasetResolutionError(
                f"Failed to resolve dataset {ds.name!r}: {exc}"
            ) from exc
        datasets[ds.name] = resolved

    provenance = _build_provenance(
        manifest_path=manifest_path,
        manifest=manifest,
        datasets=datasets,
    )

    template_path = (manifest_path.parent / manifest.templates.main).resolve()
    if not template_path.exists() and output.format != "json":
        raise FileNotFoundError(f"Template file not found: {template_path}")

    if output.format == "json":
        body = _render_json_payload(manifest=manifest, datasets=datasets)
        return {"format": "json", "body": body, "provenance": provenance}

    # Default narrative format is Markdown; HTML can be derived by callers if
    # needed by wrapping the Markdown body.
    markdown = _render_markdown_with_jinja(
        template_path=template_path,
        manifest=manifest,
        datasets=datasets,
    )
    return {"format": "markdown", "body": markdown, "provenance": provenance}


def lint_report(manifest_path: Path | str) -> List[LintIssue]:
    """Validate a manifest and its dataset bindings.

    Lint checks performed:
        - Manifest structure is valid.
        - Each dataset can be resolved against current history/cache artifacts.

    More advanced drift checks (schema mismatches, value drift) can be layered on
    top of this in future iterations.
    """

    manifest_path = Path(manifest_path).expanduser().resolve()
    issues: List[LintIssue] = []

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        issues.append(
            LintIssue(
                code="manifest_invalid",
                message=f"Invalid report manifest: {exc}",
                detail=str(exc),
            )
        )
        return issues

    history_path = resolve_history_path()
    index = HistoryIndex(history_path)

    for ds in manifest.datasets:
        try:
            index.resolve_dataset(ds)
        except DatasetResolutionError as exc:
            issues.append(
                LintIssue(
                    code="dataset_resolution_error",
                    message=f"Failed to resolve dataset {ds.name!r}",
                    dataset_name=ds.name,
                    detail=str(exc),
                )
            )

    return issues


__all__ = ["LintIssue", "build_report", "lint_report"]
