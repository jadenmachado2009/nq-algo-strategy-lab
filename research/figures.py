"""Generate the v5 figures. Theme-aware SVGs for the README, plus a preview page.

Every number here traces to a record in backtests/. Nothing is illustrative
except the single equity path in figure 2, which is resampled from the real
session distribution and labelled as one path.

    .venv/bin/python research/figures.py
"""

import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FIGDIR = ROOT / "docs" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

# ── colour roles: dataviz reference palette, slots 1-3 (validated all-pairs) ──
LIGHT = dict(s1="#2a78d6", s2="#eb6834", s3="#1baf7a", crit="#d03b3b",
             ink="#0b0b0b", ink2="#52514e", muted="#898781",
             grid="#e1e0d9", axis="#c3c2b7", surface="#fcfcfb")
DARK = dict(s1="#3987e5", s2="#d95926", s3="#199e70", crit="#d03b3b",
            ink="#f0efec", ink2="#c3c2b7", muted="#898781",
            grid="#2c2c2a", axis="#383835", surface="#1a1a19")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def sc(d0, d1, p0, p1):
    """Linear scale from data range to pixel range."""
    return lambda v: p0 + (v - d0) * (p1 - p0) / (d1 - d0) if d1 != d0 else p0


def txt(x, y, s, fill="var(--ink2)", size=12, anchor="start", weight=400,
        tab=False, style=""):
    extra = ' font-variant-numeric="tabular-nums"' if tab else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}"{extra} '
            f'style="{style}">{s}</text>')


def line(x1, y1, x2, y2, stroke="var(--grid)", w=1, dash=None, cap="butt"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{w}" stroke-linecap="{cap}"{d}/>')


def path(pts, stroke, w=2, fill="none", dash=None, join="round"):
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{w}" '
            f'stroke-linejoin="{join}" stroke-linecap="round"{da}/>')


def dot(x, y, r=5, fill="var(--s1)", ring="var(--surface)", rw=2):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
            f'stroke="{ring}" stroke-width="{rw}"/>')


def frame(inner, w, h, title, desc):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{desc}" font-family=\'{FONT}\'>'
            f'<title>{title}</title>{inner}</svg>')


def standalone(inner, w, h, title, desc):
    """A .svg file that carries its own light/dark tokens, for the README."""
    lv = ";".join(f"--{k}:{v}" for k, v in LIGHT.items())
    dv = ";".join(f"--{k}:{v}" for k, v in DARK.items())
    style = (f'<style>svg{{{lv}}}'
             f'@media (prefers-color-scheme:dark){{svg{{{dv}}}}}</style>')
    return frame(style + inner, w, h, title, desc)


# ═══════════════════════════════════════════════════════════════════════════
# FIG 1 — where ORB actually stands (live tracker, day-clustered CIs)
# ═══════════════════════════════════════════════════════════════════════════
def fig_standing():
    W, H = 720, 400
    L, R, T, B = 62, 210, 46, 58
    months = [("Aug", 50, 12, .360, .135, .596),
              ("Sep", 80, 17, .613, .403, .808),
              ("Oct", 39,  9, .590, .275, .878)]
    x = sc(-0.5, 2.5, L, W - R)
    y = sc(0.05, 0.95, H - B, T)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']

    for v in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        o.append(line(L, y(v), W - R, y(v)))
        o.append(txt(L - 10, y(v) + 4, f"{v:.0%}", "var(--muted)", 11, "end", tab=True))

    # reference bands
    for val, lab, col in ((0.657, "seven-year baseline  65.7%", "var(--s3)"),
                          (0.486, "2026Q3 break  48.6%", "var(--s2)")):
        o.append(line(L, y(val), W - R + 6, y(val), col, 2, dash="5 4"))
        o.append(txt(W - R + 12, y(val) + 4, lab, col, 11.5, weight=600))

    for i, (m, n, s, wr, lo, hi) in enumerate(months):
        px = x(i)
        o.append(line(px, y(lo), px, y(hi), "var(--s1)", 2, cap="round"))
        for e in (lo, hi):
            o.append(line(px - 5, y(e), px + 5, y(e), "var(--s1)", 2, cap="round"))
        o.append(dot(px, y(wr), 6))
        o.append(txt(px, y(wr) - 14, f"{wr:.1%}", "var(--ink)", 13, "middle", 650, tab=True))
        o.append(txt(px, H - B + 20, m, "var(--ink2)", 12.5, "middle", 600))
        o.append(txt(px, H - B + 36, f"{n} trades · {s} sessions", "var(--muted)", 10.5, "middle"))

    o.append(line(L, y(0.05), L, T - 8, "var(--axis)", 1))
    o.append(line(L, H - B, W - R, H - B, "var(--axis)", 1))
    o.append(txt(L, 20, "Win rate, live paper tracker on real NQ futures",
                 "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 36, "bars are day-clustered 95% intervals — sessions resampled, not trades",
                 "var(--muted)", 11.5))
    o.append(txt(W - R + 12, H - B - 4,
                 "Sep+Oct = 60.5%", "var(--ink)", 12, weight=650))
    o.append(txt(W - R + 12, H - B + 11, "CI [43.4%, 76.9%]", "var(--muted)", 11, tab=True))
    o.append(txt(W - R + 12, H - B + 26, "contains BOTH lines:", "var(--ink2)", 11))
    o.append(txt(W - R + 12, H - B + 40, "26 sessions cannot tell", "var(--ink2)", 11))
    o.append(txt(W - R + 12, H - B + 53, "recovery from the break.", "var(--ink2)", 11))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 2 — the trailing floor, and the two phases it creates
# ═══════════════════════════════════════════════════════════════════════════
def fig_floor():
    W, H = 720, 400
    L, R, T, B = 66, 196, 46, 52
    # one path resampled from the REAL session distribution (fixed seed)
    rows = list(csv.DictReader(open(ROOT / "execution" / "orb_paper_log.csv")))
    Rv = np.array([float(r["R"]) for r in rows])
    dts = np.array([r["date"] for r in rows])
    Rv = Rv - Rv.mean()                      # zero edge: this is the no-edge case
    uq, inv = np.unique(dts, return_inverse=True)
    sess = np.array([Rv[inv == k].sum() for k in range(len(uq))])
    rng = np.random.default_rng(20)
    # The path must pass under the REAL rules, consistency included: a best day
    # above 50% of the final total raises `required` above $3,000, so a path that
    # merely crosses the target line has not passed.
    eq = flo = peak = None
    for DOLLAR in (650.0, 550.0, 750.0, 450.0):
        for _ in range(30000):
            dd = rng.choice(sess, size=16) * DOLLAR
            e = np.concatenate([[0.0], np.cumsum(dd)])
            pk = np.maximum.accumulate(e)
            fl = np.minimum(pk - 2000.0, 0.0)
            if not (e[1:] > fl[:-1]).all() or e.max() < 3000:
                continue
            kill = int(np.argmax(e >= 3000))
            best = np.max(np.diff(e[:kill + 1]))
            if (6 <= kill <= 11 and (pk[:kill] >= 2000).any()
                    and best <= 0.50 * e[kill]):
                eq, flo, peak = e[:kill + 1], fl[:kill + 1], pk[:kill + 1]
                break
        if eq is not None:
            break
    if eq is None:
        raise SystemExit("figure 2: no passing path found; do not draw a fake one")
    n = len(eq) - 1
    lock = int(np.argmax(peak >= 2000))
    x = sc(0, n, L, W - R)
    y = sc(-2600, 3600, H - B, T)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']

    for v in (-2000, -1000, 0, 1000, 2000, 3000):
        o.append(line(L, y(v), W - R, y(v), "var(--grid)" if v else "var(--axis)",
                      1.5 if v == 0 else 1))
        o.append(txt(L - 10, y(v) + 4, f"{v:+,}".replace("+0", "0"),
                     "var(--muted)", 11, "end", tab=True))

    # the failure region, below the floor
    fl = [(x(i), y(flo[i])) for i in range(n + 1)]
    poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in fl)
    o.append(f'<polygon points="{poly} {x(n):.1f},{y(-2600):.1f} {L:.1f},{y(-2600):.1f}" '
             f'fill="var(--crit)" opacity="0.10"/>')

    o.append(line(L, y(3000), W - R, y(3000), "var(--s3)", 2, dash="5 4"))
    o.append(txt(W - R + 10, y(3000) + 4, "target  +$3,000", "var(--s3)", 11.5, weight=600))

    # floor as a step function
    step = []
    for i in range(n + 1):
        step.append((x(i), y(flo[i])))
        if i < n:
            step.append((x(i + 1), y(flo[i])))
    o.append(path(step, "var(--s2)", 2.5))
    o.append(path([(x(i), y(eq[i])) for i in range(n + 1)], "var(--s1)", 2.5))
    for i in range(n + 1):
        o.append(dot(x(i), y(eq[i]), 3.5, "var(--s1)", "var(--surface)", 1.5))

    o.append(line(x(lock), T - 4, x(lock), H - B, "var(--ink2)", 1, dash="3 3"))
    o.append(txt(x(lock) + 6, T + 8, "peak hits +$2,000", "var(--ink)", 11.5, weight=650))
    o.append(txt(x(lock) + 6, T + 22, "floor pins at $0 forever", "var(--ink2)", 11))

    o.append(txt(L + 6, y(eq[1]) - 12, "equity", "var(--s1)", 12, weight=650))
    o.append(txt(L + 6, y(flo[1]) + 18, "drawdown floor", "var(--s2)", 12, weight=650))
    o.append(txt(L + 6, y(-2350), "fail below this line", "var(--crit)", 11, weight=600))

    o.append(line(L, H - B, W - R, H - B, "var(--axis)", 1))
    for i in range(0, n + 1, max(1, n // 7)):
        o.append(txt(x(i), H - B + 18, str(i), "var(--muted)", 11, "middle", tab=True))
    o.append(txt((L + W - R) / 2, H - B + 36, "trading days", "var(--ink2)", 11.5, "middle"))

    o.append(txt(L, 20, "floor = min(end-of-day peak − $2,000, 0)", "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 36, "it ratchets up each profitable day, then pins at breakeven — one resampled path",
                 "var(--muted)", 11.5))

    bx, by = W - R + 10, y(1150)
    o.append(txt(bx, by, "PHASE 1", "var(--ink)", 11, weight=700, style="letter-spacing:.06em"))
    o.append(txt(bx, by + 15, "reach a +$2,000", "var(--ink2)", 11))
    o.append(txt(bx, by + 28, "end-of-day peak", "var(--ink2)", 11))
    o.append(txt(bx, by + 46, "38.2%", "var(--s1)", 17, weight=700, tab=True))
    o.append(txt(bx, by + 74, "PHASE 2", "var(--ink)", 11, weight=700, style="letter-spacing:.06em"))
    o.append(txt(bx, by + 89, "static barrier,", "var(--ink2)", 11))
    o.append(txt(bx, by + 102, "2000/3000 — fixed", "var(--ink2)", 11))
    o.append(txt(bx, by + 120, "66.7%", "var(--s2)", 17, weight=700, tab=True))
    o.append(line(bx, by + 132, bx + 110, by + 132, "var(--axis)", 1))
    o.append(txt(bx, by + 150, "25.4%", "var(--ink)", 17, weight=700, tab=True))
    o.append(txt(bx + 58, by + 150, "measured 25.8%", "var(--muted)", 10.5))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 3 — the 40% wall
# ═══════════════════════════════════════════════════════════════════════════
def fig_ceiling():
    W, H = 720, 350
    L, R, T, B = 240, 70, 52, 46
    items = [("0.50% risk, independent draws", .258, "this study"),
             ("0.50% risk, session replay", .319, "edge_sensitivity"),
             ("coin flip, 1 NQ @ 50pt, 1/day", .344, "half_R_coinflip"),
             ("best found: $1,500/trade, 1/day", .369, "this study")]
    x = sc(0, 0.46, L, W - R)
    y = sc(-0.5, len(items) - 0.5, T + 14, H - B - 14)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']
    for v in (0, .1, .2, .3, .4):
        o.append(line(x(v), T + 2, x(v), H - B, "var(--grid)"))
        o.append(txt(x(v), H - B + 18, f"{v:.0%}", "var(--muted)", 11, "middle", tab=True))

    o.append(line(x(.40), T - 6, x(.40), H - B + 2, "var(--crit)", 2.5))
    o.append(txt(x(.40), T - 14, "40.0% ceiling", "var(--crit)", 12, "middle", 700))

    for i, (lab, v, src) in enumerate(items):
        py = y(i)
        o.append(line(L, py, x(v), py, "var(--s1)", 2.5, cap="round"))
        o.append(dot(x(v), py, 6))
        o.append(txt(x(v) + 14, py + 4, f"{v:.1%}", "var(--ink)", 13, weight=650, tab=True))
        o.append(txt(L - 12, py + 1, lab, "var(--ink2)", 12, "end"))
        o.append(txt(L - 12, py + 15, src, "var(--muted)", 10, "end"))

    o.append(line(L, T + 2, L, H - B, "var(--axis)", 1))
    o.append(txt(14, 22, "Zero-edge pass rate: every configuration ever measured",
                 "var(--ink)", 14.5, weight=650))
    o.append(txt(14, 38, "under a static floor the answer is exactly 2000/5000 and bet size cannot "
                 "change it — the gap is end-of-day ratchet cost", "var(--muted)", 11.5))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 4 — bet size buys variance and sells skill
# ═══════════════════════════════════════════════════════════════════════════
def fig_edge_size():
    W, H = 720, 400
    L, R, T, B = 62, 176, 50, 58
    risk = [0.5, 1.0, 2.0, 3.0, 4.0, 6.0]
    zero = [25.8, 28.5, 27.0, 22.5, 17.8, 15.9]
    real = [72.8, 55.2, 40.8, 34.0, 26.5, 24.3]
    x = sc(0, len(risk) - 1, L, W - R)
    y = sc(0, 80, H - B, T)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']
    for v in (0, 20, 40, 60, 80):
        o.append(line(L, y(v), W - R, y(v), "var(--grid)"))
        o.append(txt(L - 10, y(v) + 4, f"{v}%", "var(--muted)", 11, "end", tab=True))

    band = ([(x(i), y(real[i])) for i in range(len(risk))] +
            [(x(i), y(zero[i])) for i in range(len(risk) - 1, -1, -1)])
    o.append('<polygon points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in band) +
             '" fill="var(--s1)" opacity="0.10"/>')
    o.append(path([(x(i), y(real[i])) for i in range(len(risk))], "var(--s1)", 2.5))
    o.append(path([(x(i), y(zero[i])) for i in range(len(risk))], "var(--s2)", 2.5))
    for i in range(len(risk)):
        o.append(dot(x(i), y(real[i]), 5, "var(--s1)"))
        o.append(dot(x(i), y(zero[i]), 5, "var(--s2)"))
        o.append(txt(x(i), H - B + 20, f"{risk[i]:.1f}%", "var(--ink2)", 11.5, "middle", 600))
        o.append(txt(x(i), H - B + 35, f"${risk[i]/100*50000:,.0f}", "var(--muted)", 10, "middle"))

    o.append(txt(x(0) + 10, y(real[0]) - 10, "with ORB's edge", "var(--s1)", 12.5, weight=650))
    o.append(txt(x(0) + 10, y(zero[0]) + 20, "zero edge", "var(--s2)", 12.5, weight=650))
    for i, lab in ((0, "+46.9 pts"), (5, "+8.4 pts")):
        my = (y(real[i]) + y(zero[i])) / 2
        o.append(line(x(i), y(real[i]) + 7, x(i), y(zero[i]) - 7, "var(--ink2)", 1, dash="2 2"))
        o.append(txt(x(i) + (12 if i == 0 else -12), my + 4, lab, "var(--ink)", 12,
                     "start" if i == 0 else "end", 700, tab=True))

    o.append(line(L, y(0), L, T - 8, "var(--axis)", 1))
    o.append(line(L, y(0), W - R, y(0), "var(--axis)", 1))
    o.append(txt((L + W - R) / 2, H - B + 52, "risk per trade", "var(--ink2)", 11.5, "middle"))
    o.append(txt(L, 20, "What an edge is worth, against what you bet", "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 36, "same trades, same rules — the only difference is whether the edge is left in",
                 "var(--muted)", 11.5))
    bx = W - R + 12
    o.append(txt(bx, T + 20, "Betting 12x larger", "var(--ink)", 11.5, weight=650))
    o.append(txt(bx, T + 35, "buys ~10 points of", "var(--ink2)", 11))
    o.append(txt(bx, T + 48, "zero-edge pass rate", "var(--ink2)", 11))
    o.append(txt(bx, T + 61, "and gives up five", "var(--ink2)", 11))
    o.append(txt(bx, T + 74, "sixths of what skill", "var(--ink2)", 11))
    o.append(txt(bx, T + 87, "is worth.", "var(--ink2)", 11))
    o.append(txt(bx, T + 112, "Absolutes inflated by", "var(--muted)", 10.5))
    o.append(txt(bx, T + 124, "independent draws. The", "var(--muted)", 10.5))
    o.append(txt(bx, T + 136, "session-replay model", "var(--muted)", 10.5))
    o.append(txt(bx, T + 148, "gives +7.2 pts at 0.50%", "var(--muted)", 10.5))
    o.append(txt(bx, T + 160, "and +4.1 at 1.00% —", "var(--muted)", 10.5))
    o.append(txt(bx, T + 172, "same direction.", "var(--muted)", 10.5))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 5 — why a pooled sweep lies
# ═══════════════════════════════════════════════════════════════════════════
def fig_target():
    W, H = 720, 400
    L, R, T, B = 66, 164, 50, 58
    tg = [0.25, 0.30, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00]
    pooled = [.0204, .0254, .0285, .0304, .0381, .0446, .0498, .0601, .0600, .0640]
    ins = [.0130, .0175, .0201, .0225, .0326, .0366, .0462, .0604, .0636, .0658]
    oos = [.0402, .0465, .0513, .0514, .0530, .0662, .0594, .0593, .0501, .0589]
    x = sc(0, len(tg) - 1, L, W - R)
    y = sc(0, 0.075, H - B, T)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']
    for v in (0, .02, .04, .06):
        o.append(line(L, y(v), W - R, y(v), "var(--grid)"))
        o.append(txt(L - 10, y(v) + 4, f"{v:+.3f}" if v else "0", "var(--muted)", 11, "end", tab=True))
    o.append(txt(L - 10, T - 16, "expectancy", "var(--muted)", 11, "end"))

    for i, lab in ((3, "0.50R"), (5, "0.75R")):
        o.append(line(x(i), T - 6, x(i), H - B, "var(--ink2)", 1, dash="3 3"))
    o.append(txt(x(3), T - 12, "incumbent", "var(--muted)", 11, "middle", 600))
    o.append(txt(x(5), T - 12, "only survivor", "var(--ink)", 11, "middle", 700))

    for series, col, name in ((ins, "var(--s2)", "2019–2024"),
                              (oos, "var(--s3)", "2024–2026"),
                              (pooled, "var(--s1)", "pooled")):
        o.append(path([(x(i), y(series[i])) for i in range(len(tg))], col,
                      2.5, dash="6 4" if name == "pooled" else None))
        for i in range(len(tg)):
            o.append(dot(x(i), y(series[i]), 4, col))

    o.append(txt(x(9) + 10, y(ins[9]) + 4, "2019–2024", "var(--s2)", 12, weight=650))
    o.append(txt(x(9) + 10, y(oos[9]) + 4, "2024–2026", "var(--s3)", 12, weight=650))
    o.append(txt(x(9) + 10, y(pooled[9]) + 4, "pooled", "var(--s1)", 12, weight=650))

    o.append(line(L, y(0), L, T - 8, "var(--axis)", 1))
    o.append(line(L, y(0), W - R, y(0), "var(--axis)", 1))
    for i in range(len(tg)):
        o.append(txt(x(i), H - B + 20, f"{tg[i]:.2f}", "var(--ink2)", 10.5, "middle", tab=True))
    o.append(txt((L + W - R) / 2, H - B + 40, "target, in multiples of the stop",
                 "var(--ink2)", 11.5, "middle"))
    o.append(txt(L, 20, "The pooled sweep says 2.00R. Split in half, it says nothing.",
                 "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 36, "Spearman rank correlation of expectancy against target: "
                 "+1.000 in-sample, +0.588 out", "var(--muted)", 11.5))
    bx = W - R + 12
    o.append(txt(bx, H - B - 46, "0.75R is the only", "var(--ink)", 11.5, weight=650))
    o.append(txt(bx, H - B - 32, "target that beats the", "var(--ink2)", 11))
    o.append(txt(bx, H - B - 19, "incumbent on both", "var(--ink2)", 11))
    o.append(txt(bx, H - B - 6, "mean and risk-adjusted", "var(--ink2)", 11))
    o.append(txt(bx, H - B + 7, "return in both halves.", "var(--ink2)", 11))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 6 — Monte Carlo: the answer is set by an input nobody has measured
# ═══════════════════════════════════════════════════════════════════════════
def fig_montecarlo():
    import json
    m = json.loads((FIGDIR / "_mc.json").read_text())
    W, H = 720, 430
    L, R, T, B = 64, 182, 50, 104
    g, cv = m["grid"], m["curve"]
    x = sc(-0.145, 0.125, L, W - R)
    y = sc(0, 0.72, H - B, T)
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']

    for v in (0, .2, .4, .6):
        o.append(line(L, y(v), W - R, y(v), "var(--grid)"))
        o.append(txt(L - 10, y(v) + 4, f"{v:.0%}", "var(--muted)", 11, "end", tab=True))
    o.append(txt(L - 10, T - 14, "pass rate", "var(--muted)", 11, "end"))

    def at(e):
        return float(np.interp(e, g, cv))

    # the live interval's projection onto the y-axis — the headline
    lo, hi = m["live_ci"]
    o.append(f'<rect x="{L:.1f}" y="{y(at(hi)):.1f}" width="{W-R-L:.1f}" '
             f'height="{y(at(lo))-y(at(hi)):.1f}" fill="var(--s2)" opacity="0.10"/>')

    o.append(line(x(0), T - 6, x(0), H - B, "var(--ink2)", 1, dash="3 3"))
    o.append(txt(x(0), T - 12, "zero edge", "var(--muted)", 11, "middle", 600))

    o.append(path([(x(g[i]), y(cv[i])) for i in range(len(g))], "var(--s1)", 2.5))
    for i in range(len(g)):
        o.append(dot(x(g[i]), y(cv[i]), 3.5, "var(--s1)", "var(--surface)", 1.5))

    # the two credible intervals, drawn under the axis
    rows = [("seven-year history", m["hist_ci"], m["hist_edge"], "var(--s3)", H - B + 32),
            ("38 live sessions", m["live_ci"], m["live_edge"], "var(--s2)", H - B + 64)]
    for lab, ci, pt, col, yy in rows:
        # The live interval reaches -0.286R, past the plotted range: clamp the bar
        # to the axis and mark it as continuing, rather than drawing it off-canvas.
        a, b = max(x(ci[0]), L), x(ci[1])
        clipped = x(ci[0]) < L
        o.append(line(a, yy, b, yy, col, 3, cap="round"))
        if clipped:
            o.append(path([(a + 9, yy - 6), (a, yy), (a + 9, yy + 6)], col, 2.5))
        else:
            o.append(line(a, yy - 5, a, yy + 5, col, 2.5, cap="round"))
        o.append(line(b, yy - 5, b, yy + 5, col, 2.5, cap="round"))
        o.append(dot(x(pt), yy, 5, col))
        o.append(txt(a + (16 if clipped else 0), yy - 11, lab, col, 11.5, weight=650))
        plo = at(ci[0])
        lab_lo = f"{plo:.1%}" if plo < 0.10 else f"{plo:.0%}"
        o.append(txt(b + 10, yy + 4, f"{lab_lo} – {at(ci[1]):.0%}", "var(--ink)",
                     12, weight=700, tab=True))
        for e in ci:
            if x(e) < L:
                continue
            o.append(line(x(e), y(at(e)), x(e), yy - 16, col, 1, dash="2 3"))
            o.append(line(L, y(at(e)), x(e), y(at(e)), col, 1, dash="2 3"))

    o.append(line(L, y(0), L, T - 8, "var(--axis)", 1))
    o.append(line(L, y(0), W - R, y(0), "var(--axis)", 1))
    for e in (-0.12, -0.08, -0.04, 0.0, 0.04, 0.08, 0.12):
        o.append(line(x(e), y(0), x(e), y(0) + 5, "var(--axis)", 1))
        o.append(txt(x(e), y(0) + 18, f"{e:+.2f}".replace("+0.00", "0"),
                     "var(--muted)", 10.5, "middle", tab=True))
    o.append(txt((L + W - R) / 2, y(0) + 34, "true edge, R per trade",
                 "var(--ink2)", 11.5, "middle"))

    o.append(txt(L, 20, "Monte Carlo: the pass rate is decided by the one unknown input",
                 "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 36, "40,000 session-replay paths per point, 21-day blocks, 0.50% risk — "
                "bars are day-clustered 95% intervals", "var(--muted)", 11.5))
    bx = W - R + 12
    o.append(txt(bx, T + 18, "History says you", "var(--ink2)", 11))
    o.append(txt(bx, T + 31, "pass 38–53% of", "var(--ink2)", 11))
    o.append(txt(bx, T + 44, "the time.", "var(--ink2)", 11))
    o.append(txt(bx, T + 66, "The live data says", "var(--ink2)", 11))
    o.append(txt(bx, T + 79, "somewhere between", "var(--ink2)", 11))
    o.append(txt(bx, T + 92, "0% and 56%.", "var(--ink)", 11, weight=650))
    o.append(txt(bx, T + 114, "That span is the", "var(--ink2)", 11))
    o.append(txt(bx, T + 127, "reason to wait —", "var(--ink2)", 11))
    o.append(txt(bx, T + 140, "not the point", "var(--ink2)", 11))
    o.append(txt(bx, T + 153, "estimate inside it.", "var(--ink2)", 11))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 7 — the simulation itself: every path, both scenarios
# ═══════════════════════════════════════════════════════════════════════════
def fig_paths():
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    import montecarlo as MC
    import orb_rescue as _RS
    import search_5m as _S5
    d = _S5.load_dir("data/nq_5m")
    dates = np.array([str(v) for v in d["day"]])
    FULL = _RS.collect(_S5.slice_data(d, 0, int(np.searchsorted(dates, _RS.BREAK_START))))
    M, r, _ = MC.session_matrix(FULL)

    NP, NSTAT, ND = 180, 6000, 45   # draw NP lines, measure on NSTAT paths
    W, H = 720, 604
    L, R = 66, 150
    # each panel needs ybot + 32 (day labels + axis title) + margin inside H
    panels = [("Seven-year history", r.mean(), 76, 300),
              ("Live estimate, same sessions", -0.1037, 362, 556)]
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']
    o.append(txt(L, 22, "The simulation, drawn", "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 38, f"{NP:,} lines drawn from {NSTAT:,} session-replay paths per panel; the percentages are measured on all {NSTAT:,} — 21-day blocks, 0.50% risk",
                "var(--muted)", 11.5))

    for pi, (lab, edge, ytop, ybot) in enumerate(panels):
        hist, res, passed = MC.run_paths(M, .005, edge, 21, NSTAT, ND, seed=4)
        x = sc(0, ND, L, W - R)
        y = sc(-2700, 4000, ybot, ytop)
        o.append(f'<rect x="{L}" y="{ytop}" width="{W-R-L}" height="{ybot-ytop}" '
                 f'fill="var(--grid)" opacity="0.28"/>')
        for v in (-2000, 0, 3000):
            o.append(line(L, y(v), W - R, y(v),
                          "var(--crit)" if v == -2000 else
                          ("var(--s3)" if v == 3000 else "var(--axis)"),
                          1.5, dash="5 4" if v else None))
            o.append(txt(L - 9, y(v) + 4, f"{v:+,}".replace("+0", "0"),
                         "var(--muted)", 10.5, "end", tab=True))

        # every path, coloured by how it ended
        shown = np.zeros(NSTAT, bool); shown[:NP] = True   # the first NP are i.i.d.
        for grp, col, op in ((passed & shown, "var(--s3)", 0.55),
                             (~passed & shown, "var(--s2)", 0.22)):
            for i in np.where(grp)[0]:
                k = min(int(res[i]) + 1, ND)
                pts = " ".join(f"{x(j):.0f},{y(hist[i, j]):.0f}" for j in range(k + 1))
                o.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                         f'stroke-width="1" stroke-opacity="{op}"/>')
        med = np.median(hist, axis=0)
        o.append(path([(x(j), y(med[j])) for j in range(ND + 1)], "var(--ink)", 2.5))

        o.append(txt(L, ytop - 10, lab, "var(--ink)", 12.5, weight=650))
        o.append(txt(L + 190, ytop - 10, f"edge {edge:+.4f}R", "var(--muted)", 11.5, tab=True))
        bx = W - R + 10
        o.append(txt(bx, ytop + 16, f"{passed.mean():.1%}", "var(--s3)", 20, weight=700, tab=True))
        o.append(txt(bx, ytop + 32, "passed", "var(--s3)", 11, weight=600))
        o.append(txt(bx, ytop + 58, f"{(~passed).mean():.1%}", "var(--s2)", 20, weight=700, tab=True))
        o.append(txt(bx, ytop + 74, "lost the account", "var(--s2)", 11, weight=600))
        o.append(txt(bx, ytop + 100, "median path", "var(--ink2)", 10.5))
        o.append(txt(bx, ytop + 114, f"ends ${med[-1]:+,.0f}", "var(--ink)", 12, weight=650, tab=True))
        if pi == 0:
            o.append(txt(L + 8, y(3000) - 7, "target +$3,000", "var(--s3)", 10.5, weight=600))
            o.append(txt(L + 8, y(-2000) + 14, "drawdown limit", "var(--crit)", 10.5, weight=600))

        o.append(line(L, ybot, W - R, ybot, "var(--axis)", 1))
        for j in range(0, ND + 1, 9):
            o.append(txt(x(j), ybot + 16, str(j), "var(--muted)", 10.5, "middle", tab=True))
        o.append(txt((L + W - R) / 2, ybot + 32, "trading days", "var(--ink2)", 11, "middle"))
    return "".join(o), W, H


# ═══════════════════════════════════════════════════════════════════════════
# FIG 8 — the trade-off: days against how much of the result is skill
# ═══════════════════════════════════════════════════════════════════════════
def fig_frontier():
    import json
    F = json.loads((FIGDIR / "_frontier.json").read_text())
    W, H = 720, 470
    L, R, T, B = 66, 164, 54, 64
    x = sc(np.log10(9), np.log10(360), L, W - R)     # expected days, log scale
    y = sc(0, 44, H - B, T)                          # edge worth, points
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--surface)"/>']
    for v in (0, 10, 20, 30, 40):
        o.append(line(L, y(v), W - R, y(v), "var(--grid)"))
        o.append(txt(L - 10, y(v) + 4, f"+{v}", "var(--muted)", 11, "end", tab=True))
    o.append(txt(L - 10, T - 16, "skill, pts", "var(--muted)", 10.5, "end"))
    for v in (10, 20, 50, 100, 200, 300):
        o.append(line(x(np.log10(v)), T - 4, x(np.log10(v)), H - B, "var(--grid)"))
        o.append(txt(x(np.log10(v)), H - B + 18, str(v), "var(--muted)", 11, "middle", tab=True))

    series = [("ORB 0.50R", F["orb"]["0.50"], "var(--s2)"),
              ("ORB 0.75R", F["orb"]["0.75"], "var(--s1)"),
              ("ORB 1.00R", F["orb"]["1.00"], "var(--s3)")]
    for lab, pts, col in series:
        pp = [(x(np.log10(q["edays"])), y(q["worth"])) for q in pts if q["edays"] <= 360]
        o.append(path(pp, col, 2.5))
        for q, (px, py) in zip([q for q in pts if q["edays"] <= 360], pp):
            o.append(dot(px, py, 4, col))
    o.append(txt(x(np.log10(190)), y(40) - 12, "ORB 0.75R", "var(--s1)", 12, weight=650))
    o.append(txt(x(np.log10(300)), y(32) + 16, "ORB 0.50R", "var(--s2)", 12, weight=650))
    o.append(txt(x(np.log10(150)), y(36) + 16, "ORB 1.00R", "var(--s3)", 12, weight=650))

    # the two specs that matter, called out
    marks = [("current\n0.50R @ $250", 36, 11, "var(--s2)"),
             ("recommended\n0.75R @ $250", 27, 15, "var(--s1)")]
    for lab, dd, wv, col in marks:
        px, py = x(np.log10(dd)), y(wv)
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="none" '
                 f'stroke="{col}" stroke-width="2"/>')
    o.append(txt(x(np.log10(36)) - 6, y(11) + 26, "current", "var(--s2)", 11, "middle", 700))
    o.append(txt(x(np.log10(27)) + 2, y(15) - 16, "pick this", "var(--s1)", 11, "middle", 700))

    # the $320 hole
    hx, hy = x(np.log10(18)), y(3)
    o.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="9" fill="none" stroke="var(--crit)" '
             f'stroke-width="2" stroke-dasharray="3 2"/>')
    o.append(txt(hx, hy + 24, "$320 hole", "var(--crit)", 10.5, "middle", 650))

    o.append(line(L, y(0), L, T - 8, "var(--axis)", 1))
    o.append(line(L, y(0), W - R, y(0), "var(--axis)", 1))
    o.append(txt((L + W - R) / 2, H - B + 38, "expected trading days to a funded account",
                 "var(--ink2)", 11.5, "middle"))
    o.append(txt(L, 22, "You buy speed with skill. There is no third option.",
                 "var(--ink)", 14.5, weight=650))
    o.append(txt(L, 38, "vertical axis is how many points the edge adds over an identical "
                "zero-edge trader", "var(--muted)", 11.5))
    bx = W - R + 12
    o.append(txt(bx, T + 18, "Left and up is", "var(--ink2)", 11))
    o.append(txt(bx, T + 31, "better: fewer days,", "var(--ink2)", 11))
    o.append(txt(bx, T + 44, "more of it earned.", "var(--ink2)", 11))
    o.append(txt(bx, T + 68, "0.75R sits above", "var(--s1)", 11, weight=650))
    o.append(txt(bx, T + 81, "0.50R at every", "var(--s1)", 11, weight=650))
    o.append(txt(bx, T + 94, "size tested.", "var(--s1)", 11, weight=650))
    o.append(txt(bx, T + 118, "The curve is not", "var(--crit)", 11))
    o.append(txt(bx, T + 131, "smooth. Fixed-dollar", "var(--crit)", 11))
    o.append(txt(bx, T + 144, "rules against a", "var(--crit)", 11))
    o.append(txt(bx, T + 157, "fixed-dollar bet put", "var(--crit)", 11))
    o.append(txt(bx, T + 170, "a hole at $320 in", "var(--crit)", 11))
    o.append(txt(bx, T + 183, "all three curves.", "var(--crit)", 11))
    o.append(txt(bx, T + 196, "Test your size;", "var(--ink)", 11, weight=650))
    o.append(txt(bx, T + 209, "never interpolate.", "var(--ink)", 11, weight=650))
    return "".join(o), W, H


FIGS = [
    ("01-where-it-stands", fig_standing,
     "Where ORB stands", "Monthly win rate with day-clustered confidence intervals"),
    ("02-trailing-floor", fig_floor,
     "The trailing floor", "Equity path against a drawdown floor that ratchets then pins"),
    ("03-zero-edge-ceiling", fig_ceiling,
     "The 40% wall", "Zero-edge pass rates against the static-floor ceiling"),
    ("04-edge-vs-size", fig_edge_size,
     "Edge against bet size", "Pass rate with and without an edge across risk per trade"),
    ("05-target-trap", fig_target,
     "The pooled-sweep trap", "Expectancy against target, pooled and split in half"),
    ("06-monte-carlo", fig_montecarlo,
     "Pass rate against true edge", "Monte Carlo pass rate as a function of the unknown true edge"),
    ("07-simulation-paths", fig_paths,
     "The simulation drawn", "Simulated equity paths under two edge assumptions"),
    ("08-tradeoff-frontier", fig_frontier,
     "Days against skill", "Expected days to funded against how much of the result is edge"),
]


def main():
    frags = []
    for slug, fn, title, desc in FIGS:
        inner, w, h = fn()
        (FIGDIR / f"{slug}.svg").write_text(standalone(inner, w, h, title, desc))
        frags.append((slug, title, desc, frame(inner, w, h, title, desc)))
        print(f"  docs/figures/{slug}.svg   {w}x{h}")
    import json
    (FIGDIR / "_fragments.json").write_text(json.dumps(
        [{"slug": s, "title": t, "desc": d, "svg": v} for s, t, d, v in frags]))
    print(f"\n  {len(frags)} figures + _fragments.json")


if __name__ == "__main__":
    main()
