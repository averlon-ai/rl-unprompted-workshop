"""Plots for the two-stage eval.

PNG figures, written by judge.py into results/<UTC>/plots/ and embedded in report.md (each has a table twin in
report.md / metrics.json, so no value is reachable only by colour):
  f1.png      macro F1, comply F1 and refuse F1 per checkpoint (this run's measured numbers)
  pr.png      precision and recall per checkpoint, for each class (comply vs refuse)
  labels.png  the label mix per checkpoint and target: answered / soft refusal / refused (one hue, light -> dark)
  trend.png   macro F1 across the runs under results/, when there are at least two
make_plots() writes them; report_section() is the markdown that embeds them.

For the notebook: scorecard_html, a compact HTML table of this run's precision, recall and F1 per checkpoint next to
the expected numbers, and plotly_f1 (hover and zoom).

Palette: one accent (the brand violet) against a de-emphasis grey, and a single-hue ordinal ramp for the label
mix - forms whose separation rests on lightness, with a legend and selective direct labels, so they stay readable
without colour.
"""
import glob
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ACCENT, ACCENT_MID, ACCENT_PALE = "#7E31D2", "#A46EDF", "#CDB8EC"
CONTEXT = "#BDBAC9"                        # the reference / de-emphasis grey
INK, INK2, GRID, SURFACE = "#1D1B33", "#55536E", "#E4E2EA", "#FCFCFB"
ORDER = ["base", "m1", "m2", "m3", "mc"]
MODEL_RAMP = {"base": "#B9B6CC", "m1": "#C8A8EC", "m2": ACCENT_MID, "m3": ACCENT, "mc": "#3F1A74"}   # training order, light -> dark
LABELS = [("full_compliance", "answered", ACCENT_PALE), ("partial_refusal", "soft refusal", ACCENT_MID),
          ("full_refusal", "refused", ACCENT)]
NAN = float("nan")


def _num(v):
    """A metric value as a float, NaN when missing or None."""
    return float(v) if isinstance(v, (int, float)) else NAN


def _models(metrics):
    return [m for m in ORDER if m in metrics] + [m for m in metrics if m not in ORDER]


model_order = _models                       # the public name: checkpoints in training order


def _style(ax, ylabel=None, ylim=(0, 100)):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_ylim(*ylim)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def _bars(ax, models, vals, title="", color=ACCENT, err=None):
    """One thin bar per model, directly labelled."""
    x = list(range(len(models)))
    ax.bar(x, vals, 0.5, color=color, zorder=3, edgecolor=SURFACE, linewidth=2)
    if err is not None:
        ax.errorbar(x, vals, yerr=err, fmt="none", ecolor=INK2, elinewidth=1, capsize=3, zorder=4)
    for i, v in zip(x, vals):
        if v == v:
            top = v + (err[i] if err is not None and err[i] == err[i] else 0)
            ax.text(i, top + 2, f"{v:.0f}", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=8)


def _grouped(ax, models, measured, reference, err=None, title="",
             labels=("this test", "reference (full held-out set)"), colors=(ACCENT, CONTEXT)):
    """Thin paired bars with a 2px surface gap between fills."""
    x = list(range(len(models)))
    w, g = 0.32, 0.012
    ax.bar([i - w / 2 - g for i in x], measured, w, color=colors[0], label=labels[0], zorder=3,
           edgecolor=SURFACE, linewidth=2)
    ax.bar([i + w / 2 + g for i in x], reference, w, color=colors[1], label=labels[1],
           zorder=3, edgecolor=SURFACE, linewidth=2)
    if err is not None:
        ax.errorbar([i - w / 2 - g for i in x], measured, yerr=err, fmt="none", ecolor=INK2, elinewidth=1,
                    capsize=3, zorder=4)
    for k, (i, v) in enumerate(zip(x, measured)):
        if v == v:                                        # not NaN: direct-label the measured value, above its noise bar
            top = v + (err[k] if err is not None and err[k] == err[k] else 0)
            ax.text(i - w / 2 - g, top + 2, f"{v:.0f}", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=8)


def _fig(ncols, width=11.5, height=3.9):
    fig, axes = plt.subplots(1, ncols, figsize=(width, height), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    return fig, (list(axes) if ncols > 1 else [axes])


def _finish(fig, path, legend_from=None):
    if legend_from is not None:
        h, l = legend_from.get_legend_handles_labels()
        fig.legend(h, l, loc="upper right", ncol=len(l), frameon=False, fontsize=9, labelcolor=INK2,
                   bbox_to_anchor=(0.99, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_pr(metrics, path):
    """Precision and recall per checkpoint, for each class (comply vs refuse)."""
    models = _models(metrics)
    fig, (a1, a2) = _fig(2)
    for ax, ukey, bkey, title in ((a1, "comply_P", "refuse_P", "precision"), (a2, "comply_R", "refuse_R", "recall")):
        ub = [_num(metrics[m].get(ukey)) for m in models]
        bl = [_num(metrics[m].get(bkey)) for m in models]
        _style(ax)
        _grouped(ax, models, ub, bl, None, title, labels=("comply", "refuse"), colors=(ACCENT, ACCENT_MID))
    return _finish(fig, path, legend_from=a1)


def plot_f1(metrics, path):
    """Macro F1 and the two per-class F1s per checkpoint (this run's measured numbers)."""
    models = _models(metrics)
    fig, axes = _fig(3, width=13)
    for ax, key, title in zip(axes, ("macro_F1", "comply_F1", "refuse_F1"),
                              ("macro F1 (the headline)", "comply F1", "refuse F1")):
        _style(ax)
        _bars(ax, models, [_num(metrics[m].get(key)) for m in models], title)
    return _finish(fig, path)


def plot_labels(rows, path):
    """Label mix per (checkpoint, target) as horizontal stacked bars: answered / soft refusal / refused."""
    models = _models({r["model"]: 1 for r in rows})
    groups = []                                           # (row name, [pct per label], n)
    for m in models:
        for target, tname in (("answer", "should answer"), ("refuse", "should refuse")):
            rs = [r for r in rows if r["model"] == m and r["target"] == target and r.get("label")]
            n = len(rs)
            counts = [sum(1 for r in rs if r["label"] == key) for key, _, _ in LABELS]
            if n:
                groups.append((f"{m} · {tname}", [100.0 * c / n for c in counts], n))
    fig, (ax,) = _fig(1, width=11.5, height=1.1 + 0.42 * len(groups))
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_xlim(0, 100)
    ys = list(range(len(groups)))[::-1]
    for (name, pcts, n), y in zip(groups, ys):
        left = 0.0
        for (key, lname, color), pct in zip(LABELS, pcts):
            ax.barh(y, pct, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=2, zorder=3,
                    label=lname if y == ys[0] else None)
            if pct >= 9:                                   # direct label only where it fits
                ax.text(left + pct / 2, y, f"{pct:.0f}%", ha="center", va="center", fontsize=8.5,
                        color=INK if color != ACCENT else SURFACE)
            left += pct
        ax.text(101, y, f"n={n}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(ys)
    ax.set_yticklabels([g[0] for g in groups], fontsize=9, color=INK)
    ax.set_xlabel("share of judged responses, %", color=INK2, fontsize=9)
    ax.set_title("what the judge saw: answered / soft refusal / refused", loc="left", fontsize=11, color=INK, pad=8)
    return _finish(fig, path, legend_from=ax)


def _load_runs(results_root):
    """(run time, metrics dict) for every results/<UTC>/metrics.json, oldest first; both schemas."""
    runs = []
    for p in sorted(glob.glob(os.path.join(results_root, "*", "metrics.json"))):
        try:
            d = json.load(open(p))
            m = d.get("metrics") or {}
            if m:
                runs.append((os.path.basename(os.path.dirname(p)), m))
        except Exception:                                  # noqa: BLE001 - a broken run is skipped
            pass
    return runs


def plot_trend(results_root, path):
    """Macro F1 across runs under results/, one line per checkpoint (ordinal ramp base -> m3, mc grey dashed).
    Returns None when there are fewer than two runs."""
    runs = _load_runs(results_root)
    if len(runs) < 2:
        return None
    models = _models({m: 1 for _, mm in runs for m in mm})
    ramp = MODEL_RAMP
    xs = list(range(len(runs)))
    fig, (ax,) = _fig(1, width=8)
    _style(ax)
    for m in models:
        ys = [mm.get(m, {}).get("macro_F1", NAN) for _, mm in runs]
        ax.plot(xs, ys, color=ramp.get(m, CONTEXT), linewidth=2, marker="o", markersize=5,
                linestyle="--" if m == "mc" else "-", label=m, zorder=3)
        last = [(x, y) for x, y in zip(xs, ys) if y == y]
        if last:
            ax.text(last[-1][0] + 0.08, last[-1][1], m, fontsize=8.5, color=INK, va="center")
    ax.set_xticks(xs)
    ax.set_xticklabels([t[:13].replace("T", " ") for t, _ in runs], rotation=30, ha="right", fontsize=8)
    ax.set_title("macro F1 by run", loc="left", fontsize=11, color=INK, pad=8)
    return _finish(fig, path, legend_from=ax)


def make_plots(rows, metrics, ref, out_dir, results_root=None):
    """Write the figures into out_dir/plots/. Returns [(file name, caption)] for the report."""
    pdir = os.path.join(out_dir, "plots")
    os.makedirs(pdir, exist_ok=True)
    figs = []
    if metrics:
        plot_f1(metrics, os.path.join(pdir, "f1.png"))
        figs.append(("f1.png", "Macro F1 and the two per-class F1s per checkpoint (this run's measured numbers)."))
        plot_pr(metrics, os.path.join(pdir, "pr.png"))
        figs.append(("pr.png", "Precision and recall per checkpoint, for each class (comply vs refuse)."))
    if any(r.get("label") for r in rows):
        plot_labels(rows, os.path.join(pdir, "labels.png"))
        figs.append(("labels.png", "The judge's label mix per checkpoint and class - soft refusals shown separately from "
                                   "full refusals."))
    if results_root and plot_trend(results_root, os.path.join(pdir, "trend.png")):
        figs.append(("trend.png", "Macro F1 across the runs in results/, one line per checkpoint."))
    return figs


def report_section(figs):
    """Markdown to append to report.md."""
    if not figs:
        return ""
    return "\n## Plots\n\n" + "\n\n".join(f"![{n}](plots/{n})\n\n*{c}*" for n, c in figs) + "\n"


# ------------------------------------------------------------------------------------------ interactive twins
def _m(d, key):
    """A metric by its current key, falling back to the pre-rename key, so a run judged before comply_* replaced
    unblock_* still renders in the dashboard."""
    return d.get(key, d.get(key.replace("comply_", "unblock_"))) if d else None


FONT = "Inter, Arial, sans-serif"
MONO = "JetBrains Mono, Courier New, monospace"
_PLOTLY_LAYOUT = dict(plot_bgcolor=SURFACE, paper_bgcolor="#FFFFFF", font=dict(color=INK, size=13, family=FONT),
                      margin=dict(l=50, r=30, t=60, b=50),
                      hoverlabel=dict(bgcolor=INK, bordercolor=INK, font=dict(color="#FFFFFF", family=FONT, size=12)),
                      legend=dict(orientation="h", y=1.18, x=0, font=dict(size=12, color=INK2)))


def plotly_template():
    """Register and select the "avn" plotly template (paper white, surface card, Inter, quiet grid)."""
    import plotly.graph_objects as go
    import plotly.io as pio
    axis = dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(size=12, color=INK2),
                title=dict(font=dict(size=12, color=INK2)))
    pio.templates["avn"] = go.layout.Template(layout=go.Layout(
        plot_bgcolor=SURFACE, paper_bgcolor="#FFFFFF", font=dict(color=INK, size=13, family=FONT),
        hoverlabel=_PLOTLY_LAYOUT["hoverlabel"], xaxis=axis, yaxis=axis, colorway=[ACCENT, CONTEXT, ACCENT_MID, ACCENT_PALE],
        margin=dict(l=50, r=30, t=60, b=50)))
    pio.templates.default = "avn"
    return pio.templates["avn"]


def _titles(fig):
    """Subplot titles in the deck's small-caps mono."""
    fig.update_annotations(font=dict(family=MONO, size=12, color=INK2))
    return fig


def plotly_f1(metrics, ref):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    models = _models(metrics)
    has_ref = any(ref.get(m) for m in models)
    fig = make_subplots(rows=1, cols=3, subplot_titles=("macro F1 (the headline)", "comply F1 (answer when it should)",
                                                       "refuse F1 (refuse when it should)"))
    for col, key in enumerate(("macro_F1", "comply_F1", "refuse_F1"), start=1):
        fig.add_bar(x=models, y=[_m(metrics[m], key) for m in models], name="this test", marker_color=ACCENT,
                    showlegend=(col == 1 and has_ref), row=1, col=col, hovertemplate="%{x}: %{y:.1f}<extra>this test</extra>")
        if has_ref:
            fig.add_bar(x=models, y=[ref.get(m, {}).get(key) for m in models], name="reference", marker_color=CONTEXT,
                        showlegend=(col == 1), row=1, col=col, hovertemplate="%{x}: %{y:.1f}<extra>reference</extra>")
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, height=360, **_PLOTLY_LAYOUT)
    fig.update_yaxes(range=[0, 100], gridcolor=GRID)
    return _titles(fig)


def scorecard_html(metrics, ref):
    """A compact HTML scorecard: per checkpoint, macro F1 and per-class precision / recall / F1, each measured value
    shown against the milestone's expected (reference) number when one is supplied (mc has none)."""
    from avn_client import model_id                  # the one short-name -> id mapping
    models = _models(metrics)
    def cell(v, r, lower_better):
        if v is None:
            return "<td class='num'>—</td>"
        if r is None:
            return f"<td class='num'><b>{v:.1f}</b></td>"
        d = v - r
        good = (d <= 0) if lower_better else (d >= 0)
        # two lines per cell: the measured value, then "vs expected" with the delta underneath, so the row stays narrow
        # (JupyterLab lays rendered tables out with table-layout: fixed; one long nowrap line per cell overflows)
        return (f"<td class='num'><b>{v:.1f}</b><span class='vs'>vs {r:.1f} "
                f"<span class='delta {'good' if good else 'bad'}'>{d:+.1f}</span></span></td>")
    head = ("<tr><th>checkpoint</th><th class='num'>macro F1</th><th class='num'>comply P</th><th class='num'>comply R</th>"
            "<th class='num'>comply F1</th><th class='num'>refuse P</th><th class='num'>refuse R</th><th class='num'>refuse F1</th>"
            "<th class='num'>prompts</th></tr>")
    body = ""
    for m in models:
        v, r = metrics[m], ref.get(m, {})
        body += (f"<tr><td style='white-space:nowrap'><span class='pill acc'>{m}</span> <span class='muted mono'>{model_id(m)}</span></td>"
                 f"{cell(v.get('macro_F1'), r.get('macro_F1'), False)}"
                 f"{cell(_m(v, 'comply_P'), r.get('comply_P'), False)}{cell(_m(v, 'comply_R'), r.get('comply_R'), False)}{cell(_m(v, 'comply_F1'), r.get('comply_F1'), False)}"
                 f"{cell(v.get('refuse_P'), r.get('refuse_P'), False)}{cell(v.get('refuse_R'), r.get('refuse_R'), False)}{cell(v.get('refuse_F1'), r.get('refuse_F1'), False)}"
                 f"<td class='num'>{_m(v, 'n_comply') or v.get('n_unblock', 0)} + {v.get('n_refuse', 0)}</td></tr>")
    note = ("" if not any(ref.get(m) for m in models) else
            " Each number is this test <b>vs</b> the milestone's expected (reference) number, green = at least as good, red = worse.")
    return (f"<div class='avn'><table class='grid'>{head}{body}</table><p class='small' style='margin:6px 0 0'>"
            "Precision, recall and F1 per class, with <b>macro F1</b> the headline (the mean of the two class F1s). "
            "Comply is the should-answer class, refuse the should-refuse class. "
            f"These are this run's measured numbers.{note} The reference is the frozen held-out number in "
            "<span class='mono'>checkpoints.json</span>; mc (the live run) has none. A small sample is noisy — read the "
            "direction across checkpoints before any one figure.</p></div>")
