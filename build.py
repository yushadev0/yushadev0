"""Builds dark_mode.svg and light_mode.svg for the GitHub profile README.

Left: the kedy cat as ASCII art (art/kedy.txt).
Right: a neofetch-style card. Age and GitHub stats are refreshed on every run.

Stats come from the GitHub GraphQL API using GITHUB_TOKEN (the workflow's
built-in token is enough). Without a token, or if the request fails, the last
values in cache/stats.json are used. Standard library only.
"""
import datetime as dt
import json
import os
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
LOGIN = os.environ.get("USER_NAME", "yushadev0")
BIRTH = dt.date(2005, 11, 18)

# Layout (px). Consolas at 16px with the 109% size-adjust below is ~9.6px per char.
CHAR_W = 9.6
LINE_H = 20
TOP = 30
PAD = 15
INFO_X = 595
INFO_COLS = 54

THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", value="#a5d6ff", cc="#616e7f"),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", value="#0a3069", cc="#c2cfde"),
}

# ---------------------------------------------------------------- data

def age_text(today):
    y = today.year - BIRTH.year
    m = today.month - BIRTH.month
    d = today.day - BIRTH.day
    if d < 0:
        m -= 1
        prev_month_end = today.replace(day=1) - dt.timedelta(days=1)
        d += prev_month_end.day
    if m < 0:
        y -= 1
        m += 12

    def unit(n, word):
        return f"{n} {word}{'' if n == 1 else 's'}"

    text = f"{unit(y, 'year')}, {unit(m, 'month')}, {unit(d, 'day')}"
    return text + (" 🎂" if m == 0 and d == 0 else "")


def graphql(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-readme-build"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats(token):
    q = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        followers { totalCount }
        repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { stargazerCount }
        }
        repositoriesContributedTo(first: 1, includeUserRepositories: true,
          contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW]) { totalCount }
        contributionsCollection {
          contributionYears
          contributionCalendar { totalContributions }
        }
      }
    }"""
    stars, cursor = 0, None
    while True:
        u = graphql(token, q, {"login": LOGIN, "cursor": cursor})["user"]
        repos = u["repositories"]
        stars += sum(n["stargazerCount"] for n in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]

    years = u["contributionsCollection"]["contributionYears"]
    parts = [
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        "{ totalCommitContributions }"
        for y in years
    ]
    yq = "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }"
    yd = graphql(token, yq, {"login": LOGIN})["user"]
    commits = sum(v["totalCommitContributions"] for v in yd.values())

    return {
        "repos": repos["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "followers": u["followers"]["totalCount"],
        "commits": commits,
        "last_year": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
    }


def load_stats():
    cache = ROOT / "cache" / "stats.json"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if token:
        try:
            stats = fetch_stats(token)
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
            return stats
        except Exception as e:  # keep the card building even if the API hiccups
            print(f"stats fetch failed, using cache: {e}")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    return dict(repos=0, contributed=0, stars=0, followers=0, commits=0, last_year=0)

# ---------------------------------------------------------------- rendering
# A row is a list of (css class or None, text) segments.

def kv(keys, value, width=INFO_COLS, lead=". "):
    """'. Key.Sub: ...... value' padded with dots to `width` chars."""
    segs = [("cc", lead)]
    used = len(lead)
    for i, k in enumerate(keys):
        if i:
            segs.append((None, "."))
            used += 1
        segs.append(("key", k))
        used += len(k)
    segs.append((None, ":"))
    used += 1
    dots = max(1, width - used - len(value) - 2)
    segs += [("cc", " " + "." * dots + " "), ("value", value)]
    return segs


def title(text, width=INFO_COLS):
    return [(None, text + " -" + "—" * max(2, width - len(text) - 2))]


def blank_dot():
    return [("cc", ". ")]


def fmt(n):
    return f"{n:,}"


def info_rows(today, s):
    pipe = 33  # column of the " | " separator in the two-stat rows
    right = INFO_COLS - pipe - 3
    contrib = [(None, " {"), ("key", "Contributed"), (None, ": "), ("value", fmt(s["contributed"])), (None, "}")]
    contrib_len = len(f" {{Contributed: {fmt(s['contributed'])}}}")
    return [
        title("yusa@guverdik"),
        kv(["OS"], "Windows 11, Ubuntu"),
        kv(["Uptime"], age_text(today)),
        kv(["IDE"], "Delphi, VS Code"),
        blank_dot(),
        kv(["Languages", "Code"], "Delphi, Python, Java, C#, Rust"),
        kv(["Languages", "Web"], "JavaScript, TypeScript"),
        kv(["Languages", "Real"], "Turkish, English"),
        blank_dot(),
        kv(["Frameworks"], "UniGUI, React, Vite, Tauri"),
        kv(["Data"], "UniDAC, FireDAC, SQLite, MSSQL, MySQL"),
        kv(["Infra"], "Linux, Docker, nginx, Git"),
        blank_dot(),
        kv(["Hobbies", "Software"], "Game dev with Godot & Unity"),
        [],
        title("- Contact"),
        kv(["Email"], "yusaguverdik@gmail.com"),
        kv(["Website"], "yusa.app"),
        kv(["LinkedIn"], "yusaguverdik"),
        [],
        title("- GitHub Stats"),
        kv(["Repos"], fmt(s["repos"]), pipe - contrib_len) + contrib
        + [(None, " | ")] + kv(["Stars"], fmt(s["stars"]), right, lead=""),
        kv(["Commits"], fmt(s["commits"]), pipe)
        + [(None, " | ")] + kv(["Followers"], fmt(s["followers"]), right, lead=""),
        kv(["Contributions", "LastYear"], fmt(s["last_year"])),
    ]


def tspans(x, y, segs):
    out = [f'<tspan x="{x}" y="{y}">']
    for cls, text in segs:
        t = escape(text, quote=False)
        out.append(f'<tspan class="{cls}">{t}</tspan>' if cls else t)
    out.append("</tspan>")
    return "".join(out)


def render(theme, art, rows):
    c = THEMES[theme]
    height = TOP + (len(rows) - 1) * LINE_H + 20
    art_w = max(len(l) for l in art)
    width = round(INFO_X + INFO_COLS * CHAR_W + PAD)
    art_top = TOP + ((len(rows) - len(art)) // 2) * LINE_H
    art_x = round(PAD + (INFO_X - 2 * PAD - art_w * CHAR_W) / 2)

    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" '
        f'width="{width}px" height="{height}px" font-size="16px">',
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
        " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        f".key {{fill: {c['key']};}} .value {{fill: {c['value']};}} .cc {{fill: {c['cc']};}}",
        "text, tspan {white-space: pre;}",
        "</style>",
        f'<rect width="{width}px" height="{height}px" fill="{c["bg"]}" rx="15"/>',
        f'<text x="{art_x}" y="{art_top}" fill="{c["text"]}" class="ascii">',
    ]
    for i, l in enumerate(art):
        lines.append(tspans(art_x, art_top + i * LINE_H, [(None, l)]))
    lines.append("</text>")
    lines.append(f'<text x="{INFO_X}" y="{TOP}" fill="{c["text"]}">')
    for i, segs in enumerate(rows):
        if segs:
            lines.append(tspans(INFO_X, TOP + i * LINE_H, segs))
    lines.append("</text>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date()  # Türkiye time
    art = (ROOT / "art" / "kedy.txt").read_text(encoding="utf-8").rstrip("\n").split("\n")
    rows = info_rows(today, load_stats())
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, art, rows), encoding="utf-8")
    print("built", today)


if __name__ == "__main__":
    main()
