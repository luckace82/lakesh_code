"""
playwright_server.py  —  Playwright MCP Server
Uses FastMCP — no Starlette SSE conflicts.

Install:
    pip install mcp playwright uvicorn
    playwright install chromium

Run:
    python playwright_server.py

Windsurf config:
    "mcp-playwright-local": { "url": "http://127.0.0.1:3001/sse" }
"""

import os
import json
import traceback
import tempfile
import uvicorn
from mcp.server.fastmcp import FastMCP

_output_dir = os.path.expanduser("~/codegrapher_output")
os.makedirs(_output_dir, exist_ok=True)

mcp = FastMCP("mcp-playwright-local")

# ── Browser state ──────────────────────────────────────────────────
_playwright = None
_browser    = None
_page       = None
_html_path  = None


async def get_page():
    global _playwright, _browser, _page
    if _page is None or _page.is_closed():
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser    = await _playwright.chromium.launch(headless=False)
        _page       = await _browser.new_page()
        await _page.set_viewport_size({"width": 1600, "height": 900})
    return _page


def _parse_graph(raw) -> dict:
    print(f"[DEBUG] graph type: {type(raw).__name__}")
    if isinstance(raw, str):
        print(f"[DEBUG] length: {len(raw)}  preview: {raw[:200]!r}")
        clean = raw.split("\n\n⚠")[0].strip()
        parsed = json.loads(clean)
        print(f"[DEBUG] nodes: {len(parsed.get('nodes', []))}  edges: {len(parsed.get('edges', []))}")
        return parsed
    if isinstance(raw, dict):
        print(f"[DEBUG] nodes: {len(raw.get('nodes', []))}  edges: {len(raw.get('edges', []))}")
        return raw
    raise ValueError(f"Unexpected graph type: {type(raw)}")


# ── Tools ──────────────────────────────────────────────────────────

@mcp.tool()
async def render_graph(graph: str, title: str = "Code Architecture Graph") -> str:
    """
    Render a code architecture graph from code-analyzer-mcp as an interactive
    D3.js force-directed visualization in a real Chromium browser window.
    Pass the raw output from get_graph directly.

    Args:
        graph: JSON string output from code-analyzer get_graph tool.
        title: Title for the browser tab and header.
    """
    global _html_path
    try:
        data = _parse_graph(graph)
    except Exception as e:
        return f"Failed to parse graph: {e}\n\nMake sure you pass the raw output of get_graph."

    graph_json = json.dumps(data)
    html = _build_html(title, graph_json)

    _html_path = os.path.join(_output_dir, "graph.html")
    with open(_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    try:
        page = await get_page()
        console_errors = []
        page.on("console",   lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        await page.goto(f"file://{_html_path}", wait_until="domcontentloaded")

        try:
            await page.wait_for_function("window.__graphReady === true", timeout=20_000)
        except Exception:
            pass

        node_count = await page.evaluate("document.querySelectorAll('.node').length")
        edge_count = await page.evaluate("document.querySelectorAll('.link').length")

        err_info = ""
        if console_errors:
            print("[DEBUG] Browser errors:", console_errors)
            err_info = f"\n⚠ Browser errors: {console_errors[:3]}"

        return (
            f"✅ Graph rendered.\n"
            f"   nodes: {node_count}  edges: {edge_count}\n"
            f"   saved: {_html_path}{err_info}\n\n"
            f"Call screenshot or export_pdf to save it."
        )
    except Exception as e:
        return f"Browser error: {e}\n{traceback.format_exc()}"


@mcp.tool()
async def screenshot(filename: str = "graph_screenshot.png") -> str:
    """
    Take a screenshot of the current graph in the browser.

    Args:
        filename: Output PNG filename (saved to ~/codegrapher_output/).
    """
    try:
        page = await get_page()
        if not filename.endswith(".png"):
            filename += ".png"
        out = os.path.join(_output_dir, filename)
        await page.screenshot(path=out, full_page=False)
        return f"✅ Screenshot saved → {out}"
    except Exception as e:
        return f"Screenshot failed: {e}"


@mcp.tool()
async def export_pdf(filename: str = "graph.pdf") -> str:
    """
    Export the current graph as a PDF.

    Args:
        filename: Output PDF filename (saved to ~/codegrapher_output/).
    """
    try:
        page = await get_page()
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        out = os.path.join(_output_dir, filename)
        await page.pdf(path=out, format="A3", landscape=True, print_background=True)
        return f"✅ PDF saved → {out}"
    except Exception as e:
        return f"PDF export failed: {e}"


@mcp.tool()
async def filter_graph(
    show_modules: bool = True,
    show_classes: bool = True,
    show_functions: bool = True,
    show_calls: bool = True,
    show_inherits: bool = True,
    show_imports: bool = True,
    show_contains: bool = True,
) -> str:
    """
    Toggle visibility of node/edge types in the rendered graph.

    Args:
        show_modules: Show module nodes.
        show_classes: Show class nodes.
        show_functions: Show function nodes.
        show_calls: Show call edges.
        show_inherits: Show inheritance edges.
        show_imports: Show import edges.
        show_contains: Show contains edges.
    """
    try:
        page = await get_page()
        state = {
            "node-module":   show_modules,
            "node-class":    show_classes,
            "node-function": show_functions,
            "edge-calls":    show_calls,
            "edge-inherits": show_inherits,
            "edge-imports":  show_imports,
            "edge-contains": show_contains,
        }
        await page.evaluate(f"window.__filterGraph({json.dumps(state)})")
        lines = [f"  {'on ' if v else 'off'} → {k}" for k, v in state.items()]
        return "Filters applied:\n" + "\n".join(lines)
    except Exception as e:
        return f"Filter failed: {e}"


@mcp.tool()
async def close_browser() -> str:
    """Close the browser window."""
    global _playwright, _browser, _page
    if _browser:
        await _browser.close()
        await _playwright.stop()
        _browser = _page = _playwright = None
    return "Browser closed."


# ── HTML builder ───────────────────────────────────────────────────

def _build_html(title: str, graph_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600&family=Syne:wght@700;800&display=swap');
  :root {{
    --bg:#0a0a0f; --surface:#111118; --border:#1e1e2e;
    --text:#cdd6f4; --muted:#585b70; --accent:#cba6f7;
    --module:#89b4fa; --class:#a6e3a1; --function:#fab387;
    --calls:#f38ba8; --inherits:#a6e3a1; --imports:#89b4fa; --contains:#313244;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'JetBrains Mono',monospace;
          height:100vh; display:flex; flex-direction:column; overflow:hidden; }}
  header {{ display:flex; align-items:center; gap:1rem; padding:.6rem 1.2rem;
            border-bottom:1px solid var(--border); background:var(--surface);
            flex-shrink:0; flex-wrap:wrap; }}
  .logo  {{ font-family:'Syne',sans-serif; font-weight:800; font-size:1rem; color:var(--accent); }}
  .meta  {{ font-size:.65rem; color:var(--muted); }}
  .filters {{ display:flex; gap:.35rem; flex-wrap:wrap; margin-left:auto; }}
  .pill {{ font-size:.62rem; padding:.2rem .55rem; border-radius:99px; border:1px solid;
           cursor:pointer; transition:opacity .15s; font-family:inherit; }}
  .pill.off {{ opacity:.2; }}
  .pill-module   {{ border-color:var(--module);   color:var(--module); }}
  .pill-class    {{ border-color:var(--class);    color:var(--class); }}
  .pill-function {{ border-color:var(--function); color:var(--function); }}
  .pill-calls    {{ border-color:var(--calls);    color:var(--calls); }}
  .pill-inherits {{ border-color:var(--inherits); color:var(--inherits); }}
  .pill-imports  {{ border-color:var(--imports);  color:var(--imports); }}
  .pill-contains {{ border-color:var(--muted);    color:var(--muted); }}
  #canvas {{ flex:1; position:relative; overflow:hidden; }}
  svg {{ width:100%; height:100%; }}
  .node circle {{ stroke-width:1.5; cursor:pointer; }}
  .node:hover circle {{ filter:brightness(1.4); }}
  .node text {{ font-size:9px; fill:var(--text); pointer-events:none; text-anchor:middle; }}
  .node.hidden, .link.hidden {{ display:none; }}
  .link {{ stroke-opacity:.5; stroke-width:1; fill:none; }}
  #info {{ position:absolute; right:1rem; top:1rem; width:270px; background:var(--surface);
           border:1px solid var(--border); border-radius:8px; padding:1rem; font-size:.7rem;
           display:none; max-height:65vh; overflow-y:auto; }}
  #info.on {{ display:block; }}
  #info h3 {{ font-family:'Syne',sans-serif; color:var(--accent); margin-bottom:.5rem;
              word-break:break-all; font-size:.85rem; }}
  #info .row {{ display:flex; gap:.4rem; margin-bottom:.25rem; }}
  #info .key {{ color:var(--muted); min-width:65px; }}
  #info .sec {{ margin-top:.6rem; color:var(--muted); font-size:.6rem;
                text-transform:uppercase; letter-spacing:.08em; }}
  #info ul {{ list-style:none; margin-top:.25rem; }}
  #info li {{ padding:.12rem 0; border-bottom:1px solid var(--border); font-size:.65rem; }}
  #info li:last-child {{ border:none; }}
  #close {{ position:absolute; top:.5rem; right:.6rem; background:none; border:none;
            color:var(--muted); cursor:pointer; font-size:.9rem; }}
  #stats {{ position:absolute; bottom:1rem; left:1rem; font-size:.62rem;
            color:var(--muted); line-height:1.7; }}
  #hint  {{ position:absolute; bottom:1rem; left:50%; transform:translateX(-50%);
            background:var(--surface); border:1px solid var(--border); border-radius:99px;
            padding:.3rem .9rem; font-size:.62rem; color:var(--muted); pointer-events:none; }}
</style>
</head>
<body>
<header>
  <div class="logo">⬡ {title}</div>
  <div class="meta" id="meta-label"></div>
  <div class="filters">
    <span class="pill pill-module"   data-k="node-module">module</span>
    <span class="pill pill-class"    data-k="node-class">class</span>
    <span class="pill pill-function" data-k="node-function">function</span>
    <span class="pill pill-calls"    data-k="edge-calls">calls</span>
    <span class="pill pill-inherits" data-k="edge-inherits">inherits</span>
    <span class="pill pill-imports"  data-k="edge-imports">imports</span>
    <span class="pill pill-contains" data-k="edge-contains">contains</span>
  </div>
</header>
<div id="canvas">
  <svg id="svg"></svg>
  <div id="info">
    <button id="close">✕</button>
    <h3 id="i-title"></h3>
    <div id="i-body"></div>
  </div>
  <div id="stats"></div>
  <div id="hint">scroll to zoom · drag to pan · click node to inspect</div>
</div>
<script>
(function() {{
  const DATA = {graph_json};

  if (!DATA.nodes || DATA.nodes.length === 0) {{
    document.getElementById('hint').textContent = 'No nodes to display.';
    window.__graphReady = true;
    return;
  }}

  const nodeColor = {{ module:'#89b4fa', class:'#a6e3a1', function:'#fab387' }};
  const edgeColor = {{ calls:'#f38ba8', inherits:'#a6e3a1', imports:'#89b4fa', contains:'#313244' }};
  const nodeR     = {{ module:10, class:8, function:5 }};
  const vis = {{
    'node-module':true,'node-class':true,'node-function':true,
    'edge-calls':true,'edge-inherits':true,'edge-imports':true,'edge-contains':true
  }};

  const meta = DATA.meta || {{}};
  document.getElementById('meta-label').textContent =
    `${{meta.total_files||0}} files · ${{DATA.nodes.length}} nodes · ${{DATA.edges.length}} edges`;

  const nc = t => DATA.nodes.filter(n=>n.type===t).length;
  const ec = t => DATA.edges.filter(e=>e.type===t).length;
  document.getElementById('stats').innerHTML =
    `<span style="color:var(--module)">■</span> ${{nc('module')}} modules &nbsp;`+
    `<span style="color:var(--class)">■</span> ${{nc('class')}} classes &nbsp;`+
    `<span style="color:var(--function)">■</span> ${{nc('function')}} functions<br>`+
    `<span style="color:var(--calls)">→</span> ${{ec('calls')}} calls &nbsp;`+
    `<span style="color:var(--inherits)">→</span> ${{ec('inherits')}} inherits &nbsp;`+
    `<span style="color:var(--imports)">→</span> ${{ec('imports')}} imports`;

  const svg = d3.select('#svg');
  const W = window.innerWidth, H = window.innerHeight - 48;
  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([.05,8]).on('zoom', e => g.attr('transform', e.transform)));

  const nodes = DATA.nodes.map(d => ({{...d}}));
  const nodeIds = new Set(nodes.map(n => n.id));
  const links = DATA.edges
    .filter(d => nodeIds.has(d.from) && nodeIds.has(d.to))
    .map(d => ({{...d, source:d.from, target:d.to}}));

  const defs = svg.append('defs');
  Object.entries(edgeColor).forEach(([t,c]) => {{
    defs.append('marker').attr('id',`arr-${{t}}`).attr('viewBox','0 -4 8 8')
      .attr('refX',18).attr('refY',0).attr('markerWidth',5).attr('markerHeight',5)
      .attr('orient','auto')
      .append('path').attr('d','M0,-4L8,0L0,4').attr('fill',c);
  }});

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(d=>d.type==='contains'?60:130).strength(.5))
    .force('charge', d3.forceManyBody().strength(-250))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collide', d3.forceCollide(d=>(nodeR[d.type]||5)+8));

  const link = g.append('g').selectAll('line').data(links).join('line')
    .attr('class', d => `link ${{vis[`edge-${{d.type}}`]?'':'hidden'}}`)
    .attr('stroke', d => edgeColor[d.type]||'#555')
    .attr('marker-end', d => `url(#arr-${{d.type}})`);

  const node = g.append('g').selectAll('g').data(nodes).join('g')
    .attr('class', d => `node ${{vis[`node-${{d.type}}`]?'':'hidden'}}`)
    .call(d3.drag()
      .on('start',(e,d) => {{ if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on('drag', (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on('end',  (e,d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }})
    )
    .on('click', (e,d) => {{ e.stopPropagation(); showInfo(d); }});

  node.append('circle')
    .attr('r', d => nodeR[d.type]||5)
    .attr('fill', d => nodeColor[d.type]||'#888')
    .attr('stroke', d => d3.color(nodeColor[d.type]||'#888').brighter(1));

  node.append('text').attr('dy', d => (nodeR[d.type]||5)+10)
    .text(d => {{
      const l = d.name || d.id.split('::').pop();
      return l.length > 22 ? l.slice(0,20)+'…' : l;
    }});

  sim.on('tick', () => {{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
  }});
  sim.on('end', () => {{ window.__graphReady = true; }});
  window.__graphReady = false;

  function showInfo(d) {{
    document.getElementById('i-title').textContent = d.id;
    const callers  = links.filter(l=>(l.target.id||l.target)===d.id&&l.type==='calls').map(l=>l.source.id||l.source);
    const callees  = links.filter(l=>(l.source.id||l.source)===d.id&&l.type==='calls').map(l=>l.target.id||l.target);
    const inherits = links.filter(l=>(l.source.id||l.source)===d.id&&l.type==='inherits').map(l=>l.target.id||l.target);
    const children = links.filter(l=>(l.source.id||l.source)===d.id&&l.type==='contains').map(l=>l.target.id||l.target);
    let h = `<div class="row"><span class="key">type</span><span style="color:${{nodeColor[d.type]}}">${{d.type}}</span></div>
             <div class="row"><span class="key">module</span><span>${{d.module||'—'}}</span></div>
             ${{d.lineno?`<div class="row"><span class="key">line</span><span>${{d.lineno}}</span></div>`:''}}`;
    if(inherits.length) h+=sec('inherits',inherits);
    if(children.length) h+=sec('contains',children);
    if(callees.length)  h+=sec('calls',callees);
    if(callers.length)  h+=sec('called by',callers);
    document.getElementById('i-body').innerHTML = h;
    document.getElementById('info').classList.add('on');
  }}

  function sec(t, items) {{
    return `<div class="sec">${{t}} (${{items.length}})</div><ul>` +
      items.map(i=>`<li>${{i.split('::').pop()}} <span style="color:var(--muted);font-size:.58rem">${{i}}</span></li>`).join('') +
      `</ul>`;
  }}

  document.getElementById('close').onclick = () => document.getElementById('info').classList.remove('on');
  svg.on('click', () => document.getElementById('info').classList.remove('on'));

  document.querySelectorAll('.pill').forEach(p => {{
    p.addEventListener('click', () => {{
      const k = p.dataset.k; vis[k] = !vis[k]; p.classList.toggle('off', !vis[k]);
      d3.selectAll('.node').classed('hidden', d => !vis[`node-${{d.type}}`]);
      d3.selectAll('.link').classed('hidden', d => !vis[`edge-${{d.type}}`]);
    }});
  }});

  window.__filterGraph = function(state) {{
    Object.entries(state).forEach(([k,v]) => {{
      vis[k] = v;
      document.querySelector(`[data-k="${{k}}"]`)?.classList.toggle('off', !v);
    }});
    d3.selectAll('.node').classed('hidden', d => !vis[`node-${{d.type}}`]);
    d3.selectAll('.link').classed('hidden', d => !vis[`edge-${{d.type}}`]);
  }};
}})();
</script>
</body>
</html>"""


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Output directory: {_output_dir}")
    import asyncio
    asyncio.run(mcp.run_sse_async(host="127.0.0.1", port=3001))
    