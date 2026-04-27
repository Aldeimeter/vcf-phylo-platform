import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.services.job_storage import job_storage
from app.logger import logger

router = APIRouter(prefix="/jobs", tags=["export"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"


def _duration(started_at, completed_at) -> str:
    if not started_at or not completed_at:
        return "—"
    secs = int((completed_at - started_at).total_seconds())
    m, s = divmod(secs, 60)
    return f"{m}m {s}s" if m else f"{s}s"


def _pct_badge(value) -> str:
    if value is None:
        return '<span class="badge badge-na">N/A</span>'
    color = "badge-high" if value >= 70 else ("badge-mid" if value >= 40 else "badge-low")
    return f'<span class="badge {color}">{value}%</span>'


def _status_badge(status: str) -> str:
    css = {
        "completed": "badge-high",
        "running": "badge-mid",
        "pending": "badge-na",
        "failed": "badge-low",
    }.get(status, "badge-na")
    return f'<span class="badge {css}">{status}</span>'


def _render_comparison(results_json: dict) -> str:
    rows = ""
    for pair_key, data in results_json.items():
        tool_a, tool_b = pair_key.split("_vs_")
        topo = data.get("topology") or {}
        bl = data.get("branch_lengths") or {}
        pearson = bl.get("pearson") or {}
        spearman = bl.get("spearman") or {}
        wrf = data.get("weighted_rf") or {}

        topo_pct = topo.get("similarity_pct")
        pearson_pct = pearson.get("similarity_pct")
        spearman_pct = spearman.get("similarity_pct")
        wrf_pct = wrf.get("similarity_pct")

        topo_detail = ""
        if "raw_rf" in topo:
            topo_detail = f'RF={topo["raw_rf"]}, norm={topo.get("normalized_rf", "—")}'
        elif "error" in topo:
            topo_detail = f'error: {topo["error"]}'

        pearson_detail = ""
        if "r" in pearson:
            pearson_detail = f'r={pearson["r"]}, n={pearson.get("pairs_used", "—")}'
        elif "reason" in pearson:
            pearson_detail = pearson["reason"]
        elif "error" in bl:
            pearson_detail = f'error: {bl["error"]}'

        spearman_detail = ""
        if "r" in spearman:
            spearman_detail = f'ρ={spearman["r"]}, n={spearman.get("pairs_used", "—")}'
        elif "reason" in spearman:
            spearman_detail = spearman["reason"]

        wrf_detail = ""
        if "wrf_distance" in wrf:
            wrf_detail = f'd={wrf["wrf_distance"]}'
        elif "error" in wrf:
            wrf_detail = f'error: {wrf["error"]}'

        rows += f"""
        <tr>
          <td><strong>{tool_a}</strong> vs <strong>{tool_b}</strong></td>
          <td>{_pct_badge(topo_pct)}<br><small>{topo_detail}</small></td>
          <td>{_pct_badge(pearson_pct)}<br><small>{pearson_detail}</small></td>
          <td>{_pct_badge(spearman_pct)}<br><small>{spearman_detail}</small></td>
          <td>{_pct_badge(wrf_pct)}<br><small>{wrf_detail}</small></td>
        </tr>"""

    return f"""
    <table class="legend-table">
      <tbody>
        <tr><td><strong>Topology (RF)</strong></td><td>Robinson-Foulds distance on unrooted trees — counts differing bipartitions. 100% = identical branching structure.</td></tr>
        <tr><td><strong>Branch lengths (Pearson)</strong></td><td>Pearson correlation of normalized patristic distances — measures whether relative branch proportions agree, regardless of unit scale.</td></tr>
        <tr><td><strong>Branch lengths (Spearman)</strong></td><td>Spearman rank correlation of normalized patristic distances — same as Pearson but rank-based, more robust to skewed branch length distributions and outlier branches.</td></tr>
        <tr><td><strong>Topology + branch lengths (wRF)</strong></td><td>Weighted Robinson-Foulds on normalized branch lengths — shared splits contribute |w1−w2|, unshared splits their full length. 100% = identical topology and proportions.</td></tr>
      </tbody>
    </table>
    <table>
      <thead>
        <tr>
          <th>Pair</th>
          <th>Topology (RF)</th>
          <th>Branch lengths (Pearson)</th>
          <th>Branch lengths (Spearman)</th>
          <th>Topology + branch lengths (wRF)</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _render_timing(tools_timing) -> str:
    if not tools_timing:
        return "<p>No timing data available.</p>"

    rows = ""
    for tool, secs in tools_timing.model_dump().items():
        if secs is not None:
            rows += f"<tr><td>{tool}</td><td>{secs:.2f}s</td></tr>"

    if not rows:
        return "<p>No timing data available.</p>"

    return f"""
    <table>
      <thead><tr><th>Tool</th><th>Duration</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def _collect_nwk_trees(results_path: Path) -> list[dict]:
    trees = []
    for tool_dir in sorted(results_path.iterdir()):
        if not tool_dir.is_dir():
            continue
        for nwk_file in tool_dir.glob("*.nwk"):
            trees.append({
                "tool": tool_dir.name,
                "newick": nwk_file.read_text().strip(),
            })
    return trees


# ---------------------------------------------------------------------------
# Server-side SVG tree renderer (used for PDF; HTML uses D3)
# ---------------------------------------------------------------------------

def _parse_newick(s: str) -> dict:
    node: dict = {}
    ancestors: list = []
    tokens = re.split(r'\s*(;|\(|\)|,|:)\s*', s.strip().rstrip(";"))
    for i, token in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else ""
        if token == "(":
            child: dict = {}
            node.setdefault("children", []).append(child)
            ancestors.append(node)
            node = child
        elif token == ",":
            child = {}
            ancestors[-1].setdefault("children", []).append(child)
            node = child
        elif token == ")":
            node = ancestors.pop()
        elif token == ":":
            pass
        elif token.strip():
            if prev in (")", "(", ","):
                node["name"] = token.strip()
            elif prev == ":":
                try:
                    node["length"] = float(token)
                except ValueError:
                    pass
    return node


class _Node:
    __slots__ = ("data", "children", "x", "y")

    def __init__(self, data: dict):
        self.data = data
        self.children = [_Node(c) for c in data.get("children", [])]
        self.x = 0.0
        self.y = 0.0


def _leaves(node: _Node) -> list[_Node]:
    if not node.children:
        return [node]
    result = []
    for c in node.children:
        result.extend(_leaves(c))
    return result


def _all_nodes(node: _Node) -> list[_Node]:
    result = [node]
    for c in node.children:
        result.extend(_all_nodes(c))
    return result


def _max_depth(node: _Node, d: int = 0) -> int:
    if not node.children:
        return d
    return max(_max_depth(c, d + 1) for c in node.children)


def _build_layout(root: _Node, inner_width: float, inner_height: float) -> None:
    leaf_list = _leaves(root)
    n = len(leaf_list)
    step = inner_height / max(n - 1, 1) if n > 1 else 0.0
    for i, leaf in enumerate(leaf_list):
        leaf.x = i * step if n > 1 else inner_height / 2

    def assign_internal_x(node: _Node) -> None:
        for c in node.children:
            assign_internal_x(c)
        if node.children:
            node.x = (node.children[0].x + node.children[-1].x) / 2

    assign_internal_x(root)

    depth = _max_depth(root)

    def assign_y(node: _Node, d: int = 0) -> None:
        if not node.children:
            node.y = inner_width
        else:
            node.y = (d / depth * inner_width) if depth > 0 else 0.0
            for c in node.children:
                assign_y(c, d + 1)

    assign_y(root)


def _newick_to_svg(newick: str, svg_width: int = 1000, max_height: int | None = None) -> str:
    """Render a Newick string as an SVG.

    If *max_height* is given the row spacing is compressed so the tree fits
    within that pixel budget — WeasyPrint does not scale SVG via viewBox, so
    we must produce the right dimensions directly.
    """
    MAX_ROW_HEIGHT = 22
    MIN_ROW_HEIGHT = 4
    MARGIN_LEFT = 16
    MARGIN_RIGHT = 220
    MARGIN_TOP = 16
    MARGIN_BOT = 16
    INNER_WIDTH = float(svg_width - MARGIN_LEFT - MARGIN_RIGHT)

    try:
        data = _parse_newick(newick)
    except Exception as e:
        return f'<p style="color:red">Failed to parse tree: {e}</p>'

    root = _Node(data)
    leaf_list = _leaves(root)
    n_leaves = len(leaf_list)

    # Choose row height that fits within max_height if given
    if max_height:
        available = max_height - MARGIN_TOP - MARGIN_BOT
        row_height = max(MIN_ROW_HEIGHT, min(MAX_ROW_HEIGHT, available / max(n_leaves, 1)))
    else:
        row_height = MAX_ROW_HEIGHT

    inner_height = float(max(n_leaves * row_height, 80))
    svg_height = inner_height + MARGIN_TOP + MARGIN_BOT

    # Scale font sizes proportionally when rows are compressed
    label_font = max(7, min(12, int(row_height * 0.85)))
    bootstrap_font = max(6, min(10, int(row_height * 0.7)))

    _build_layout(root, INNER_WIDTH, inner_height)

    elements: list[str] = []

    for node in _all_nodes(root):
        for child in node.children:
            elements.append(
                f'<path d="M{node.y:.1f},{node.x:.1f}V{child.x:.1f}H{child.y:.1f}"'
                f' fill="none" stroke="#495057" stroke-width="1.5"/>'
            )

    for node in _all_nodes(root):
        elements.append(
            f'<circle cx="{node.y:.1f}" cy="{node.x:.1f}" r="3" fill="#495057"/>'
        )
        name = node.data.get("name", "")
        if not node.children and name:
            elements.append(
                f'<text x="{node.y + 8:.1f}" y="{node.x:.1f}" dy="0.32em"'
                f' font-size="{label_font}" fill="#212529" font-family="sans-serif">{name}</text>'
            )
        elif node.children and node is not root and name:
            elements.append(
                f'<text x="{node.y - 6:.1f}" y="{node.x:.1f}" dy="-0.4em"'
                f' font-size="{bootstrap_font}" fill="#868e96" font-family="sans-serif"'
                f' text-anchor="end">{name}</text>'
            )

    inner = "\n".join(elements)
    return (
        f'<svg width="{svg_width}" height="{svg_height:.0f}" xmlns="http://www.w3.org/2000/svg">'
        f'<g transform="translate({MARGIN_LEFT},{MARGIN_TOP})">{inner}</g>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# D3 tree rendering JS (HTML export only)
# ---------------------------------------------------------------------------

_TREE_JS = r"""
function parseNewick(s) {
  var ancestors = [], tree = {}, tokens = s.split(/\s*(;|\(|\)|,|:)\s*/);
  for (var i = 0; i < tokens.length; i++) {
    var token = tokens[i], subtree = {};
    switch (token) {
      case '(':
        tree.children = [subtree]; ancestors.push(tree); tree = subtree; break;
      case ',':
        ancestors[ancestors.length-1].children.push(subtree); tree = subtree; break;
      case ')':
        tree = ancestors.pop(); break;
      case ':': break;
      default:
        var prev = tokens[i-1];
        if (prev === ')' || prev === '(' || prev === ',') tree.name = token;
        else if (prev === ':') tree.length = parseFloat(token);
    }
  }
  return tree;
}

(function renderTrees() {
  if (typeof TREES === 'undefined' || !Array.isArray(TREES)) return;
  TREES.forEach(function({tool, newick}) {
    var container = document.getElementById('tree-' + tool);
    if (!container) return;

    var parsed;
    try { parsed = parseNewick(newick); } catch(e) {
      container.textContent = 'Failed to parse Newick: ' + e;
      return;
    }

    var root = d3.hierarchy(parsed, function(d) { return d.children; });
    var leafCount = root.leaves().length;

    var rowHeight   = 28;
    var marginTop   = 16;
    var marginBot   = 16;
    var marginLeft  = 16;
    var marginRight = 200;
    var svgWidth    = 700;
    var innerWidth  = svgWidth - marginLeft - marginRight;
    var innerHeight = Math.max(leafCount * rowHeight, 80);
    var svgHeight   = innerHeight + marginTop + marginBot;

    var cluster = d3.cluster().size([innerHeight, innerWidth]);
    cluster(root);

    var svg = d3.select(container)
      .append('svg')
        .attr('width', svgWidth)
        .attr('height', svgHeight)
        .attr('style', 'max-width:100%;height:auto;');

    var g = svg.append('g')
      .attr('transform', 'translate(' + marginLeft + ',' + marginTop + ')');

    g.selectAll('.tree-link')
      .data(root.links())
      .join('path')
        .attr('class', 'tree-link')
        .attr('d', function(d) {
          return 'M' + d.source.y + ',' + d.source.x
               + 'V' + d.target.x
               + 'H' + d.target.y;
        });

    var node = g.selectAll('.tree-node')
      .data(root.descendants())
      .join('g')
        .attr('class', 'tree-node')
        .attr('transform', function(d) {
          return 'translate(' + d.y + ',' + d.x + ')';
        });

    node.append('circle').attr('r', 3);

    node.filter(function(d) { return !d.children; })
      .append('text')
        .attr('class', 'leaf-label')
        .attr('x', 8)
        .attr('dy', '0.32em')
        .text(function(d) { return d.data.name || ''; });

    node.filter(function(d) { return d.children && d.parent && d.data.name; })
      .append('text')
        .attr('class', 'bootstrap-label')
        .attr('x', -6)
        .attr('dy', '-0.4em')
        .text(function(d) { return d.data.name; });
  });
})();
"""

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_CSS = """
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: sans-serif; margin: 0; padding: 2rem; background: #f8f9fa; color: #212529; }
    h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
    h2 { font-size: 1.1rem; margin: 2rem 0 0.75rem; border-bottom: 1px solid #dee2e6; padding-bottom: 0.4rem; }
    h3 { font-size: 0.95rem; margin: 0 0 0.5rem; color: #495057; }
    .meta { color: #6c757d; font-size: 0.85rem; margin-bottom: 2rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.875rem; background: #fff;
            border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 1rem; }
    th { background: #f1f3f5; text-align: left; padding: 0.5rem 0.75rem; font-weight: 600; }
    td { padding: 0.5rem 0.75rem; border-top: 1px solid #e9ecef; vertical-align: top; }
    small { color: #868e96; }
    .badge { display: inline-block; padding: 0.15em 0.55em; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
    .badge-high { background: #d3f9d8; color: #1a7f37; }
    .badge-mid  { background: #fff3cd; color: #856404; }
    .badge-low  { background: #ffe3e3; color: #c92a2a; }
    .badge-na   { background: #e9ecef; color: #495057; }
    section { margin-bottom: 2rem; }
    .tree-card { background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 1rem;
                 margin-bottom: 1rem; overflow-x: auto; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .tree-link { fill: none; stroke: #495057; stroke-width: 1.5px; }
    .tree-node circle { fill: #495057; }
    .leaf-label { font-size: 12px; fill: #212529; font-family: sans-serif; }
    .bootstrap-label { font-size: 10px; fill: #868e96; font-family: sans-serif; text-anchor: end; }
    .note { font-size: 0.8rem; color: #6c757d; margin: 0 0 0.75rem; }
    .legend-table { font-size: 0.8rem; color: #6c757d; margin-bottom: 0.75rem; box-shadow: none; background: #f8f9fa; }
    .legend-table td { border-top: none; padding: 0.25rem 0.75rem; }
    .legend-table td:first-child { white-space: nowrap; color: #495057; }
    details { margin-top: 0.75rem; }
    summary { font-size: 0.8rem; color: #6c757d; cursor: pointer; }
    pre.nwk { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;
              padding: 0.5rem 0.75rem; font-size: 0.75rem; overflow-x: auto;
              white-space: pre-wrap; word-break: break-all; margin: 0.5rem 0 0; }
"""


def render_html_report(job, results_path: Path, pdf_mode: bool = False) -> str:
    pipeline_status = job.pipeline_status
    tool_statuses = pipeline_status.model_dump() if pipeline_status else {}

    status_rows = "".join(
        f"<tr><td>{tool}</td><td>{_status_badge(status)}</td></tr>"
        for tool, status in tool_statuses.items()
    )

    config = job.pipeline_config
    config_rows = ""
    if config:
        for k, v in config.model_dump().items():
            config_rows += f"<tr><td>{k}</td><td>{v}</td></tr>"

    comparison_html = "<p>No comparison results available.</p>"
    results_json_path = results_path / "comparison" / "results.json"
    if results_json_path.exists():
        try:
            data = json.loads(results_json_path.read_text())
            comparison_html = _render_comparison(data)
        except Exception as e:
            logger.warning(f"Failed to parse comparison results at {results_json_path}: {e}")
            comparison_html = "<p>Failed to parse comparison results.</p>"

    timing_html = _render_timing(job.tools_timing)

    trees = _collect_nwk_trees(results_path)

    # Tree section: inline SVG for PDF, D3 containers for HTML
    tree_sections = ""
    if trees:
        for t in trees:
            if pdf_mode:
                tree_viz = _newick_to_svg(t["newick"], svg_width=980, max_height=700)
                tree_sections += f"""
    <div class="tree-card">
      <h3>{t["tool"]}</h3>
      {tree_viz}
    </div>"""
            else:
                tree_sections += f"""
    <div class="tree-card">
      <h3>{t["tool"]}</h3>
      <div id="tree-{t["tool"]}"></div>
      <details>
        <summary>Raw Newick</summary>
        <pre class="nwk">{t["newick"]}</pre>
      </details>
    </div>"""
    else:
        tree_sections = "<p>No Newick files found.</p>"

    pdf_css = """
    @page { size: A4 landscape; margin: 1.5cm; }
    """ if pdf_mode else ""

    d3_head = '<script src="https://d3js.org/d3.v7.min.js"></script>' if not pdf_mode else ""
    trees_json = json.dumps(trees)
    d3_script = f"""
  <script>
    const TREES = {trees_json};
    {_TREE_JS}
  </script>""" if not pdf_mode else ""

    config_section = f"""
  <section>
    <h2>Pipeline configuration</h2>
    <table>
      <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
      <tbody>{config_rows}</tbody>
    </table>
  </section>""" if config_rows else ""

    error_row = f'<tr><td><strong>Error</strong></td><td><code>{job.error}</code></td></tr>' if job.error else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Report — {job.id}</title>
  {d3_head}
  <style>{_CSS}{pdf_css}</style>
</head>
<body>
  <h1>Phylogenetic Analysis Report</h1>
  <p class="meta">Job ID: <code>{job.id}</code> &nbsp;|&nbsp; Dataset: <code>{job.dataset_id}</code></p>

  <section>
    <h2>Job summary</h2>
    <table>
      <tbody>
        <tr><td><strong>Status</strong></td><td>{_status_badge(job.status)}</td></tr>
        <tr><td><strong>Created</strong></td><td>{_fmt_dt(job.created_at)}</td></tr>
        <tr><td><strong>Started</strong></td><td>{_fmt_dt(job.started_at)}</td></tr>
        <tr><td><strong>Completed</strong></td><td>{_fmt_dt(job.completed_at)}</td></tr>
        <tr><td><strong>Total duration</strong></td><td>{_duration(job.started_at, job.completed_at)}</td></tr>
        {error_row}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Pipeline status</h2>
    <table>
      <thead><tr><th>Tool</th><th>Status</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </section>

  {config_section}

  <section>
    <h2>Tool timing</h2>
    {timing_html}
  </section>

  <section>
    <h2>Tree comparison</h2>
    {comparison_html}
  </section>

  <section>
    <h2>Phylogenetic trees</h2>
    {tree_sections}
  </section>
  {d3_script}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{job_id}/export/html", response_class=HTMLResponse)
async def export_html(job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    results_path = Path(os.environ["STATIC_PATH"], job_id)
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Results for job '{job_id}' not found — the job may still be running or may have failed")

    logger.info(f"Exporting HTML report for job {job_id}")
    html = render_html_report(job, results_path, pdf_mode=False)
    headers = {"Content-Disposition": f'attachment; filename="report_{job_id}.html"'}
    return HTMLResponse(content=html, headers=headers)


@router.get("/{job_id}/export/pdf")
async def export_pdf(job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    results_path = Path(os.environ["STATIC_PATH"], job_id)
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Results for job '{job_id}' not found — the job may still be running or may have failed")

    from weasyprint import HTML

    logger.info(f"Exporting PDF report for job {job_id}")
    try:
        html = render_html_report(job, results_path, pdf_mode=True)
        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as e:
        logger.error(f"PDF generation failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    headers = {"Content-Disposition": f'attachment; filename="report_{job_id}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
