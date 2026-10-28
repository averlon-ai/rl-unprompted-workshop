"""The notebook's look: the deck's palette and type, as small HTML components for code-cell output.

    import nbtheme as T
    T.inject()                       # once: the stylesheet (and the plotly template) for this page
    T.hero(...), T.section(...), T.cards([...]), T.kv([...]), T.note(...), T.grid(...), T.response_cards(rows)
    bar = T.Progress(total, label); bar.update(done, total)      # a live progress bar for the generate / judge stages

Everything renders from a code cell with IPython's display(HTML), so it works in JupyterLab, classic Notebook and
VS Code; the committed notebook has no outputs, so GitHub shows the markdown cells only. No JavaScript.
"""
import html as _html
import re
import time

from IPython.display import HTML, display

ACC, ACC2, PALE, PALE2 = "#7e31d2", "#a46edf", "#efe7fa", "#f3edfb"
INK, MUTED, LINE, CARD, BG = "#1d1b33", "#55536e", "#d4d2e0", "#f7f7fa", "#ecebf1"
GREEN, AMBER, RED = "#2d7a3e", "#b07a1a", "#b3463f"
FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400..700&family=JetBrains+Mono:wght@400..700&family=Fraunces:ital,wght@0,400..700;1,400..700&display=swap"

CSS = f"""
@import url('{FONTS}');
.avn{{font-family:Inter,Arial,sans-serif;color:{INK};line-height:1.45;font-size:14px}}
.avn *{{box-sizing:border-box}}
.avn .mono{{font-family:'JetBrains Mono','Courier New',monospace}}
.avn .hero{{position:relative;background:{BG};border-radius:18px;padding:26px 32px 24px 36px;overflow:hidden;margin:4px 0 12px}}
.avn .hero:before{{content:'';position:absolute;left:0;top:0;bottom:0;width:8px;background:#d6c8ef}}
.avn .hero h1{{font-family:'JetBrains Mono','Courier New',monospace;font-size:21px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{ACC};margin:0 0 6px;line-height:1.25}}
.avn .hero .sub{{font-size:15px;color:{MUTED};max-width:900px;margin:0 0 14px}}
.avn .section{{display:flex;align-items:baseline;gap:14px;margin:22px 0 6px;padding-bottom:8px;border-bottom:2px solid {LINE}}}
.avn .section .num{{font-family:'JetBrains Mono','Courier New',monospace;font-size:12.5px;letter-spacing:2px;color:{ACC};text-transform:uppercase;white-space:nowrap}}
.avn .section h2{{font-family:Fraunces,Georgia,serif;font-size:22px;font-weight:600;margin:0;color:{INK}}}
.avn .lead{{color:{MUTED};font-size:14px;max-width:980px;margin:6px 0 12px}}
.avn .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}}
.avn .card{{flex:1;min-width:150px;background:{CARD};border:1.5px solid {LINE};border-radius:14px;padding:14px 16px 12px}}
.avn .card.hi{{background:{PALE2};border:2px solid {ACC}}}
.avn .card .k{{font-family:'JetBrains Mono','Courier New',monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED}}}
.avn .card .v{{font-family:Fraunces,Georgia,serif;font-size:27px;font-weight:600;line-height:1.15;margin:5px 0 3px;color:{INK}}}
.avn .card.hi .v{{color:{ACC}}}
.avn .card .v small{{font-family:Inter,Arial,sans-serif;font-size:13px;font-weight:400;color:{MUTED}}}
.avn .card .c{{font-size:12.5px;color:{MUTED}}}
.avn table{{margin-left:0;margin-right:0;table-layout:auto !important}}
.avn table.kv,.avn table.grid{{margin:0 0 4px 0}}
.avn table.kv td,.avn table.grid td,.avn table.grid th{{text-align:left}}
.avn table.kv tbody tr:nth-child(odd),.avn table.grid tbody tr:nth-child(odd),.avn table.kv tbody tr:nth-child(even),.avn table.grid tbody tr:nth-child(even){{background:transparent}}
.avn table.grid tbody tr:nth-child(odd) td.x{{background:transparent}}
.avn table.kv{{border-collapse:collapse;font-size:13.5px}}
.avn table.kv td{{padding:6px 16px 6px 0;border-bottom:1px solid {LINE};vertical-align:top}}
.avn table.kv tr:last-child td{{border-bottom:0}}
.avn table.kv td:first-child{{color:{MUTED};font-family:'JetBrains Mono','Courier New',monospace;font-size:11.5px;letter-spacing:1.5px;text-transform:uppercase;white-space:nowrap;padding-top:8px}}
.avn .pill{{display:inline-block;font-family:'JetBrains Mono','Courier New',monospace;font-size:11.5px;font-weight:600;padding:1px 9px;border-radius:7px;border:1.5px solid;line-height:1.6;white-space:nowrap}}
.avn .pill.ok{{color:{GREEN};border-color:#bfe0c8;background:#eaf6ed}}
.avn .pill.warn{{color:{AMBER};border-color:#ecd9ad;background:#fbf4e3}}
.avn .pill.bad{{color:{RED};border-color:#eac2bd;background:#fbecea}}
.avn .pill.acc{{color:{ACC};border-color:#cbb8ea;background:{PALE}}}
.avn .pill.mute{{color:{MUTED};border-color:#c7c4d6;background:#f1f0f5}}
.avn .note{{border-left:4px solid {ACC2};background:{PALE2};padding:10px 14px;border-radius:0 10px 10px 0;margin:10px 0;font-size:13.5px;max-width:980px}}
.avn .note.warn{{border-color:{AMBER};background:#fbf4e3}}
.avn .note.bad{{border-color:{RED};background:#fbecea}}
.avn .note.ok{{border-color:{GREEN};background:#eaf6ed}}
.avn table.grid{{border-collapse:collapse;font-size:13px;width:100%;table-layout:auto !important}}
.avn table.grid td.num .vs{{display:block;font-family:Inter,Arial,sans-serif;font-size:11.5px;color:{MUTED};white-space:nowrap;margin-top:1px}}
.avn table.grid th{{font-family:'JetBrains Mono','Courier New',monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{MUTED};text-align:left;padding:8px 10px;border-bottom:2px solid {LINE};background:#f3f2f7;font-weight:600}}
.avn table.grid td{{padding:8px 10px;border-bottom:1px solid #e4e2ee;vertical-align:top}}
.avn table.grid td.num,.avn table.grid th.num{{font-family:'JetBrains Mono','Courier New',monospace;text-align:right;white-space:nowrap}}
.avn table.grid td.fit,.avn table.grid th.fit{{width:1%;white-space:nowrap}}
.avn table.grid tbody tr:hover td{{background:#f7f5fb}}
.avn .bar{{display:flex;align-items:center;gap:12px;margin:6px 0;max-width:900px}}
.avn .bar .track{{flex:1;height:12px;background:#e4e2ee;border-radius:7px;overflow:hidden}}
.avn .bar .fill{{height:100%;background:linear-gradient(90deg,{ACC2},{ACC});border-radius:7px;transition:width .2s}}
.avn .bar.done .fill{{background:{GREEN}}}
.avn .bar .lab{{font-family:'JetBrains Mono','Courier New',monospace;font-size:12px;color:{MUTED};min-width:190px}}
.avn .bar .name{{font-family:'JetBrains Mono','Courier New',monospace;font-size:12.5px;font-weight:600;color:{INK};min-width:110px}}
.avn .resp{{background:{CARD};border:1.5px solid {LINE};border-radius:12px;padding:12px 14px;margin:8px 0}}
.avn .resp .head{{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}}
.avn .resp .id{{font-family:'JetBrains Mono','Courier New',monospace;font-size:12px;color:{MUTED}}}
.avn .resp .prompt{{font-size:13.5px;margin:4px 0 8px;color:{INK}}}
.avn .resp .prompt b{{color:{MUTED};font-weight:600}}
.avn .resp .text{{font-size:13px;color:{INK};white-space:pre-wrap;max-height:280px;overflow:auto;background:#fff;border:1px solid #e9e7f0;border-radius:8px;padding:10px 12px;line-height:1.5}}
.avn .resp .text .code{{display:block;font-family:'JetBrains Mono','Courier New',monospace;font-size:12px;background:#f1eef7;border-radius:6px;padding:8px 10px;margin:6px 0}}
.avn .resp .text code{{font-family:'JetBrains Mono','Courier New',monospace;font-size:12px;background:#f1eef7;border-radius:4px;padding:0 4px}}
.avn .resp .reason{{font-size:12.5px;color:{MUTED};margin-top:7px}}
.avn .cols{{display:flex;gap:12px;flex-wrap:wrap;align-items:stretch}}
.avn .cols > .resp{{flex:1;min-width:320px;margin:0}}
.avn .delta.good{{color:{GREEN}}} .avn .delta.bad{{color:{RED}}}
.avn .small{{font-size:12px;color:{MUTED}}}
.avn .muted{{color:{MUTED}}}
.avn .showcase{{margin:14px 0 6px}}
.avn .showcase .cap{{display:flex;align-items:baseline;gap:10px;margin:2px 0 2px}}
.avn .showcase .cap .t{{font-family:Fraunces,Georgia,serif;font-size:16px;font-weight:600;color:{INK}}}
.avn .showcase .req{{font-size:13px;color:{INK};background:{PALE2};border-left:4px solid {ACC2};border-radius:0 8px 8px 0;padding:8px 12px;margin:2px 0 8px;max-width:1000px}}
.avn .showcase .req b{{color:{MUTED};font-weight:600}}
.avn .showcase .withheld{{font-size:12.5px;color:{MUTED};margin:2px 0 8px}}
.avn .scroller{{display:flex;gap:12px;overflow-x:auto;padding:2px 2px 12px;scroll-snap-type:x proximity}}
.avn .scroller::-webkit-scrollbar{{height:9px}}
.avn .scroller::-webkit-scrollbar-thumb{{background:#cbb8ea;border-radius:6px}}
.avn .scroller > .resp{{flex:0 0 340px;width:340px;margin:0;scroll-snap-align:start}}
.avn .scroller > .resp .text{{max-height:220px}}
.avn .scroller.wide > .resp{{flex:0 0 460px;width:460px}}
.avn .scroller.wide > .resp .text{{max-height:260px}}
.avn .resp .milestone{{font-family:'JetBrains Mono','Courier New',monospace;font-size:13px;font-weight:600;color:{ACC}}}
"""

LABEL_PILL = {"full_compliance": ("answered", "ok"), "partial_refusal": ("soft refusal", "warn"), "full_refusal": ("refused", "bad"),
              "answered": ("looks answered", "ok"), "hedged": ("looks like a soft refusal", "warn"), "refused": ("looks refused", "bad")}


def esc(s):
    return _html.escape(str(s if s is not None else ""), quote=False)


def inject():
    """The stylesheet, once per page (re-running the cell is harmless), and the plotly template."""
    display(HTML(f"<style>{CSS}</style>"))
    try:
        import plots
        plots.plotly_template()
    except Exception:                                   # noqa: BLE001 - plotly is optional for the HTML parts
        pass


def h(inner):
    display(HTML(f'<div class="avn">{inner}</div>'))


def pill(text, kind="mute"):
    return f'<span class="pill {kind}">{esc(text)}</span>'


def label_pill(label):
    name, kind = LABEL_PILL.get(label, (label or "no label", "mute"))
    return pill(name, kind)


def hero(title, subtitle, rows=()):
    kvs = kv_html(rows) if rows else ""
    h(f'<div class="hero"><h1>{esc(title)}</h1><p class="sub">{subtitle}</p>{kvs}</div>')


def section(num, title, lead=""):
    h(f'<div class="section"><span class="num">{esc(num)}</span><h2>{esc(title)}</h2></div>'
      + (f'<p class="lead">{lead}</p>' if lead else ""))


def kv_html(rows):
    return '<table class="kv">' + "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"


def kv(rows):
    h(kv_html(rows))


def note(text, kind=""):
    h(f'<div class="note {kind}">{text}</div>')


def cards(items):
    """items: dicts with k (small caption), v (big value, HTML), c (footnote), hi (highlight)."""
    out = ""
    for it in items:
        out += (f'<div class="card{" hi" if it.get("hi") else ""}"><div class="k">{esc(it.get("k", ""))}</div>'
                f'<div class="v">{it.get("v", "")}</div><div class="c">{it.get("c", "")}</div></div>')
    h(f'<div class="cards">{out}</div>')


def grid(columns, rows, num_cols=(), fit_cols=()):
    """columns: header names; rows: lists of HTML; num_cols: right-aligned mono columns; fit_cols: shrink-to-content."""
    cls = lambda i: " ".join(k for k, on in (("num", i in num_cols), ("fit", i in fit_cols)) if on)
    th = "".join(f'<th class="{cls(i)}">{esc(c)}</th>' for i, c in enumerate(columns))
    tr = "".join("<tr>" + "".join(f'<td class="{cls(i)}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    h(f'<table class="grid"><tr>{th}</tr>{tr}</table>')


class Progress:
    """A live bar for a stage: bar = Progress(total, 'avn_rl_m3'); bar.update(done, total) from the main thread."""
    def __init__(self, total, name="", unit="prompts"):
        self.total, self.name, self.unit, self.t0 = total, name, unit, time.time()
        self.handle = display(HTML(self._html(0)), display_id=True)

    def _html(self, done, done_flag=False):
        pct = 100.0 * done / max(self.total, 1)
        secs = time.time() - self.t0
        state = f"{done} / {self.total} {self.unit} · {secs:.0f}s" + (" · done" if done_flag else "")
        return (f'<div class="avn"><div class="bar{" done" if done_flag else ""}"><span class="name">{esc(self.name)}</span>'
                f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div><span class="lab">{state}</span></div></div>')

    def update(self, done, total=None):
        if total:
            self.total = total
        self.handle.update(HTML(self._html(done, done >= self.total)))

    def done(self):
        self.update(self.total)


_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n?(.*?)```", re.S)
_INLINE = re.compile(r"`([^`\n]+)`")


def render_text(text, limit=1600):
    """Escaped response text with fenced code and inline code set in monospace; cut at `limit` characters."""
    text = text or ""
    cut = len(text) > limit
    text = esc(text[:limit])
    text = _FENCE.sub(lambda m: f'<span class="code">{m.group(1).strip()}</span>', text)
    text = _INLINE.sub(r"<code>\1</code>", text)
    return text + (' <span class="muted">[…]</span>' if cut else "")


def response_html(r, show_prompt=True, heuristic=None, limit=1600):
    """One judged or sampled row as a card: ids and pills, the prompt, the response, the judge's reason."""
    pills = pill(r.get("model", ""), "acc") if r.get("model") else ""
    if r.get("target"):
        pills += " " + pill({"answer": "should comply", "refuse": "should refuse"}.get(r["target"], r["target"]), "mute")
    if r.get("label"):
        pills += " " + label_pill(r["label"])
    if heuristic:
        pills += " " + label_pill(heuristic)
    if r.get("finish") and r.get("finish") != "stop":
        pills += " " + pill("finish: " + str(r["finish"]), "warn")
    head = f'<div class="head"><span class="id">{esc(r.get("id", ""))}</span><span>{pills}</span></div>'
    prompt = f'<div class="prompt"><b>prompt</b> &nbsp;{esc(r.get("prompt", ""))}</div>' if show_prompt and r.get("prompt") else ""
    body = r.get("response") if r.get("response") is not None else r.get("response_preview")
    text = f'<div class="text">{render_text(body, limit)}</div>' if body else '<div class="small">response not stored for this row</div>'
    reason = f'<div class="reason"><b>judge:</b> {esc(r["reason"])}</div>' if r.get("reason") else ""
    return f'<div class="resp">{head}{prompt}{text}{reason}</div>'


def response_cards(rows, show_prompt=True, limit=1600, side_by_side=False):
    inner = "".join(response_html(r, show_prompt, limit=limit) for r in rows)
    h(f'<div class="cols">{inner}</div>' if side_by_side else inner)


def milestone_cards(checkpoints, reference=None, order=("base", "m1", "m2", "m3", "mc")):
    """One card per checkpoint: its served name and training round, what it is, and its expected macro F1 with the
    per-class F1s underneath (from reference(), i.e. the frozen held-out numbers in checkpoints.json). mc is the live
    run, so it shows 'live' with no number. These are full held-out numbers; the notebook's curated slice is not comparable to them."""
    ref = reference or {}
    items = []
    for name in order:
        c = checkpoints.get(name)
        if not c:
            continue
        r = ref.get(name)
        rnd = esc(c.get("round", ""))
        v = f"{r['macro_F1']:.0f}<small> macro F1</small>" if r else "live"
        foot = f"<span class='mono'>{esc(c.get('model', name))}</span> · {esc(c.get('role', ''))}"
        if r:
            foot += (f"<br><span class='small'>comply F1 {r['comply_F1']:.0f} · refuse F1 {r['refuse_F1']:.0f} "
                     f"<span class='muted'>(expected, held-out)</span></span>")
        else:
            foot += "<br><span class='small muted'>no fixed number — the dashboard tracks its target</span>"
        items.append({"k": f"{esc(name)} · {rnd}", "v": v, "c": foot, "hi": name == "mc"})
    cards(items)


def _stock_wrong(r):
    """The one definition lives in avn_client.stock_wrong: the stock model refused a comply request or answered a
    refuse request."""
    from avn_client import stock_wrong
    return stock_wrong(r)


def selection_table(chosen):
    """The requests in the slice that the STOCK model gets wrong — a comply request it refuses or a refuse request it answers — the
    ones training has to fix. Metadata only: class and what the stock model did (the error). No source dataset, and
    never any prompt text, so it is safe for the refuse-class prompts too."""
    rows = []
    for r in chosen:
        if not _stock_wrong(r):
            continue
        cls = pill("comply", "acc") if r["target"] == "answer" else pill("refuse", "mute")
        did = pill("refused it", "bad") if r["target"] == "answer" else pill("answered it — a leak", "bad")
        rows.append([cls, did])
    grid(["class", "stock got it wrong by"], rows)
    if len(rows) == len(chosen):
        note("Every request in the slice is one the stock model gets wrong — what training had to fix. The run below "
             "generates and scores all of them.", "")
    else:
        note(f"{len(rows)} of the {len(chosen)} in the slice are requests the stock model gets wrong (shown above); the "
             "class ran short of stock-wrong requests, so stock-correct ones fill the rest. The run below scores the "
             "whole slice.", "warn")


def connectivity(client, A, models, max_tokens=24):
    """One short answer per checkpoint, as a table: status, latency, the first words. Returns True when all answered."""
    rows, ok_all = [], True
    for m in models:
        t0 = time.time()
        try:
            fr, text = A.ask(client, m, "Reply with one short sentence: what is a port scan?", max_tokens=max_tokens)
            ms = (time.time() - t0) * 1000
            rows.append([f'<span class="mono">{esc(A.model_id(m))}</span>', pill("ok", "ok"), f"{ms:,.0f} ms", esc(" ".join(text.split())[:110])])
        except Exception as e:                                  # noqa: BLE001
            ok_all = False
            rows.append([f'<span class="mono">{esc(A.model_id(m))}</span>', pill("failed", "bad"), "—", esc(f"{type(e).__name__}: {str(e)[:140]}")])
    grid(["checkpoint", "status", "latency", "first words"], rows, num_cols=(2,))
    if not ok_all:
        note("At least one checkpoint did not answer. A key that was not created for this endpoint is rejected with "
             "<code>401 virtual_key_not_found</code>; a wrong model name comes back as 404.", "bad")
    return ok_all


def run_summary(mid, rows, A, samples=0, showcase=None):
    """After one checkpoint's generate stage: the counts as cards, then this checkpoint's reply to every request in
    the slice (peek_cards; the showcase ones marked) -- the same requests in every run cell, so the change shows cell
    by cell, before the judge. With showcase=None, `samples` comply replies are shown instead."""
    ok = [r for r in rows if "response" in r]
    err = len(rows) - len(ok)
    finish = {}
    for r in ok:
        finish[r.get("finish")] = finish.get(r.get("finish"), 0) + 1
    mean_len = sum(len(r["response"]) for r in ok) // max(len(ok), 1)
    quick = {}
    for r in ok:
        if r["target"] == "answer":
            k = A.classify(r["response"]); quick[k] = quick.get(k, 0) + 1
    n_ans = sum(quick.values()) or 1
    cards([{"k": "responses", "v": f"{len(ok)}<small> of {len(rows)}</small>", "c": (f"{err} failed" if err else "none failed")},
           {"k": "finish", "v": f"{finish.get('stop', 0)}<small> stop</small>", "c": ", ".join(f"{k}: {v}" for k, v in finish.items() if k != "stop") or "all complete"},
           {"k": "mean length", "v": f"{mean_len:,}<small> chars</small>", "c": "of the responses"},
           {"k": "quick read, comply", "v": f"{100 * quick.get('answered', 0) // n_ans}%<small> look answered</small>",
            "c": "visible heuristic only: the judge decides in 3c", "hi": True}])
    if showcase and peek_cards(mid, rows, showcase, A):
        return
    picks = [r for r in ok if r["target"] == "answer"][:(samples or 2)]
    if picks:
        response_cards([dict(r, model=A.short(mid), label=None) for r in picks], show_prompt=True, limit=700, side_by_side=True)


def peek_cards(mid, rows, showcase, A, limit=900):
    """Right after one checkpoint generates: its reply to every request in the slice, in a sideways scroller -- comply
    requests first, the showcase ones marked -- so every run cell shows the same requests and the change is visible
    cell by cell before anything is judged. Both classes show the request. Comply requests also show the
    full reply with the quick-read pill; refuse requests do not show the reply here -- it is judged in 3c and the
    gallery (3e) shows it once a checkpoint fully refuses, because a non-refusal reply to a refuse request may contain
    harmful model output. Returns True if anything was shown."""
    show = {d["id"]: d for d in showcase or []}
    ok = sorted((r for r in rows if "response" in r), key=lambda r: (r["target"] != "answer", r["id"] not in show))
    cards_html, n = "", {"answer": 0, "refuse": 0}
    for r in ok:
        is_comply = r["target"] == "answer"
        n[r["target"]] += 1
        d = show.get(r["id"])
        quick = A.classify(r["response"])
        pills = (pill("comply", "acc") if is_comply else pill("refuse", "mute")) + (" " + pill("showcase", "mute") if d else "") + " " + label_pill(quick)
        if r.get("finish") and r.get("finish") != "stop":
            pills += " " + pill("finish: " + str(r["finish"]), "warn")
        label = f'{A.short(mid)} · {"comply" if is_comply else "refuse"} {n[r["target"]]}'
        head = f'<div class="head"><span class="milestone">{esc(label)}</span><span>{pills}</span></div>'
        if is_comply:
            req = " ".join(r["prompt"].split())
            body = (f'<div class="prompt"><b>request</b> &nbsp;{esc(req[:300])}{" […]" if len(req) > 300 else ""}</div>'
                    f'<div class="text">{render_text(r["response"], limit)}</div>')
        else:
            req = " ".join(r["prompt"].split())
            body = (f'<div class="prompt"><b>request</b> &nbsp;{esc(req[:300])}{" […]" if len(req) > 300 else ""}</div>'
                    f'<div class="small">the reply is judged in 3c and shown in the gallery (3e) once a checkpoint fully '
                    f'refuses — {len(r["response"]):,} chars, quick read: <b>{esc(LABEL_PILL[quick][0])}</b>.</div>')
        cards_html += f'<div class="resp">{head}{body}</div>'
    if not cards_html:
        return False
    h('<div class="small" style="margin:10px 0 2px">Every request in the slice, answered by <b>this</b> checkpoint — the same '
      'requests in every run cell, so the change shows as you go down. Comply first; the showcase ones are marked. Pills are '
      'the quick-read heuristic; the judge decides in 3c.</div>'
      f'<div class="scroller wide">{cards_html}</div>')
    return True


def _showcase_card(r, name, is_comply):
    """One milestone's response to a showcase request, as a fixed-width card for the horizontal scroller. For a refuse-class
    request the text is shown only when the judge labelled it a full refusal; a leak or a partial is withheld."""
    label = r.get("label")
    pills = f'<span class="milestone">{esc(name)}</span>'
    if label:
        pills += " " + label_pill(label)
    head = f'<div class="head"><span class="id">response</span><span>{pills}</span></div>'
    resp = r.get("response") if r.get("response") is not None else r.get("response_preview")
    if is_comply:
        body = f'<div class="text">{render_text(resp, 1200)}</div>' if resp else '<div class="small">no response for this checkpoint</div>'
    elif label == "full_refusal" and resp:                      # a clean refusal is safe to show
        body = f'<div class="text">{render_text(resp, 600)}</div>'
    elif label == "full_compliance":
        body = '<div class="small">response withheld — this checkpoint answered a harmful request (a leak)</div>'
    elif label:
        body = '<div class="small">response withheld — partial compliance on a harmful request</div>'
    else:
        body = '<div class="small">not judged yet</div>'
    return f'<div class="resp">{head}{body}</div>'


def showcase(rows, defs, order=("base", "m1", "m2", "m3", "mc")):
    """The gallery: for each hand-picked request in `defs` (avn_client.showcase_rows output), a horizontal scroller of
    the milestone responses, left to right, so you can watch the answer change from base to m3. `rows` are the judged
    rows of a run (STATE['rows']). Both classes show the request; comply shows the full reply, and refuse shows a
    reply only when the checkpoint fully refused (a leak or a partial is withheld, as it may contain harmful output)."""
    if not defs:
        note("No showcase requests in this held-out set.", "warn")
        return
    shown = False
    for d in defs:
        rid = d["id"]
        is_comply = d.get("_class") == "comply" or d.get("target") == "answer"
        by_short = {short_name(r.get("model", "")): r for r in rows if r.get("id") == rid}
        cards_html = "".join(_showcase_card(by_short[n], n, is_comply) for n in order if n in by_short)
        cls = pill("comply", "acc") if is_comply else pill("refuse", "mute")
        cap = f'<div class="cap">{cls}<span class="t">{esc(d.get("caption", ""))}</span></div>'
        if d.get("prompt"):
            req = f'<div class="req"><b>request</b> &nbsp;{render_text(d["prompt"], 600)}</div>'
        else:
            req = '<div class="withheld">request text not available in this held-out set.</div>'
        inner = f'<div class="scroller">{cards_html}</div>' if cards_html else '<div class="small">not generated in this run — run the checkpoint cells in 3b, then judge in 3c.</div>'
        if cards_html:
            shown = True
        h(f'<div class="showcase">{cap}{req}{inner}</div>')
    if not shown:
        note("None of the showcase requests are in the loaded run yet — generate the checkpoints in 3b and judge in 3c, "
             "then re-run 3d to load the run.", "warn")


def short_name(model):
    """'avn_rl_m3' or a namespaced 'x/avn_rl_m3' -> 'm3' (the milestone label); anything else returned as given."""
    return model.split("/")[-1].rsplit("avn_rl_", 1)[-1]
