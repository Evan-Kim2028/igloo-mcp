from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .audit import LineageAudit
from .builder import LineageBuilder, LineageBuildResult
from .graph import EdgeType, LineageGraph, NodeType


@dataclass
class LineageQueryResult:
    graph: LineageGraph
    audit: LineageAudit


class LineageQueryService:
    def __init__(
        self, catalog_dir: Path | str, cache_root: Path | str | None = None
    ) -> None:
        self.catalog_dir = Path(catalog_dir)
        if cache_root is None:
            self.cache_root = self.catalog_dir.parent / "lineage"
        else:
            self.cache_root = Path(cache_root)
        self.cache_dir = self.cache_root / self.catalog_dir.name
        self.builder = LineageBuilder(self.catalog_dir)
        self.graph_path = self.cache_dir / "lineage_graph.json"
        self.audit_path = self.cache_dir / "lineage_audit.json"
        self._graph: Optional[LineageGraph] = None
        self._audit: Optional[LineageAudit] = None

    def build(self, *, force: bool = False) -> LineageBuildResult:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if not force and self.graph_path.exists() and self.audit_path.exists():
            self._graph = LineageGraph.from_dict(
                json.loads(self.graph_path.read_text())
            )
            self._audit = LineageAudit.from_dict(
                json.loads(self.audit_path.read_text())
            )
            return LineageBuildResult(self._graph, self._audit)

        result = self.builder.build()
        self.graph_path.write_text(json.dumps(result.graph.to_dict(), indent=2))
        self.audit_path.write_text(json.dumps(result.audit.to_dict(), indent=2))
        self._graph = result.graph
        self._audit = result.audit
        return result

    def load_cached(self) -> LineageQueryResult:
        if self._graph and self._audit:
            return LineageQueryResult(self._graph, self._audit)
        if not self.graph_path.exists() or not self.audit_path.exists():
            raise FileNotFoundError("Lineage graph not built yet; run lineage rebuild")
        self._graph = LineageGraph.from_dict(json.loads(self.graph_path.read_text()))
        self._audit = LineageAudit.from_dict(json.loads(self.audit_path.read_text()))
        return LineageQueryResult(self._graph, self._audit)

    def object_subgraph(
        self,
        object_key: str,
        *,
        direction: str = "both",
        depth: Optional[int] = None,
    ) -> LineageQueryResult:
        lineage = self.load_cached()
        if object_key not in lineage.graph.nodes:
            raise KeyError(f"Object not found in lineage graph: {object_key}")
        subgraph = lineage.graph.traverse(
            object_key,
            direction=direction,
            depth=depth,
        )
        return LineageQueryResult(subgraph, lineage.audit)

    def audit(self) -> LineageAudit:
        return self.load_cached().audit

    @staticmethod
    def to_dot(graph: LineageGraph) -> str:
        def _escape(value: str) -> str:
            return value.replace('"', "'")

        lines = ["digraph Lineage {"]
        lines.append("  rankdir=LR;")
        for node in graph.nodes.values():
            label = _escape(node.attributes.get("name") or node.key)
            node_key = _escape(node.key)
            if node.node_type == NodeType.TASK:
                shape = "octagon"
                color = "#1f77b4"
            else:
                shape = "box"
                color = "#2ca02c"
            lines.append(
                f'  "{node_key}" [label="{label}", shape={shape}, color="{color}"];'
            )
        for (src, dst, edge_type), _ in graph.edge_metadata.items():
            src_key = _escape(src)
            dst_key = _escape(dst)
            label = edge_type.value
            lines.append(f'  "{src_key}" -> "{dst_key}" [label="{label}"];')
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_json(graph: LineageGraph) -> Dict:
        return graph.to_dict()

    @staticmethod
    def to_html(
        graph: LineageGraph,
        output_path: Path | str,
        *,
        title: str | None = None,
        root_key: str | None = None,
    ) -> Path:
        try:
            from pyvis.network import Network  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pyvis is required for HTML export. Install pyvis>=0.3.2"
            ) from exc

        html_path = Path(output_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)

        net = Network(directed=True, height="750px", width="100%", notebook=False)
        net.barnes_hut()
        net.set_options(
            json.dumps(
                {
                    "interaction": {"hover": True},
                    "physics": {
                        "stabilization": {"iterations": 250},
                        "barnesHut": {"springLength": 250},  # Increase spacing
                    },
                    "edges": {"smooth": True},
                    "layout": {"improvedLayout": True},
                }
            )
        )
        if title:
            net.heading = title

        object_color_map = {
            "table": "#1f77b4",
            "view": "#2ca02c",
            "materialized_view": "#9467bd",
            "dynamic_table": "#ff7f0e",
            "task": "#17becf",
            "procedure": "#e377c2",
            "function": "#bcbd22",
            "default": "#7f7f7f",
        }
        edge_color_map = {
            EdgeType.DERIVES_FROM: "#6baed6",
            EdgeType.CONSUMES: "#ff7f0e",
            EdgeType.PRODUCES: "#9467bd",
        }
        legend_items = [
            ("Table", object_color_map["table"]),
            ("View", object_color_map["view"]),
            ("Materialized View", object_color_map["materialized_view"]),
            ("Dynamic Table", object_color_map["dynamic_table"]),
            ("Task", object_color_map["task"]),
        ]
        span_style = "margin-left:12px; display:inline-flex; align-items:center;"
        inner_span_base = (
            "display:inline-block;width:12px;height:12px;background:{color};"
        )
        inner_span_style = inner_span_base + "margin-right:4px;border:1px solid #ccc;"
        legend_html = "".join(
            f'<span style="{span_style}"><span style="{inner_span_style}"></span>{label}</span>'
            for label, color in legend_items
        )

        for node in graph.nodes.values():
            base_label = node.attributes.get("name") or node.key
            obj_kind = node.attributes.get("object_type") or node.node_type.value
            label = f"{base_label}\n[{obj_kind.replace('_', ' ').title()}]"
            title_lines = [
                f"Type: {node.node_type.value}",
                f"Key: {node.key}",
            ]
            title_lines.extend(f"{k}: {v}" for k, v in node.attributes.items())
            title_text = "<br>".join(title_lines)
            color = object_color_map.get(obj_kind.lower(), object_color_map["default"])
            net.add_node(
                node.key,
                label=label,
                title=title_text,
                color=color,
            )

        for (src, dst, edge_type), evidence in graph.edge_metadata.items():
            tooltip_lines = [f"Type: {edge_type.value}"]
            tooltip_lines.extend(f"{k}: {v}" for k, v in evidence.items())
            tooltip = "<br>".join(tooltip_lines)
            net.add_edge(
                src,
                dst,
                label=edge_type.value,
                title=tooltip,
                arrows="to",
                color=edge_color_map.get(edge_type, "#888"),
                edge_type=edge_type.value,
            )

        net.save_graph(str(html_path))

        html_text = html_path.read_text()
        div_style = "padding:8px; background:#f7f7f7; border-bottom:1px solid #ddd; font-family:Arial, sans-serif;"
        controls_html = textwrap.dedent(
            f"""
            <div id="lineage-controls" style="{div_style}">
              <div><strong>Node Types:</strong>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-table" checked>
                  Table</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-view" checked>
                  View</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-materialized_view"
                  checked> Mat. View</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-dynamic_table"
                  checked> Dyn. Table</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-task" checked>
                  Task</label>
              </div>
              <div style="margin-top:6px;"><strong>Edge Types:</strong>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-derives_from"
                  checked> derives_from</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-consumes"
                  checked> consumes</label>
                <label style="margin-left:12px;"><input type="checkbox" id="toggle-produces"
                  checked> produces</label>
              </div>
              <div style="margin-top:6px;"><strong>Legend:</strong>{legend_html}</div>
              <div style="margin-top:6px; font-size:11px; color:#666;">
                Use checkboxes to show/hide different types of objects and relationships
              </div>
            </div>
            """
        ).strip()
        controls_div = controls_html
        if "lineage-controls" not in html_text and 'id="mynetwork"' in html_text:
            if '<div id="mynetwork">' in html_text:
                html_text = html_text.replace(
                    '<div id="mynetwork">', controls_div + '\n<div id="mynetwork">', 1
                )
            else:
                html_text = html_text.replace(
                    '<div id="mynetwork"', controls_div + '\n<div id="mynetwork"', 1
                )

        controls_script = """
<script type=\"text/javascript\">
// Simple toggle controls for node and edge types
(function () {
  // Toggle node visibility by type
  function toggleNodes(nodeType, show) {
    if (typeof nodes !== 'undefined' && nodes) {
      const allNodes = nodes.get();
      allNodes.forEach(node => {
        if (node.title && node.title.includes('object_type: ' + nodeType)) {
          nodes.update({id: node.id, hidden: !show});
        }
      });
    }
  }

  // Toggle edge visibility by type
  function toggleEdges(edgeType, show) {
    if (typeof edges !== 'undefined' && edges) {
      const allEdges = edges.get();
      allEdges.forEach(edge => {
        if (edge.edge_type === edgeType) {
          edges.update({id: edge.id, hidden: !show});
        }
      });
    }
  }

  // Set up event listeners for checkboxes
  const nodeTypes = ['table', 'view', 'materialized_view', 'dynamic_table', 'task'];
  const edgeTypes = ['derives_from', 'consumes', 'produces'];

  nodeTypes.forEach(type => {
    const checkbox = document.getElementById('toggle-' + type);
    if (checkbox) {
      checkbox.addEventListener('change', (event) => {
        toggleNodes(type, event.target.checked);
      });
    }
  });

  edgeTypes.forEach(type => {
    const checkbox = document.getElementById('toggle-' + type);
    if (checkbox) {
      checkbox.addEventListener('change', (event) => {
        toggleEdges(type, event.target.checked);
      });
    }
  });

  // Auto-fit after a delay
  setTimeout(function() {
    if (typeof network !== 'undefined' && network) {
      network.fit();
    }
  }, 500);
})();
</script>
"""
        if controls_script not in html_text:
            html_text = html_text.replace("</body>", controls_script + "\\n</body>", 1)

        html_path.write_text(html_text)
        return html_path
