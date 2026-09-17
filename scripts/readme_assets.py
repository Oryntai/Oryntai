#!/usr/bin/env python3
"""Renders the SVG assets shown in README.md.

    python3 scripts/readme_assets.py static   hero, contact buttons, spotlight, project cards, stack, timeline
    python3 scripts/readme_assets.py stats    activity panel from the GitHub GraphQL API (needs GITHUB_TOKEN)

Each asset is written as assets/<name>-light.svg and assets/<name>-dark.svg, and README.md
picks the variant with <picture> + prefers-color-scheme. Standard library only.
Icons: Simple Icons (CC0) in scripts/icons/simple, Lucide (ISC) in scripts/icons/lucide.

Text in SVG is laid out without a font engine, so widths are estimated from Helvetica
metrics with a safety margin; `warn()` flags anything that might not fit.
"""
import colorsys
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = Path(__file__).resolve().parent / "icons"
LOGIN = "Oryntai"

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "light": dict(
        surface="#ffffff", raised="#f6f8fa", border="#d1d9e0", grid="#e6eaef",
        text="#1f2328", muted="#59636e", faint="#6e7781",
        accent="#0f766e", accent2="#0369a1",
        hero_a="#ecfdf8", hero_b="#f6f8fa", dots="#0f172a", dots_opacity=0.12,
        glow_a="#5eead4", glow_b="#a5b4fc", glow_opacity=0.45, shadow=0.22,
        bar="#0d9488", langs=["#2a78d6", "#eb6834", "#1baf7a"], other="#8c959f",
    ),
    "dark": dict(
        surface="#161b22", raised="#1f242c", border="#30363d", grid="#262c35",
        text="#e6edf3", muted="#9198a1", faint="#8b949e",
        accent="#2dd4bf", accent2="#38bdf8",
        hero_a="#0a1f24", hero_b="#0d1117", dots="#ffffff", dots_opacity=0.08,
        glow_a="#14b8a6", glow_b="#6366f1", glow_opacity=0.30, shadow=0.55,
        bar="#0d9488", langs=["#3987e5", "#d95926", "#199e70"], other="#6e7681",
    ),
}

# Card accent hues: (light, dark). Used for small marks and labels only.
HUES = {
    "teal": ("#0f766e", "#2dd4bf"), "violet": ("#6d28d9", "#a78bfa"), "sky": ("#0369a1", "#38bdf8"),
    "rose": ("#be123c", "#fb7185"), "amber": ("#b45309", "#fbbf24"), "indigo": ("#4338ca", "#818cf8"),
    "orange": ("#c2410c", "#fb923c"), "lime": ("#4d7c0f", "#a3e635"),
}

BRAND = {  # Simple Icons brand colors; None = use the text color
    "python": "#3776AB", "fastapi": "#009688", "django": "#092E20", "postgresql": "#4169E1",
    "redis": "#FF4438", "rabbitmq": "#FF6600", "celery": "#37814A", "sqlalchemy": "#D71F00",
    "pydantic": "#E92063", "openai": None, "claude": "#D97757", "googlegemini": "#8E75B2",
    "modelcontextprotocol": None, "pytorch": "#EE4C2C", "opencv": "#5C3EE8", "typescript": "#3178C6",
    "react": "#61DAFB", "vuedotjs": "#4FC08D", "nuxt": "#00DC82", "tailwindcss": "#06B6D4",
    "expo": None, "docker": "#2496ED", "nginx": "#009639", "linux": "#FCC624",
    "githubactions": "#2088FF", "nodedotjs": "#5FA04E", "pytest": "#0A9EDC", "playwright": "#2EAD33",
    "telegram": "#26A5E4", "godotengine": "#478CBF", "mqtt": "#660066",
}

HERO_CODE = [
    [("class ", "kw"), ("Oryntai", "cls"), ("(", "p"), ("Engineer", "base"), ("):", "p")],
    [("    ", "p"), ('"""Backend + AI integrations."""', "str")],
    [("    stack ", "p"), ("= ", "kw"), ("[", "p"), ('"python"', "str"), (", ", "p"), ('"postgres"', "str"), ("]", "p")],
    [("    ai ", "p"), ("= ", "kw"), ("[", "p"), ('"agents"', "str"), (", ", "p"), ('"rag"', "str"), (", ", "p"),
     ('"mcp"', "str"), ("]", "p")],
    [],
    [("    ", "p"), ("def ", "kw"), ("ship", "fn"), ("(", "p"), ("self", "var"), (", ", "p"), ("idea", "var"), ("):", "p")],
    [("        ", "p"), ("return ", "kw"), ("deploy", "fn"), ("(", "p"), ("build", "fn"), ("(", "p"), ("idea", "var"),
     ("))", "p")],
]
SYNTAX = {"kw": "#ff7b72", "cls": "#ffa657", "base": "#79c0ff", "str": "#a5d6ff", "fn": "#d2a8ff",
          "var": "#ffa657", "p": "#e6edf3"}

FEATURED = [
    dict(slug="agentlink", title="AgentLink", hue="teal", icon="messages-square", eyebrow="AI agents · open source",
         desc="Encrypted peer-to-peer bridge that lets local Codex and Claude agents talk to each other.",
         tags=[("nodedotjs", "Node.js"), ("modelcontextprotocol", "MCP"), ("lucide:lock", "E2E encryption")]),
    dict(slug="observer", title="Observer", hue="violet", icon="crown", eyebrow="LLM agents · simulation",
         desc="Two pixel-art tribes whose rulers are Claude Haiku agents acting through MCP tools.",
         tags=[("godotengine", "Godot 4"), ("python", "Python"), ("claude", "Claude Agent SDK")]),
    dict(slug="salyq", title="Salyq AI", hue="sky", icon="scale", eyebrow="RAG · legal tech",
         desc="Tax consultant for Kazakhstan: plain-language answers with citations to Tax Code articles.",
         tags=[("fastapi", "FastAPI"), ("react", "React"), ("openai", "OpenAI")]),
    dict(slug="iot", title="IoT Security Monitoring", hue="rose", icon="shield-check", eyebrow="Security · ML · diploma",
         desc="Rule-based device checks plus a PyTorch autoencoder that flags anomalous IoT traffic.",
         tags=[("fastapi", "FastAPI"), ("pytorch", "PyTorch"), ("mqtt", "MQTT")]),
]
COMPACT = [
    dict(slug="braincanvas", title="BrainCanvas", hue="indigo", icon="pen-tool", eyebrow="Realtime · React · Yjs",
         desc="Whiteboard with a voice-driven AI teammate."),
    dict(slug="fire", title="FIRE", hue="orange", icon="flame", eyebrow="Hackathon · FastAPI · Gemini",
         desc="LLM triage and routing of support tickets."),
    dict(slug="browser-agent", title="browser-agent", hue="amber", icon="globe", eyebrow="Hackathon · Playwright",
         desc="Backend for an autonomous LLM browser agent."),
    dict(slug="handstick", title="Handstick", hue="lime", icon="hand", eyebrow="Computer vision · MediaPipe",
         desc="Hands-free mouse via webcam palm tracking."),
]

STACK = [
    ("Backend", [("python", "Python"), ("fastapi", "FastAPI"), ("django", "Django"), ("postgresql", "PostgreSQL"),
                 ("redis", "Redis"), ("rabbitmq", "RabbitMQ"), ("celery", "Celery"), ("sqlalchemy", "SQLAlchemy"),
                 ("pydantic", "Pydantic"), ("pytest", "pytest")]),
    ("AI & ML", [("openai", "OpenAI"), ("claude", "Claude"), ("googlegemini", "Gemini"),
                 ("modelcontextprotocol", "MCP"), ("lucide:sparkles", "RAG"), ("pytorch", "PyTorch"),
                 ("opencv", "OpenCV")]),
    ("Frontend", [("typescript", "TypeScript"), ("react", "React"), ("vuedotjs", "Vue"), ("nuxt", "Nuxt"),
                  ("tailwindcss", "Tailwind CSS"), ("expo", "React Native")]),
    ("Infra & tools", [("docker", "Docker"), ("nginx", "Nginx"), ("linux", "Linux"),
                       ("githubactions", "GitHub Actions"), ("nodedotjs", "Node.js"),
                       ("playwright", "Playwright")]),
]

EXPERIENCE = [
    ("Future.AI", "Developer · Integration Engineer", "19 months", "AI solutions, REST APIs, integrations"),
    ("Freelance", "Developer", "1 year", "Bots, web apps and REST APIs for clients"),
    ("AGI Center", "Backend / Web Developer Intern", "1.5 months", "Genetics and healthcare projects"),
]
EDUCATION = ("Astana IT University", "B.Sc. in Information Security", "2023–2026",
             "Diploma: intelligent IoT security monitoring")
LANGUAGES = [("Kazakh", "native"), ("Russian", "fluent"), ("English", "B2")]

# Activity panel: repos that are public but not part of the showcase, and non-code languages.
STATS_EXCLUDE_REPOS = {"Oryntai", "Trendsee", "HackhatonQazCode", "Job-Application-CRM", "CLI-tool-for-taking-notes",
                       "noticeboard", "reminderbot", "MalwareProjectpsy"}
STATS_HIDE_LANGS = {"HTML", "CSS", "SCSS", "Jupyter Notebook", "Dockerfile", "Makefile", "Shell", "PowerShell",
                    "Batchfile", "Procfile", "Mako", "Jinja"}
# Categorical slots follow the language, never its rank. Three slots validate all-pairs in
# both modes; everything else folds into "Other".
STATS_LANGS = ["Python", "TypeScript", "JavaScript"]


# --------------------------------------------------------------------------- text metrics

_REG = ([278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 +
        [278, 278, 584, 584, 584, 556, 1015,
         667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667,
         944, 667, 667, 611, 278, 278, 278, 469, 556, 333,
         556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500,
         722, 500, 500, 500, 334, 260, 334, 584])
_BOLD = ([278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 +
         [333, 333, 584, 584, 584, 611, 975,
          722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667,
          944, 667, 667, 611, 333, 278, 333, 584, 556, 333,
          556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556,
          778, 556, 556, 500, 389, 280, 389, 584])
_EXTRA = {"·": 278, "—": 1000, "–": 556, "’": 278, "…": 1000, "█": 600}
assert len(_REG) == len(_BOLD) == 95


def text_w(s, size, bold=False, mono=False, spacing=0.0):
    """Estimated rendered width; errs on the wide side (Noto Sans / DejaVu are wider than Helvetica)."""
    if mono:
        return len(s) * size * 0.61 + spacing * max(len(s) - 1, 0)
    table = _BOLD if bold else _REG
    units = sum(table[ord(c) - 32] if 32 <= ord(c) <= 126 else _EXTRA.get(c, 600) for c in s)
    return units / 1000 * size * 1.08 + spacing * max(len(s) - 1, 0)


def wrap(s, size, max_w, bold=False):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and text_w(trial, size, bold) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def warn(msg):
    print(f"WARN: {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- color

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(r, g, b):
    return "#%02x%02x%02x" % tuple(round(max(0.0, min(1.0, v)) * 255) for v in (r, g, b))


def _lum(h):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable(color, bg, ratio=3.0):
    """Keeps a brand color's hue but moves its lightness until it clears `ratio` against bg."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(color))
    step = 0.02 if _lum(bg) < 0.5 else -0.02
    while contrast(_hex(*colorsys.hls_to_rgb(h, l, s)), bg) < ratio and 0.0 <= l <= 1.0:
        l += step
    return _hex(*colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s))


# --------------------------------------------------------------------------- svg helpers

def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def document(w, h, title, body, defs="", css="", desc=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title>" + (f"<desc>{escape(desc)}</desc>" if desc else "") +
        f"<style>.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}{css}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
        f"<defs>{defs}</defs>{body}</svg>\n"
    )


def text(x, y, s, size, fill, mono=False, weight=None, anchor=None, spacing=None, attrs=""):
    a = f'x="{f(x)}" y="{f(y)}" class="{"m" if mono else "s"}" font-size="{size}" fill="{fill}"'
    if weight:
        a += f' font-weight="{weight}"'
    if anchor:
        a += f' text-anchor="{anchor}"'
    if spacing:
        a += f' letter-spacing="{spacing}"'
    return f"<text {a}{attrs}>{escape(s)}</text>"


def _icon_body(kind, name):
    svg = (ICONS / kind / f"{name}.svg").read_text()
    if kind == "simple":
        return re.search(r' d="([^"]+)"', svg).group(1)
    body = svg[svg.index(">", svg.index("<svg")) + 1:svg.rindex("</svg>")]
    return re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()


def icon(spec, x, y, size, color):
    """spec: a Simple Icons slug, or 'lucide:<name>'."""
    k = size / 24
    tr = f'transform="translate({f(x)} {f(y)}) scale({k:.4f})"'
    if spec.startswith("lucide:"):
        return (f'<g {tr} fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
                f'stroke-linejoin="round">{_icon_body("lucide", spec[7:])}</g>')
    return f'<path {tr} fill="{color}" d="{_icon_body("simple", spec)}"/>'


def icon_color(spec, t, bg):
    if spec.startswith("lucide:"):
        return t["accent"]
    brand = BRAND.get(spec)
    return readable(brand, bg, 3.0) if brand else t["text"]


def pill(x, y, label, t, h=36, size=16, spec=None, rx=None, weight=500, fill=None, color=None):
    """Returns (svg, width)."""
    icon_size = round(h * 0.5)
    w = (12 + icon_size + 8 if spec else 16) + text_w(label, size, bold=weight >= 600) + 14
    bg = fill or t["raised"]
    out = (f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{h}" rx="{f(h / 2 if rx is None else rx)}" '
           f'fill="{bg}" stroke="{t["border"]}" stroke-width="1.5"/>')
    tx = x + 16
    if spec:
        out += icon(spec, x + 12, y + (h - icon_size) / 2, icon_size, icon_color(spec, t, bg))
        tx = x + 12 + icon_size + 8
    out += text(tx, y + h / 2 + size * 0.35, label, size, color or t["text"], weight=weight)
    return out, w


def write(name, theme, svg):
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / f"{name}-{theme}.svg").write_text(svg)


# --------------------------------------------------------------------------- static assets

def hero(t, theme):
    W, H = 1280, 440
    dark = theme == "dark"
    defs = (
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["hero_a"]}"/>'
        f'<stop offset="1" stop-color="{t["hero_b"]}"/></linearGradient>'
        f'<radialGradient id="ga"><stop offset="0" stop-color="{t["glow_a"]}" stop-opacity="{t["glow_opacity"]}"/>'
        f'<stop offset="1" stop-color="{t["glow_a"]}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="gb"><stop offset="0" stop-color="{t["glow_b"]}" stop-opacity="{t["glow_opacity"] * 0.7:.2f}"/>'
        f'<stop offset="1" stop-color="{t["glow_b"]}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="name" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["accent"]}"/>'
        f'<stop offset="1" stop-color="{t["accent2"]}"/></linearGradient>'
        f'<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">'
        f'<circle cx="13" cy="13" r="1.4" fill="{t["dots"]}"/></pattern>'
        '<radialGradient id="fade" cx="0.35" cy="0.5" r="0.75"><stop offset="0" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#000"/></radialGradient>'
        f'<mask id="dm"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>'
        f'<clipPath id="clip"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="28"/></clipPath>'
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="170%">'
        f'<feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#0f172a" flood-opacity="{t["shadow"]}"/></filter>'
    )
    css = (".ping{transform-box:fill-box;transform-origin:center;animation:ping 2.4s cubic-bezier(0,0,.2,1) infinite}"
           "@keyframes ping{75%,100%{transform:scale(2.6);opacity:0}}"
           ".cursor{animation:blink 1.1s steps(1,end) infinite}@keyframes blink{50%{opacity:0}}")
    b = [
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="28" fill="url(#bg)"/>',
        '<g clip-path="url(#clip)">',
        '<circle cx="1110" cy="20" r="430" fill="url(#ga)"/><circle cx="60" cy="480" r="380" fill="url(#gb)"/>',
        f'<rect width="{W}" height="{H}" fill="url(#dots)" opacity="{t["dots_opacity"]}" mask="url(#dm)"/>',
        "</g>",
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="28" fill="none" stroke="{t["border"]}" stroke-width="2"/>',
    ]
    # Left: location, name, role.
    loc = "Astana, Kazakhstan"
    pw = 44 + text_w(loc, 17, mono=True) + 18
    b += [
        f'<rect x="76" y="78" width="{f(pw)}" height="40" rx="20" fill="{t["surface"]}" fill-opacity="0.75" '
        f'stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<circle class="ping" cx="98" cy="98" r="5" fill="none" stroke="{t["accent"]}" stroke-width="2" opacity="0.6"/>',
        f'<circle cx="98" cy="98" r="5" fill="{t["accent"]}"/>',
        text(114, 104, loc, 17, t["muted"], mono=True),
        text(72, 210, "Oryntai", 80, t["text"], weight=800, spacing=-1.5),
        text(72, 296, "Pazylbekov", 80, "url(#name)", weight=800, spacing=-1.5),
        text(76, 354, "Python backend · AI integrations", 30, t["muted"], weight=500),
    ]
    if text_w("Pazylbekov", 80, bold=True) + 72 > 670:
        warn("hero name may run into the code window")
    # Right: code window (dark in both themes).
    x, y, w, h = 688, 70, 528, 300
    b += [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#0d1117" filter="url(#shadow)"/>',
        f'<path d="M{x} {y + 52}V{y + 18}a18 18 0 0 1 18-18h{w - 36}a18 18 0 0 1 18 18V{y + 52}Z" fill="#161b22"/>',
        f'<line x1="{x}" y1="{y + 52}" x2="{x + w}" y2="{y + 52}" stroke="#30363d"/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="none" '
        f'stroke="{"#30363d" if dark else "#0f172a"}" stroke-opacity="{1 if dark else 0.6}" stroke-width="1.5"/>',
    ]
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        b.append(f'<circle cx="{x + 28 + i * 22}" cy="{y + 26}" r="6.5" fill="{c}"/>')
    b.append(text(x + w / 2, y + 32, "oryntai.py", 16, "#8b949e", mono=True, anchor="middle"))
    for i, line in enumerate(HERO_CODE):
        ly = y + 90 + i * 30
        b.append(text(x + 36, ly, str(i + 1), 17, "#6e7681", mono=True, anchor="end"))
        spans = "".join(f'<tspan fill="{SYNTAX[kind]}">{escape(s)}</tspan>' for s, kind in line)
        if i == len(HERO_CODE) - 1:
            spans += f'<tspan class="cursor" fill="{THEMES["dark"]["accent"]}">█</tspan>'
        width = sum(len(s) for s, _ in line) + (1 if i == len(HERO_CODE) - 1 else 0)
        if 56 + width * 18 * 0.61 > w - 20:
            warn(f"hero code line {i + 1} may overflow the window")
        b.append(f'<text x="{x + 56}" y="{ly}" class="m" font-size="18" xml:space="preserve">{spans}</text>')
    title = "Oryntai Pazylbekov — Python backend developer and AI integration engineer, Astana, Kazakhstan"
    return document(W, H, title, "".join(b), defs, css)


def button(t, theme, kind):
    if kind == "email":
        label, value, spec = "Email", "pazylbekovoryntai@gmail.com", "lucide:mail"
    else:
        label, value, spec = "Telegram", "@oryntaivez", "telegram"
    H, size = 64, 21
    lw = text_w(label, size, bold=True)
    W = round(64 + lw + 12 + text_w(value, size) + 28)
    body = (
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{(H - 2) / 2}" fill="{t["surface"]}" '
        f'stroke="{t["border"]}" stroke-width="2"/>'
        + icon(spec, 26, 19, 26, icon_color(spec, t, t["surface"]))
        + text(64, 40, label, size, t["text"], weight=600)
        + text(64 + lw + 12, 40, value, size, t["muted"])
    )
    return document(W, H, f"{label}: {value}", body)


def spotlight(t, theme):
    W, H = 1280, 244
    hue = t["accent"]
    defs = (
        f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{hue}" stop-opacity="0.9"/>'
        f'<stop offset="0.45" stop-color="{t["border"]}"/><stop offset="1" stop-color="{t["border"]}"/></linearGradient>'
        f'<linearGradient id="tile" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#14b8a6"/>'
        f'<stop offset="1" stop-color="#0369a1"/></linearGradient>'
        f'<radialGradient id="glow"><stop offset="0" stop-color="{t["glow_a"]}" stop-opacity="{t["glow_opacity"] * 0.6:.2f}"/>'
        f'<stop offset="1" stop-color="{t["glow_a"]}" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="clip"><rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24"/></clipPath>'
    )
    b = [
        f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24" fill="{t["surface"]}"/>',
        f'<g clip-path="url(#clip)"><circle cx="{W - 60}" cy="10" r="320" fill="url(#glow)"/></g>',
        f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24" fill="none" stroke="url(#edge)" stroke-width="2"/>',
        '<rect x="40" y="40" width="76" height="76" rx="22" fill="url(#tile)"/>',
        icon("lucide:graduation-cap", 57, 57, 42, "#ffffff"),
        text(144, 68, "COMMERCIAL PRODUCT · CLOSED SOURCE", 16, hue, mono=True, spacing=1.6),
        text(W - 74, 68, "oqcrm.kz", 18, t["muted"], mono=True, anchor="end"),
        icon("lucide:arrow-up-right", W - 66, 50, 22, t["muted"]),
        text(144, 116, "oqCRM", 42, t["text"], weight=700),
    ]
    sub_x = 144 + text_w("oqCRM", 42, bold=True) + 16
    b.append(text(sub_x, 116, "CRM for education centers", 28, t["muted"], weight=500))
    desc = "Built from scratch: leads, schedules, payments and teacher payroll in one system."
    if 144 + text_w(desc, 22) > W - 40:
        warn("spotlight description may overflow")
    b.append(text(144, 160, desc, 22, t["muted"]))
    x = 144
    for spec, label in [("fastapi", "FastAPI"), ("postgresql", "PostgreSQL"), ("react", "React"),
                        ("expo", "React Native")]:
        svg, w = pill(x, 184, label, t, h=40, size=18, spec=spec)
        b.append(svg)
        x += w + 10
    b.append(text(W - 44, 210, "web + mobile apps", 17, t["faint"], mono=True, anchor="end"))
    title = ("oqCRM — commercial CRM for education centers, built from scratch: leads, schedules, payments and "
             "teacher payroll. FastAPI, PostgreSQL, React, React Native. oqcrm.kz")
    return document(W, H, title, "".join(b), defs)


def card(t, theme, p, compact=False):
    hue = HUES[p["hue"]][0 if theme == "light" else 1]
    W, m = 540, 6
    H = 150 if compact else 280
    r = 18 if compact else 20
    tile = 46 if compact else 56
    tx = m + (22 if compact else 24)
    x0 = tx + tile + 18
    arrow = 20 if compact else 22
    defs = (
        f'<radialGradient id="glow"><stop offset="0" stop-color="{hue}" stop-opacity="{0.16 if theme == "dark" else 0.10}"/>'
        f'<stop offset="1" stop-color="{hue}" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="clip"><rect x="{m}" y="{m}" width="{W - 2 * m}" height="{H - 2 * m}" rx="{r}"/></clipPath>'
    )
    b = [
        f'<rect x="{m}" y="{m}" width="{W - 2 * m}" height="{H - 2 * m}" rx="{r}" fill="{t["surface"]}"/>',
        f'<g clip-path="url(#clip)"><circle cx="{W - m}" cy="{m}" r="{150 if compact else 210}" fill="url(#glow)"/></g>',
        f'<rect x="{m}" y="{m}" width="{W - 2 * m}" height="{H - 2 * m}" rx="{r}" fill="none" '
        f'stroke="{t["border"]}" stroke-width="1.5"/>',
        f'<rect x="{tx}" y="{tx}" width="{tile}" height="{tile}" rx="{14 if compact else 16}" fill="{hue}" '
        f'fill-opacity="0.12" stroke="{hue}" stroke-opacity="0.35" stroke-width="1.5"/>',
    ]
    isz = 24 if compact else 30
    b.append(icon("lucide:" + p["icon"], tx + (tile - isz) / 2, tx + (tile - isz) / 2, isz, hue))
    b.append(icon("lucide:arrow-up-right", W - m - 24 - arrow, m + 24, arrow, t["faint"]))
    eyebrow = p["eyebrow"].upper()
    ey, ty, tsize = (m + 42, m + 70, 24) if compact else (m + 46, m + 76, 28)
    right_limit = W - m - 24 - arrow - 12
    if x0 + text_w(eyebrow, 15, mono=True, spacing=1.2) > right_limit:
        warn(f"{p['slug']}: eyebrow may run into the arrow")
    if x0 + text_w(p["title"], tsize, bold=True) > right_limit:
        warn(f"{p['slug']}: title may run into the arrow")
    b.append(text(x0, ey, eyebrow, 15, hue, mono=True, spacing=1.2))
    b.append(text(x0, ty, p["title"], tsize, t["text"], weight=700))
    text_left, text_max = m + 22, W - 2 * m - 44
    if compact:
        if text_w(p["desc"], 19) > text_max:
            warn(f"{p['slug']}: description does not fit on one line")
        b.append(text(text_left, 118, p["desc"], 19, t["muted"]))
    else:
        lines = wrap(p["desc"], 20, text_max)
        if len(lines) > 3:
            warn(f"{p['slug']}: description needs {len(lines)} lines")
        for i, line in enumerate(lines[:3]):
            b.append(text(text_left, 132 + i * 29, line, 20, t["muted"]))
        x = text_left
        for spec, label in p["tags"]:
            svg, w = pill(x, 214, label, t, h=36, size=16, spec=spec)
            if x + w > W - m - 20:
                warn(f"{p['slug']}: tag '{label}' dropped, no room")
                break
            b.append(svg)
            x += w + 8
    tags = ", ".join(label for _, label in p.get("tags", []))
    title = f"{p['title']} — {p['desc']}" + (f" ({tags})" if tags else "")
    return document(W, H, title, "".join(b), defs)


def stack(t, theme):
    W, x0, x_max, ph, gap, size = 1280, 244, 1236, 52, 10, 21
    parts, y = [], 40
    for i, (label, items) in enumerate(STACK):
        if i:
            parts.append(f'<line x1="44" y1="{y - 16}" x2="{x_max}" y2="{y - 16}" stroke="{t["border"]}" '
                         f'stroke-opacity="0.7"/>')
        parts.append(text(44, y + ph / 2 + 6, label.upper(), 16, t["faint"], mono=True, spacing=1.4))
        x, row_y = x0, y
        for spec, name in items:
            _, w = pill(x, row_y, name, t, h=ph, size=size, spec=spec, rx=14)
            if x + w > x_max:
                x, row_y = x0, row_y + ph + 12
            svg, w = pill(x, row_y, name, t, h=ph, size=size, spec=spec, rx=14)
            parts.append(svg)
            x += w + gap
        y = row_y + ph + 32
    H = y - 32 + 40
    body = (f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24" fill="{t["surface"]}" '
            f'stroke="{t["border"]}" stroke-width="2"/>' + "".join(parts))
    title = "Stack — " + "; ".join(f"{label}: {', '.join(n for _, n in items)}" for label, items in STACK)
    return document(W, H, title, body)


def timeline(t, theme):
    W, H = 1280, 460
    b = [f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24" fill="{t["surface"]}" '
         f'stroke="{t["border"]}" stroke-width="2"/>',
         f'<line x1="640" y1="44" x2="640" y2="{H - 44}" stroke="{t["border"]}" stroke-opacity="0.7"/>']

    def dur_pill(right, y, label):
        w = text_w(label, 15, mono=True) + 26
        return (f'<rect x="{f(right - w)}" y="{y - 23}" width="{f(w)}" height="30" rx="15" fill="{t["raised"]}" '
                f'stroke="{t["border"]}" stroke-width="1.5"/>'
                + text(right - w / 2, y - 3, label, 15, t["muted"], mono=True, anchor="middle"))

    def entry(x, y, title_s, role, when, desc, right):
        out = [f'<circle cx="{x + 10}" cy="{y - 9}" r="7" fill="{t["surface"]}" stroke="{t["accent"]}" stroke-width="3.5"/>',
               text(x + 40, y, title_s, 27, t["text"], weight=700), dur_pill(right, y, when),
               text(x + 40, y + 33, role, 21, t["accent"], weight=500),
               text(x + 40, y + 63, desc, 20, t["muted"])]
        if x + 40 + text_w(title_s, 27, bold=True) > right - text_w(when, 15, mono=True) - 38:
            warn(f"timeline: '{title_s}' may run into its date")
        if x + 40 + text_w(desc, 20) > right:
            warn(f"timeline: description of '{title_s}' may overflow")
        return "".join(out)

    b.append(text(48, 66, "EXPERIENCE", 15, t["faint"], mono=True, spacing=1.6))
    ys = [124 + i * 110 for i in range(len(EXPERIENCE))]
    b.append(f'<line x1="58" y1="{ys[0] - 9}" x2="58" y2="{ys[-1] - 9}" stroke="{t["border"]}" stroke-width="2"/>')
    for (name, role, when, desc), y in zip(EXPERIENCE, ys):
        b.append(entry(48, y, name, role, when, desc, 604))

    b.append(text(688, 66, "EDUCATION", 15, t["faint"], mono=True, spacing=1.6))
    b.append(entry(688, 124, *EDUCATION, 1236))
    b.append(text(688, 262, "LANGUAGES", 15, t["faint"], mono=True, spacing=1.6))
    x = 688
    for lang, level in LANGUAGES:
        svg, w = pill(x, 284, f"{lang} · {level}", t, h=44, size=19)
        b.append(svg)
        x += w + 10
    title = ("Experience: " + "; ".join(f"{n}, {r}, {w} — {d}" for n, r, w, d in EXPERIENCE)
             + f". Education: {EDUCATION[0]}, {EDUCATION[1]}, {EDUCATION[2]}. Languages: "
             + ", ".join(f"{a} ({b_})" for a, b_ in LANGUAGES))
    return document(W, H, title, "".join(b))


def build_static():
    for theme, t in THEMES.items():
        write("hero", theme, hero(t, theme))
        write("btn-email", theme, button(t, theme, "email"))
        write("btn-telegram", theme, button(t, theme, "telegram"))
        write("oqcrm", theme, spotlight(t, theme))
        for p in FEATURED:
            write(f"card-{p['slug']}", theme, card(t, theme, p))
        for p in COMPACT:
            write(f"card-{p['slug']}", theme, card(t, theme, p, compact=True))
        write("stack", theme, stack(t, theme))
        write("timeline", theme, timeline(t, theme))


# --------------------------------------------------------------------------- activity panel

STATS_QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
    pullRequests { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes { name languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}"""


def fetch_stats(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": STATS_QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": f"{LOGIN}-readme-assets"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {payload.get('errors')}")
    user = payload["data"]["user"]

    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [(w["contributionDays"][0]["date"], sum(d["contributionCount"] for d in w["contributionDays"]))
             for w in cal["weeks"] if w["contributionDays"]]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    longest = run = 0
    for c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)

    sizes = {}
    for repo in user["repositories"]["nodes"]:
        if repo["name"] in STATS_EXCLUDE_REPOS:
            continue
        for e in repo["languages"]["edges"]:
            if e["node"]["name"] not in STATS_HIDE_LANGS:
                sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    total = sum(sizes.values()) or 1
    langs = [(name, sizes.get(name, 0) / total) for name in STATS_LANGS if sizes.get(name)]
    other = 1 - sum(share for _, share in langs)
    return dict(contributions=cal["totalContributions"], longest=longest, prs=user["pullRequests"]["totalCount"],
                repos=user["repositories"]["totalCount"], weeks=weeks, langs=langs, other=other)


def _nice_ceiling(v):
    for n in (5, 10, 20, 25, 50, 100, 150, 200, 250, 500, 1000):
        if v <= n:
            return n
    return math.ceil(v / 1000) * 1000


def stats_panel(t, theme, s):
    W, H = 1280, 580
    b = [f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="24" fill="{t["surface"]}" '
         f'stroke="{t["border"]}" stroke-width="2"/>']

    # KPI row: sentence-case label over a semibold value.
    tiles = [("Contributions, past year", f"{s['contributions']:,}"),
             ("Longest streak", f"{s['longest']} day{'s' if s['longest'] != 1 else ''}"),
             ("Pull requests", f"{s['prs']:,}"),
             ("Public repositories", f"{s['repos']:,}")]
    for i, (label, value) in enumerate(tiles):
        x = 48 + i * 298
        if i:
            b.append(f'<line x1="{x - 26}" y1="48" x2="{x - 26}" y2="150" stroke="{t["border"]}"/>')
        b.append(text(x, 80, label, 20, t["muted"]))
        b.append(text(x, 138, value, 50, t["text"], weight=600))

    # Contributions per week: one series, so one hue and no legend; the title names it.
    left, right, top, base = 48, 1232, 250, 392
    b.append(text(left, 214, "Contributions per week", 21, t["text"], weight=600))
    weeks = s["weeks"]
    vmax = _nice_ceiling(max((v for _, v in weeks), default=0) or 1)
    b.append(f'<line x1="{left}" y1="{top}" x2="{right}" y2="{top}" stroke="{t["grid"]}"/>')
    b.append(text(right, top - 9, f"{vmax}", 16, t["muted"], anchor="end"))
    slot = (right - left) / max(len(weeks), 1)
    bw = min(16.0, slot - 4)
    peak = max(range(len(weeks)), key=lambda i: weeks[i][1]) if weeks else None
    last_label = -10
    for i, (start, v) in enumerate(weeks):
        x = left + i * slot + (slot - bw) / 2
        hgt = v / vmax * (base - top)
        if v and hgt < 3:
            hgt = 3
        if hgt:
            r = min(4, hgt, bw / 2)
            y = base - hgt
            b.append(f'<path d="M{f(x)} {base}V{f(y + r)}Q{f(x)} {f(y)} {f(x + r)} {f(y)}H{f(x + bw - r)}'
                     f'Q{f(x + bw)} {f(y)} {f(x + bw)} {f(y + r)}V{base}Z" fill="{t["bar"]}">'
                     f"<title>Week of {start}: {v}</title></path>")
        month = start[5:7]
        if i == 0 or month != weeks[i - 1][0][5:7]:
            if i - last_label >= 3 and x + 30 < right:
                name = dt.date.fromisoformat(start).strftime("%b")
                b.append(text(x, base + 27, name, 16, t["muted"]))
                last_label = i
    if peak is not None and weeks[peak][1]:
        px = left + peak * slot + slot / 2
        py = base - max(weeks[peak][1] / vmax * (base - top), 3) - 8
        anchor = "end" if px > right - 60 else "middle"
        b.append(text(px + (bw / 2 if anchor == "end" else 0), py, f"peak {weeks[peak][1]}", 16, t["text"],
                      weight=600, anchor=anchor))
    b.append(f'<line x1="{left}" y1="{base}" x2="{right}" y2="{base}" stroke="{t["border"]}"/>')

    # Languages: part-to-whole bar with 2px surface gaps, legend + direct percentages.
    b.append(text(left, 474, "Languages in public projects", 21, t["text"], weight=600))
    segs = [(name, share, t["langs"][STATS_LANGS.index(name)]) for name, share in s["langs"]]
    segs.sort(key=lambda seg: -seg[1])
    if s["other"] > 0.005:
        segs.append(("Other", s["other"], t["other"]))
    bar_y, bar_h = 494, 16
    b.append(f'<clipPath id="bar"><rect x="{left}" y="{bar_y}" width="{right - left}" height="{bar_h}" rx="4"/></clipPath>')
    b.append('<g clip-path="url(#bar)">')
    x = left
    for i, (name, share, color) in enumerate(segs):
        w = (right - left) * share
        gap = 2 if i < len(segs) - 1 else 0
        b.append(f'<rect x="{f(x)}" y="{bar_y}" width="{f(max(w - gap, 0))}" height="{bar_h}" fill="{color}"/>')
        x += w
    b.append("</g>")
    x = left
    for name, share, color in segs:
        label = f"{name} {share * 100:.0f}%"
        b.append(f'<circle cx="{f(x + 7)}" cy="539" r="7" fill="{color}"/>')
        b.append(text(x + 22, 545, label, 18, t["text"]))
        x += 22 + text_w(label, 18) + 30

    desc = (f"{s['contributions']} contributions in the last 12 months, longest streak {s['longest']} days, "
            f"{s['prs']} pull requests, {s['repos']} public repositories. Languages: "
            + ", ".join(f"{n} {sh * 100:.0f}%" for n, sh, _ in segs))
    return document(W, H, "GitHub activity", "".join(b), desc=desc)


def build_stats():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    s = fetch_stats(token)
    for theme, t in THEMES.items():
        write("stats", theme, stats_panel(t, theme, s))
    print(json.dumps({k: v for k, v in s.items() if k != "weeks"}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "static":
        build_static()
    elif mode == "stats":
        build_stats()
    else:
        raise SystemExit(__doc__)
