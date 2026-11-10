#!/usr/bin/env python3
"""Generate the Rush Labs organization profile: profile/README.md and its SVGs.

Run:  python3 scripts/build.py [path/to/fonts]
Fonts: archivo-expanded-800.ttf and archivo-400.ttf (SIL OFL), the same files
rushlabs.ai uses. Text is drawn as glyph paths because GitHub's image proxy
blocks web fonts. Colours and type follow rushlabs.ai (see its DESIGN.md):
deep green and beige themes, wide Archivo for display, the hero current.
Asset names carry a content hash so GitHub's image cache never shows stale art.
"""
from pathlib import Path
from html import escape
import hashlib
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ttf import Font  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profile"
OUT = PROFILE / "assets"
FONTS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "repos/rushlabs-ai/assets/fonts"
WIDE = Font(FONTS / "archivo-expanded-800.ttf")
BODY = Font(FONTS / "archivo-400.ttf")
FONT_IDS = {id(WIDE): "w", id(BODY): "b"}

# rushlabs.ai tokens (app/globals.css)
THEMES = {
    "light": dict(bg="#EBDCB3", surface="#FFFCF4", line="#D8C99D", fg="#0A1C16", muted="#4A6358",
                  live="#2F7A62", screen="#0A1C16",
                  glow=("#FFFAEE", .55), depth=("#A88860", .16), current=.30),
    "dark": dict(bg="#0A1C16", surface="#122722", line="#2A4A40", fg="#F6EFE3", muted="#B9A98A",
                 live="#8CC9B0", screen="#0E231D",
                 glow=("#417C69", .22), depth=("#E8D5A5", .06), current=.34),
}
# cover art palette (components/site/case-cover.tsx), always on the dark screen
SAND, DUNE, FOREST, MINT = "#E8D5A5", "#A39682", "#417C69", "#7FB9A4"
ICON_GREY = "#8B949E"


class Doc:
    """One SVG: collects glyphs into <defs> and emits text as <use> runs."""

    def __init__(self):
        self.glyphs = {}

    def text(self, x, y, s, font, size, fill, tracking=0.0, anchor="start", opacity=1):
        k = size / font.upm
        w = font.width(s, size, tracking)
        if anchor == "end":
            x -= w
        elif anchor == "middle":
            x -= w / 2
        fid = FONT_IDS[id(font)]
        uses, pen = [], 0.0
        trk = tracking * font.upm
        for ch in s:
            g = font.gid(ch)
            if ch != " " and font.path(g):
                key = f"{fid}{g}"
                self.glyphs[key] = font.path(g)
                uses.append(f'<use href="#{key}" x="{pen:.0f}"/>')
            pen += font.advance(g) + trk
        op = f' fill-opacity="{opacity}"' if opacity != 1 else ""
        return (f'<g fill="{fill}"{op} transform="translate({x:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})">'
                f'{"".join(uses)}</g>')

    def defs(self):
        return "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.glyphs.items())


def wrap(s, font, size, max_w):
    lines, cur = [], ""
    for word in s.split(" "):
        trial = f"{cur} {word}".strip()
        if not cur or font.width(trial, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def svg(w, h, title, doc, body, css="", extra_defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'
            f'<style>@media (prefers-reduced-motion: reduce){{*{{animation:none !important}}}}{css}</style>'
            f'<defs>{doc.defs()}{extra_defs}</defs>{body}</svg>')


# ── The current (components/site/current-field.tsx + lib/noise.ts) ──────────
def make_perm(seed):
    base = list(range(256))
    s = seed & 0xFFFFFFFF or 1
    for i in range(255, 0, -1):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        j = s % (i + 1)
        base[i], base[j] = base[j], base[i]
    return [base[i & 255] for i in range(512)]


PERM = make_perm(7)


def noise3(x, y, z):
    fade = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
    lerp = lambda a, b, t: a + (b - a) * t
    lat = lambda X, Y, Z: PERM[(PERM[(PERM[X & 255] + Y) & 255] + Z) & 255] / 127.5 - 1
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    u, v, w = fade(x - xi), fade(y - yi), fade(z - zi)
    c = lambda X, Y: lerp(lat(X, Y, zi), lat(X, Y, zi + 1), w)
    return lerp(lerp(c(xi, yi), c(xi + 1, yi), u), lerp(c(xi, yi + 1), c(xi + 1, yi + 1), u), v)


def fbm(x, y, z):
    return noise3(x, y, z) * 0.7 + noise3(x * 2.1 + 31, y * 2.1 + 17, z * 1.5) * 0.3


def prng(seed):
    s = [seed]

    def r():
        s[0] = (s[0] * 1664525 + 1013904223) % 4294967296
        return s[0] / 4294967296
    return r


def streamlines(w, h, count, steps, step_px, seed, t=11.3):
    r = prng(seed)
    scale = 1 / max(380, min(w, h) * 0.8)
    out = []
    for _ in range(count):
        x, y = r() * w, r() * h
        pts = [(x, y)]
        for _ in range(steps):
            a = fbm(x * scale, y * scale, t) * math.pi * 1.8 + 0.3
            x += math.cos(a) * step_px
            y += math.sin(a) * step_px
            if not (-10 < x < w + 10 and -10 < y < h + 10):
                break
            pts.append((x, y))
        if len(pts) > steps // 2:
            out.append(pts)
    return out


CURRENT_CSS = (".cur{stroke-dasharray:14 100;stroke-dashoffset:-40;animation:flow 9s linear infinite both}"
               "@keyframes flow{0%{stroke-dashoffset:14}100%{stroke-dashoffset:-100}}")


def current(w, h, color, alpha, count, seed, steps=34, step_px=3.2, width=1.35):
    """Faint streamlines plus a short bright dash travelling along each one."""
    lines = streamlines(w, h, count, steps, step_px, seed)
    base, heads = [], []
    for i, pts in enumerate(lines):
        p = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
        base.append(f'<polyline points="{p}"/>')
        heads.append(f'<polyline class="cur" pathLength="100" style="animation-delay:-{(i * 1.37) % 9:.2f}s" points="{p}"/>')
    common = f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'
    return (f'<g {common} stroke-opacity="{alpha * 0.32:.3f}">{"".join(base)}</g>'
            f'<g {common} stroke-opacity="{alpha:.3f}">{"".join(heads)}</g>')


def atmosphere(w, h, t, uid):
    (g1, a1), (g2, a2) = t["glow"], t["depth"]
    defs = (f'<radialGradient id="{uid}g" cx=".08" cy="0" r=".6"><stop offset="0" stop-color="{g1}" stop-opacity="{a1}"/>'
            f'<stop offset=".7" stop-color="{g1}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="{uid}d" cx=".95" cy="1" r=".45"><stop offset="0" stop-color="{g2}" stop-opacity="{a2}"/>'
            f'<stop offset=".7" stop-color="{g2}" stop-opacity="0"/></radialGradient>')
    body = (f'<rect width="{w}" height="{h}" fill="url(#{uid}g)"/>'
            f'<rect width="{w}" height="{h}" fill="url(#{uid}d)"/>')
    return defs, body


def calm(uid, w, h, x, y, rw, rh):
    """Mask that fades the current behind body text so it stays easy to read."""
    return (f'<filter id="{uid}b" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>'
            f'<mask id="{uid}k" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>'
            f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" rx="20" fill="#000" fill-opacity=".8" filter="url(#{uid}b)"/></mask>')


# ── Copy (mirrors rushlabs.ai: components/site/hero.tsx, lib/content/*) ───────
HEADLINE = ["Open-source tools", "for open models."]
HEADLINE_M = ["Open-source", "tools for", "open models."]
INTRO = "Four released tools and a research model for fine-tuning, retrieval and local AI."
HEADER_ALT = "Rush Labs, an applied AI lab. Open-source tools for open models. " + INTRO


def header(t, uid):
    W, P = 1000, 44
    size, lead = 68, 62
    assert WIDE.width(HEADLINE[0], size, -0.025) < W - 2 * P
    intro_y = 158 + lead + 56
    H = intro_y + 50
    doc = Doc()
    adefs, abody = atmosphere(W, H, t, uid)
    clip = f'<clipPath id="{uid}c"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="20"/></clipPath>'
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="20" fill="{t["bg"]}" stroke="{t["line"]}"/>',
         f'<g clip-path="url(#{uid}c)">{abody}<g mask="url(#{uid}k)">{current(W, H, t["fg"], t["current"], 120, 19)}</g></g>']
    b.append(doc.text(P, 66, "Rush Labs", WIDE, 19, t["fg"], -0.01))
    b.append(doc.text(W - P, 66, "Applied AI lab", BODY, 16, t["muted"], anchor="end"))
    for i, line in enumerate(HEADLINE):
        b.append(doc.text(P - 3, 158 + i * lead, line, WIDE, size, t["fg"], -0.025))
    b.append(doc.text(P, intro_y, INTRO, BODY, 19, t["fg"]))
    mask = calm(uid, W, H, P - 14, intro_y - 26, BODY.width(INTRO, 19) + 28, 38)
    return svg(W, H, HEADER_ALT, doc, "".join(b), CURRENT_CSS, adefs + clip + mask)


def header_m(t, uid):
    W, P = 400, 24
    size, lead = 37, 34
    doc = Doc()
    b = [doc.text(P, 46, "Rush Labs", WIDE, 16, t["fg"], -0.01)]
    for i, line in enumerate(HEADLINE_M):
        b.append(doc.text(P - 1, 108 + i * lead, line, WIDE, size, t["fg"], -0.025))
    y = 108 + 2 * lead + 44
    lines = balanced(INTRO, BODY, 17, W - 2 * P)
    for i, line in enumerate(lines):
        b.append(doc.text(P, y + i * 26, line, BODY, 17, t["fg"]))
    H = y + (len(lines) - 1) * 26 + 30
    adefs, abody = atmosphere(W, H, t, uid)
    clip = f'<clipPath id="{uid}c"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18"/></clipPath>'
    frame = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="{t["bg"]}" stroke="{t["line"]}"/>'
             f'<g clip-path="url(#{uid}c)">{abody}<g mask="url(#{uid}k)">{current(W, H, t["fg"], t["current"], 60, 23, steps=26)}</g></g>')
    mask = calm(uid, W, H, P - 10, y - 22, W - 2 * P + 20, len(lines) * 26 + 10)
    return svg(W, H, HEADER_ALT, doc, frame + "".join(b), CURRENT_CSS, adefs + clip + mask)


# ── Cover motifs (ported from components/site/case-cover.tsx, 800x500) ──────
def m_embed():
    r = prng(11)
    centers = [(210, 170), (560, 140), (450, 360), (170, 380)]
    pts = []
    for k, (cx, cy) in enumerate(centers):
        for _ in range(22):
            pts.append(dict(x=cx + (r() - .5) * 190, y=cy + (r() - .5) * 140, k=k, s=2 + r() * 3, o=.2 + r() * .45))
    q = (505, 300)
    near = sorted((p for p in pts if p["k"] == 2), key=lambda p: math.hypot(p["x"] - q[0], p["y"] - q[1]))[:5]
    o = [f'<circle cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="{p["s"]:.1f}" fill="{MINT if p["k"] == 2 else DUNE}" '
         f'opacity="{(p["o"] + .2) if p["k"] == 2 else p["o"]:.2f}"/>' for p in pts]
    o += [f'<line x1="{q[0]}" y1="{q[1]}" x2="{p["x"]:.1f}" y2="{p["y"]:.1f}" stroke="{SAND}" stroke-opacity=".55" stroke-width="1.5"/>' for p in near]
    o.append(f'<circle class="ping" cx="{q[0]}" cy="{q[1]}" r="30" fill="none" stroke="{SAND}" stroke-opacity=".35"/>')
    o.append(f'<circle cx="{q[0]}" cy="{q[1]}" r="10" fill="{SAND}"/>')
    o.append(f'<rect x="96" y="52" width="300" height="44" rx="22" fill="#16302A" stroke="{FOREST}" stroke-opacity=".7"/>')
    o.append(f'<circle cx="122" cy="74" r="7" fill="none" stroke="{SAND}" stroke-width="2"/>')
    o.append(f'<line x1="127" y1="79" x2="133" y2="85" stroke="{SAND}" stroke-width="2" stroke-linecap="round"/>')
    o.append(f'<rect x="146" y="70" width="170" height="8" rx="4" fill="{SAND}" opacity=".75"/>')
    return "".join(o)


def m_train():
    r = prng(7)
    pts = " ".join(f"{80 + i * 16},{400 - 250 * (1 - math.exp(-i / 9)) + (r() - .5) * 18:.1f}" for i in range(40))
    o = [f'<line x1="80" y1="{100 + i * 75}" x2="720" y2="{100 + i * 75}" stroke="{FOREST}" stroke-opacity=".25"/>' for i in range(5)]
    o.append(f'<line x1="80" y1="260" x2="720" y2="260" stroke="{DUNE}" stroke-opacity=".6" stroke-dasharray="6 7"/>')
    o.append(f'<polyline class="draw" pathLength="100" points="{pts}" fill="none" stroke="{MINT}" stroke-width="3" stroke-linejoin="round"/>')
    o.append(f'<circle class="ping" cx="704" cy="152" r="8" fill="{SAND}"/>')
    return "".join(o)


def m_quant():
    r = prng(3)
    levels = [.25, .55, .9]
    o = []
    for row in range(10):
        for col in range(18):
            v = r()
            q = col >= 9
            op = levels[min(2, int(v * 3))] if q else .15 + v * .75
            o.append(f'<rect x="{70 + col * 37 + (16 if q else 0)}" y="{60 + row * 38}" width="30" height="30" rx="4" '
                     f'fill="{MINT if q else DUNE}" opacity="{op:.2f}"/>')
    o.append(f'<line x1="419" y1="44" x2="419" y2="456" stroke="{SAND}" stroke-opacity=".5" stroke-dasharray="4 6"/>')
    return "".join(o)


def m_cli(seed=5):
    r = prng(seed)
    PANEL, LINE = "#16302A", "#24443A"
    o = [f'<rect x="60" y="50" width="680" height="400" rx="16" fill="{PANEL}" stroke="{LINE}"/>',
         f'<line x1="60" y1="90" x2="740" y2="90" stroke="{LINE}"/>']
    o += [f'<circle cx="{86 + i * 18}" cy="70" r="5" fill="{DUNE}" opacity=".35"/>' for i in range(3)]
    for i in range(7):
        y = 124 + i * 34
        o.append(f'<g class="row" style="animation-delay:{i * .18:.2f}s">'
                 f'<rect x="90" y="{y}" width="14" height="8" rx="4" fill="{MINT}" opacity=".8"/>'
                 f'<rect x="116" y="{y}" width="{120 + r() * 200:.0f}" height="8" rx="4" fill="{SAND}" opacity=".35"/>'
                 f'<rect x="560" y="{y}" width="{60 + r() * 60:.0f}" height="8" rx="4" fill="{DUNE}" opacity=".4"/></g>')
    o.append(f'<rect x="90" y="380" width="250" height="40" rx="20" fill="{MINT}"/>')
    o.append('<rect x="118" y="396" width="150" height="8" rx="4" fill="#0F221D" opacity=".8"/>')
    return "".join(o)


def m_search():
    """Rush Index: one query, documents and photos in one ranked list."""
    r = prng(13)
    o = [f'<rect x="96" y="52" width="608" height="48" rx="24" fill="#16302A" stroke="{FOREST}" stroke-opacity=".7"/>',
         f'<circle cx="124" cy="75" r="8" fill="none" stroke="{SAND}" stroke-width="2.4"/>',
         f'<line x1="130" y1="81" x2="137" y2="88" stroke="{SAND}" stroke-width="2.4" stroke-linecap="round"/>',
         f'<rect x="152" y="71" width="230" height="9" rx="4.5" fill="{SAND}" opacity=".75"/>']
    for i, kind in enumerate(("doc", "photo", "doc", "photo", "doc")):
        y = 124 + i * 66
        g = [f'<rect x="96" y="{y}" width="608" height="54" rx="12" fill="#16302A" opacity="{.9 if i == 0 else .55}"/>']
        if kind == "doc":
            g.append(f'<rect x="114" y="{y + 10}" width="27" height="34" rx="4" fill="none" stroke="{SAND}" stroke-opacity=".7" stroke-width="2"/>')
            g.append(f'<rect x="120" y="{y + 20}" width="15" height="3" rx="1.5" fill="{SAND}" opacity=".6"/>')
            g.append(f'<rect x="120" y="{y + 28}" width="11" height="3" rx="1.5" fill="{SAND}" opacity=".6"/>')
        else:
            g.append(f'<rect x="110" y="{y + 10}" width="44" height="34" rx="5" fill="{FOREST}"/>')
            g.append(f'<path d="M112 {y + 42} L126 {y + 26} L136 {y + 35} L142 {y + 29} L152 {y + 42} Z" fill="{MINT}" opacity=".9"/>')
            g.append(f'<circle cx="143" cy="{y + 19}" r="4" fill="{SAND}"/>')
        g.append(f'<rect x="172" y="{y + 15}" width="{150 + r() * 190:.0f}" height="8" rx="4" fill="{SAND}" opacity=".45"/>')
        g.append(f'<rect x="172" y="{y + 31}" width="{90 + r() * 120:.0f}" height="7" rx="3.5" fill="{DUNE}" opacity=".4"/>')
        g.append(f'<rect x="{620 - i * 22}" y="{y + 23}" width="{60 + i * 22}" height="8" rx="4" fill="{MINT}" opacity="{.9 - i * .15:.2f}"/>')
        o.append(f'<g class="row" style="animation-delay:{i * .2:.2f}s">{"".join(g)}</g>')
    return "".join(o)


def m_current():
    return current(800, 500, "#F6EFE3", .5, 120, 31, steps=40, step_px=4.5, width=2.2)


MOTIF_CSS = (".ping{transform-box:fill-box;transform-origin:center;animation:ping 3.2s ease-out 1s infinite both}"
             "@keyframes ping{0%,100%{transform:scale(1)}30%{transform:scale(1.18)}60%{transform:scale(1)}}"
             ".draw{stroke-dasharray:100 100;animation:draw 7s ease-out infinite both}"
             "@keyframes draw{0%{stroke-dashoffset:100}35%,100%{stroke-dashoffset:0}}"
             ".row{animation:row 6s ease-out infinite both}"
             "@keyframes row{0%{opacity:0}8%,100%{opacity:1}}") + CURRENT_CSS
MOTIFS = {"embed": m_embed, "train": m_train, "quant": m_quant, "cli": m_cli, "search": m_search,
          "current": m_current}


# ── Project cards (rushlabs.ai home: cover, status, name, summary) ───────────
PROJECTS = [
    dict(key="tunekeep", name="tunekeep", status="v0.2.2", motif="train",
         href="https://github.com/rushlabs-ai/tunekeep",
         summary="Keep a fine-tuned model working when its provider retires the base model."),
    dict(key="crosscheck", name="Crosscheck", status="v0.3.0", motif="embed",
         href="https://github.com/rushlabs-ai/crosscheck",
         summary="Several local vision models describe a photo, and you hear where they disagree."),
    dict(key="rerankd", name="rerankd", status="v0.1.1", motif="cli",
         href="https://github.com/rushlabs-ai/rerankd",
         summary="Rerank endpoints for Ollama, using the reranker models you already pulled."),
    dict(key="rush-index", name="Rush Index", status="v0.2.0", motif="search",
         href="https://github.com/rushlabs-ai/rush-index",
         summary="Search your documents and photos together, locally, on any laptop or an NVIDIA GPU."),
    dict(key="rush-small", name="Rush Small", status="v0 research", motif="quant",
         href="https://github.com/rushlabs-ai/rush-small",
         summary="A 0.6B reranker trained only on permissively licensed data, reproducible with one command."),
    dict(key="lab", name="The lab", status="rushlabs.ai", motif="current",
         href="https://rushlabs.ai",
         summary="Why we picked each project, how we build models, and every result."),
]
CARD_W, GAP = 488, 24
COVER_H = 220


def cover(x, y, w, h, motif, t, uid, rx=16):
    s = (max if motif in ("quant", "current") else min)(w / 800, h / 500)
    dx, dy = x + (w - 800 * s) / 2, y + (h - 500 * s) / 2
    clip = f'<clipPath id="{uid}m"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/></clipPath>'
    body = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{t["screen"]}"/>'
            f'<g clip-path="url(#{uid}m)"><g transform="translate({dx:.1f} {dy:.1f}) scale({s:.4f})">{MOTIFS[motif]()}</g></g>'
            f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="none" stroke="#1F3A32"/>')
    return clip, body


def balanced(s, font, size, max_w):
    """Wrap like CSS text-wrap: balance for two lines: no lone word on the last line."""
    lines = wrap(s, font, size, max_w)
    if len(lines) != 2:
        return lines
    words = s.split(" ")
    best = min((max(font.width(" ".join(words[:i]), size), font.width(" ".join(words[i:]), size)), i)
               for i in range(1, len(words)))
    return [" ".join(words[:best[1]]), " ".join(words[best[1]:])]


def card_lines(p):
    return balanced(p["summary"], BODY, 15, CARD_W - 2 * 22)


CARD_H = 12 + COVER_H + 34 + 34 + max(len(card_lines(p)) for p in PROJECTS) * 23 + 14


def card(p, t, side, uid):
    half = GAP // 2
    W, H = CARD_W + half, CARD_H
    dx = 0 if side == "L" else half
    doc = Doc()
    clip, cov = cover(12, 12, CARD_W - 24, COVER_H, p["motif"], t, uid)
    b = [f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{H - 1}" rx="20" fill="{t["surface"]}" stroke="{t["line"]}"/>',
         cov,
         doc.text(22, 12 + COVER_H + 34, p["status"], BODY, 14, t["muted"]),
         doc.text(22, 12 + COVER_H + 66, p["name"], WIDE, 21, t["fg"], -0.01)]
    for i, line in enumerate(card_lines(p)):
        b.append(doc.text(22, 12 + COVER_H + 96 + i * 23, line, BODY, 15, t["muted"]))
    body = f'<g transform="translate({dx},0)">{"".join(b)}</g>'
    title = f'{p["name"]}. {p["status"]}. {p["summary"]}'
    return svg(W, H, title, doc, body, MOTIF_CSS, clip)


CARD_W_M, GAP_M = 210, 16


def card_m(p, t, side, uid):
    half = GAP_M // 2
    W, CH = CARD_W_M + half, 186
    dx = 0 if side == "L" else half
    doc = Doc()
    clip, cov = cover(8, 8, CARD_W_M - 16, 96, p["motif"], t, uid, rx=12)
    b = [f'<rect x="0.5" y="0.5" width="{CARD_W_M - 1}" height="{CH - 1}" rx="16" fill="{t["surface"]}" stroke="{t["line"]}"/>',
         cov,
         doc.text(16, 132, p["status"], BODY, 13, t["muted"])]
    name_size = 19 if WIDE.width(p["name"], 19) <= CARD_W_M - 32 else 16
    b.append(doc.text(16, 162, p["name"], WIDE, name_size, t["fg"], -0.01))
    body = f'<g transform="translate({dx},0)">{"".join(b)}</g>'
    title = f'{p["name"]}. {p["status"]}. {p["summary"]}'
    return svg(W, CH, title, doc, body, MOTIF_CSS, clip)


# ── Footer icons ────────────────────────────────────────────────────────────
def icon_web():
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" role="img" aria-label="Website">'
            f'<g fill="none" stroke="{ICON_GREY}" stroke-width="2" stroke-linecap="round">'
            '<circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4.5" ry="10"/><line x1="2" y1="12" x2="22" y2="12"/></g></svg>')


def icon_mail():
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" role="img" aria-label="Email">'
            f'<g fill="none" stroke="{ICON_GREY}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M3 6l9 7 9-7"/></g></svg>')


# ── Build ───────────────────────────────────────────────────────────────────
def main():
    files = {"icon-web": icon_web(), "icon-mail": icon_mail()}
    for name, t in THEMES.items():
        files[f"header-{name}"] = header(t, "h")
        files[f"header-m-{name}"] = header_m(t, "h")
        for i, p in enumerate(PROJECTS):
            side = "L" if i % 2 == 0 else "R"
            files[f"card-{p['key']}-{name}"] = card(p, t, side, "c")
            files[f"card-m-{p['key']}-{name}"] = card_m(p, t, side, "c")

    ver = hashlib.sha1("".join(files[k] for k in sorted(files)).encode()).hexdigest()[:7]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for stem, content in files.items():
        (OUT / f"{stem}.{ver}.svg").write_text(content)

    mobile = "(max-width: 767px)"

    def pic(stem, alt, width="100%", href=None, m=None):
        src = ""
        if m:
            src += (f'<source media="{mobile} and (prefers-color-scheme: dark)" srcset="assets/{m}-dark.{ver}.svg">'
                    f'<source media="{mobile}" srcset="assets/{m}-light.{ver}.svg">')
        src += f'<source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.{ver}.svg">'
        out = f'<picture>{src}<img alt="{escape(alt)}" src="assets/{stem}-light.{ver}.svg" width="{width}"></picture>'
        return f'<a href="{href}">{out}</a>' if href else out

    blocks = [pic("header", HEADER_ALT, href="https://rushlabs.ai", m="header-m")]
    for i in range(0, len(PROJECTS), 2):
        a, b = PROJECTS[i], PROJECTS[i + 1]
        blocks.append(pic(f"card-{a['key']}", f'{a["name"]}. {a["status"]}. {a["summary"]}', "50%", a["href"], f"card-m-{a['key']}")
                      + pic(f"card-{b['key']}", f'{b["name"]}. {b["status"]}. {b["summary"]}', "50%", b["href"], f"card-m-{b['key']}"))
    blocks.append('<p align="center">'
                  f'<img src="assets/icon-web.{ver}.svg" height="15" alt="Website"> <a href="https://rushlabs.ai">rushlabs.ai</a>'
                  '&nbsp;&nbsp;&nbsp;&nbsp;'
                  f'<img src="assets/icon-mail.{ver}.svg" height="15" alt="Email"> <a href="mailto:admin@rushlabs.ai">admin@rushlabs.ai</a>'
                  '</p>')
    (PROFILE / "README.md").write_text("\n\n".join(blocks) + "\n")
    sizes = sorted((len(v), k) for k, v in files.items())
    print("version", ver, "·", len(files), "svgs · largest", sizes[-1][1], sizes[-1][0] // 1024, "KB")


if __name__ == "__main__":
    main()
