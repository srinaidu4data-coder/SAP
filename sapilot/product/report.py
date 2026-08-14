"""Write a consultant HTML report for a research sitting."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def report_name() -> str:
    return "REPORT.html"


def report_url(job_id: str) -> str:
    return f"/research/{job_id}"


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _fmt(n: Any) -> str:
    if n is None:
        return "—"
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return _esc(n)


def _drill_html(drill: dict) -> str:
    if not drill:
        return "<p class='mut'>No display drill-through on this sitting.</p>"
    layers = drill.get("layers") or {}
    cyc = ""
    for c in drill.get("cycles") or []:
        hops = "".join(
            f"<li><b>{_esc(s.get('tcode'))}</b> ({_esc(s.get('phase'))}) — {_esc(s.get('purpose'))}</li>"
            for s in (c.get("showable") or [])[:12]
        )
        flag = "SHOWABLE E2E" if c.get("can_walk_e2e") else "partial"
        cyc += (
            f"<div class='scen'><div class='st'>{flag} · {_esc(c.get('name'))}</div>"
            f"<b>{_esc(c.get('title'))}</b><div class='mut'>{_esc(c.get('spine'))}</div>"
            f"<ul>{hops}</ul></div>"
        )
    walk = "".join(
        f"<li><b>{_esc(s.get('tcode'))}</b> — {_esc(s.get('purpose'))}</li>"
        for s in (drill.get("display_walk") or [])
    )
    return (
        f"<p>{_esc(drill.get('story'))}</p>"
        f"<p class='mut'>Layers — config {layers.get('config', 0)}, "
        f"master {layers.get('master', 0)}, transactional {layers.get('transaction', 0)}, "
        f"total {layers.get('total', 0)}. {_esc(drill.get('dictionary') or '')}</p>"
        f"{cyc}<h2>Display-only walk of the named process</h2><ul>{walk}</ul>"
    )


def render_html(job: dict) -> str:
    jid = _esc(job.get("id") or "")
    title = _esc(job.get("title") or job.get("asked") or "Research")
    asked = _esc(job.get("asked") or "")
    spine = _esc(job.get("spine") or "")
    status = _esc(job.get("status") or "")
    prog = job.get("progress") or {}
    counts = job.get("counts") or []
    visits = job.get("visits") or []
    hops = job.get("hops") or []
    scenarios = job.get("scenarios") or []
    narrative = job.get("narrative") or []
    questions = job.get("questions") or []
    live = [c for c in counts if c.get("entries_found") is not None]
    zeros = [c for c in live if c.get("entries_found") == 0]
    miss = [c for c in counts if c.get("entries_found") is None]

    tiles = []
    for c in live:
        cls = " zero" if c.get("entries_found") == 0 else ""
        tiles.append(
            f"<div class='tile{cls}'><em>{_esc(c.get('table'))}</em>"
            f"<b>{_fmt(c.get('entries_found'))}</b></div>"
        )

    hop_li = "".join(f"<li>{_esc(h)}</li>" for h in hops)
    qs_li = "".join(f"<li>{_esc(q)}</li>" for q in questions)
    narr = "".join(f"<p>{_esc(p)}</p>" for p in narrative if p)
    scens = "".join(
        f"<div class='scen'><div class='st'>{_esc(s.get('status') or 'OPEN')}</div>"
        f"<div>{_esc(s.get('text'))}</div></div>"
        for s in scenarios
    )

    figs = []
    for v in visits:
        shot = Path(str(v.get("shot") or "")).name
        if not shot:
            continue
        figs.append(
            "<figure><img src='/api/research/"
            f"{jid}/file/{_esc(shot)}' alt='{_esc(v.get('tcode'))}'/>"
            f"<figcaption>{_esc(v.get('tcode'))} — {_esc(v.get('title'))}</figcaption></figure>"
        )
    for c in counts:
        shot = Path(str(c.get("shot") or "")).name
        if not shot or c.get("entries_found") is None:
            continue
        if not any(x in shot for x in ("_count", "_popup", "_sel")):
            continue
        figs.append(
            "<figure><img src='/api/research/"
            f"{jid}/file/{_esc(shot)}' alt='{_esc(c.get('table'))}'/>"
            f"<figcaption>{_esc(c.get('table'))} = {_fmt(c.get('entries_found'))}</figcaption></figure>"
        )

    rows = []
    for c in counts:
        rows.append(
            "<tr>"
            f"<td>{_esc(c.get('table'))}</td>"
            f"<td>{_fmt(c.get('entries_found'))}</td>"
            f"<td>{_esc(c.get('rank'))}</td>"
            f"<td>{_esc((c.get('notes') or '')[:180])}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>SAPILOT research — {title}</title>
<style>
  :root {{ --bg:#0b1020; --card:#141b2e; --line:#2a3354; --txt:#eef2ff; --mut:#93a0c4; --acc:#7c93ff; --warn:#f5c16c; }}
  body{{margin:0;background:var(--bg);color:var(--txt);font:16px/1.5 "Segoe UI",system-ui,sans-serif}}
  header{{padding:1.2rem 1.6rem;border-bottom:1px solid var(--line)}}
  main{{max-width:980px;margin:0 auto;padding:1.4rem 1.6rem 3rem}}
  h1{{margin:.2rem 0 .35rem;font-size:1.7rem}}
  .spine{{color:var(--acc)}}
  .mut{{color:var(--mut)}}
  h2{{margin:1.6rem 0 .5rem;font-size:.8rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}}
  .tiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.45rem}}
  .tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.55rem}}
  .tile em{{display:block;font-style:normal;color:var(--mut);font-size:.72rem}}
  .tile.zero b{{color:var(--warn)}}
  .scen{{border:1px solid var(--line);border-radius:12px;padding:.75rem;margin:.4rem 0;background:var(--card)}}
  .st{{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--acc)}}
  .thumbs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.5rem}}
  figure{{margin:0;background:#080c18;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
  figure img{{width:100%;display:block;aspect-ratio:16/10;object-fit:cover}}
  figcaption{{padding:.35rem .5rem;font-size:.75rem;color:var(--mut)}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th,td{{text-align:left;padding:.3rem .4rem;border-bottom:1px solid #1c253c;vertical-align:top}}
  th{{color:var(--mut)}}
  a{{color:var(--acc)}}
</style>
</head>
<body>
<header>
  <div class="mut">SAPILOT live glass research · display never creates · sitting {jid} · {status}</div>
  <h1>{title}</h1>
  <div class="spine">{spine}</div>
  <p class="mut">Asked: {asked}</p>
</header>
<main>
  <p>Sitting <b>{_esc(prog.get('done') or 0)}</b> / {_esc(prog.get('total') or job.get('universe') or 0)}
     · LIVE tables {len(live)} · empty {len(zeros)} · not proven {len(miss)}
     · display hops {len(visits)}. Counts are Number of Entries (F7). Nothing was created or posted.</p>
  <h2>What the numbers mean together</h2>
  {narr or "<p class='mut'>Report fills as F7 counts land.</p>"}
  <h2>Opened tables — what is on the glass</h2>
  {"".join(
        f"<div class='scen'><div class='st'>{_esc(s.get('table'))}</div><p>{_esc(s.get('story'))}</p>"
        f"<p class='mut'>Columns: {_esc(', '.join(s.get('columns') or [])[:240])}</p></div>"
        for s in (job.get("studies") or [])
    ) or "<p class='mut'>No table has been opened yet.</p>"}
  <h2>Live census</h2>
  <div class="tiles">{"".join(tiles) or "<p class='mut'>No proven counts yet.</p>"}</div>
  <h2>End-to-end display drill-through</h2>
  {_drill_html(job.get("drill") or {})}
  <h2>Multi-hop</h2>
  <ul>{hop_li or "<li class='mut'>Hops appear after paired tables are counted.</li>"}</ul>
  <h2>Scenario analysis</h2>
  {scens or "<p class='mut'>No scenarios on this process yet.</p>"}
  <h2>Evidence on the glass</h2>
  <div class="thumbs">{"".join(figs) or "<p class='mut'>Screenshots attach as the operator works.</p>"}</div>
  <h2>Still ask on the glass</h2>
  <ul>{qs_li}</ul>
  <h2>Every table this sitting</h2>
  <table>
    <thead><tr><th>Table</th><th>Entries</th><th>Rank</th><th>Notes</th></tr></thead>
    <tbody>{"".join(rows) or "<tr><td colspan='4'>None yet</td></tr>"}</tbody>
  </table>
  <p class="mut">Open this sitting in the product console: <a href="/?job={jid}">http://127.0.0.1:8800/?job={jid}</a></p>
</main>
</body>
</html>
"""


def write_report(job: dict) -> Path | None:
    dest = job.get("dir")
    if not dest:
        return None
    path = Path(dest) / report_name()
    path.write_text(render_html(job), encoding="utf-8")
    job["report_file"] = str(path)
    job["report_url"] = report_url(str(job.get("id") or ""))
    return path
