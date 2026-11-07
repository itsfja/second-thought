#!/usr/bin/env python3
"""Make the pictures in README.md and docs/ (#345), so they can be made again whenever the page changes:

  screenshots/examples.png       the Examples browser
  screenshots/agent-run.png      an agent checking the sample house, its steps in the run log
  screenshots/export.png         the Import / export panel
  screenshots/home-assistant.png the sample house the Home Assistant blocks use on the page
  screenshots/terminal-run.png   an exported program running in a terminal
  screenshots/terminal-doctor.png  --doctor checking one
  screenshots/review-loop.svg    draft, review, revise, as a diagram
  screenshots/settings-layers.svg  where settings come from, as a diagram

It drives the real page in the test suite's headless browser, so run tests/setup.sh once first. Claude's replies are
scripted below (nothing calls a real model), so the pictures come out the same every time. The terminal pictures
are drawn from text below, in the shape exported programs print. The diagrams need mmdc (Mermaid's command line).

    python tools/record_docs.py
"""
import asyncio
import html
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
sys.path.insert(0, str(ROOT / "tests"))
import run_tests as T  # noqa: E402  the test suite's page, CDN stand-ins and route()

# Stand-ins for the page's runtime capabilities: an agent that follows window.__agentScript a step at a time, and a
# plain answer for anything else.
MOCK = r"""(function(){
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.claude = { use: async n => {
  if (n === 'db') { const c = { limit(){ return c; }, onSnapshot(fn){ setTimeout(() => fn({ docs:[], size:0, empty:true, docChanges:() => [], metadata:{} }), 10); return () => {}; },
                               doc(){ return { set:async () => {}, delete:async () => {} }; } }; return { collection:() => c }; }
  if (n === 'user') return { id:async () => 'docs' };
  if (n === 'downloads') return { save:async () => ({ status:'saved' }) };
  if (n !== 'sample') return null;
  const last = input => Array.isArray(input) ? input[input.length - 1].content : input;
  const f = async (input, o = {}) => { await sleep(200); const t = window.__text || 'Done.'; o.onText && o.onText({ text:t, delta:t }); return { text:t, truncated:false }; };
  f.json = async input => { await sleep(250); const p = last(input);
    if (p.includes('one step at a time, using tools') && window.__agentScript) {
      const steps = (p.match(/\nStep \d+: /g) || []).length;
      return JSON.parse(JSON.stringify(window.__agentScript[Math.min(steps, window.__agentScript.length - 1)])); }
    if (p.includes('"approved"')) return { approved:true, problems:[] };
    return {}; };
  f.limits = async () => ({ maxPromptBytes:262144, images:{ maxCount:5, maxInputBytes:20000000, mediaTypes:['image/png'] } });
  return f; } };
})();"""

HOUSE_CHECK = [
    {"tool": "find_devices", "input": {"search": "door"}, "why": "Doors and windows first.",
     "plan": ["Look for open doors and windows", "Check battery levels", "Look at temperatures over the last day", "List what needs attention"]},
    {"tool": "find_devices", "input": {"search": "battery"}, "why": "Then batteries below 20%."},
    {"tool": "device_history", "input": {"entity": "sensor.freezer_temperature", "hours": 24}, "why": "The freezer is the one that matters if it drifts."},
    {"done": True, "answer": "Needs attention, most urgent first:\n\n1. The back door and the kitchen window are open.\n"
                             "2. The kitchen leak sensor's battery is at 9%, the hallway motion sensor's at 14% and the back door "
                             "sensor's at 18%.\n3. The shed door sensor is unavailable.\n\nThe freezer held at about -17.5 °C all day."},
]

# For the terminal pictures, in exactly the shape exported programs print: a review-loop run (its numbers made up),
# and --doctor as a real wallet program printed it (paths changed).
RUN = """C:\\Users\\you\\review-loop>run.bat

=== Run · 09:14 ===

▸ Task set  [set]
    Explain what autolyse is in sourdough baking, for a home baker's reference page.

▸ Write a first draft  [done]
    Autolyse is a rest you give flour and water before the salt and starter go in…
    · Claude, balanced (standard) · 6.8 s · 412 in, 286 out

▸ Review  [needs work]
    - Doesn't say why bakers use it.
    - Jargon: 'enzymes' and 'gluten' aren't explained for a beginner.
    · Claude, quick (budget) · 2.1 s · 655 in, 61 out

▸ Revise to fix the problems  [revised]
    Autolyse is a rest you give flour and water before adding the salt and starter…
    · Claude, balanced (standard) · 7.4 s · 1,020 in, 341 out

▸ Review  [approved]
    · Claude, quick (budget) · 1.9 s · 702 in, 12 out

============================================================
RESULT
============================================================
Autolyse is a rest you give flour and water before adding the salt and starter…

Done · 4 model calls · Claude: 2,789 tokens in, 700 out · about £0.01 at list prices
"""
DOCTOR = """C:\\Users\\you\\wallet-health-check>python wallet-health-check.py --doctor

Checking wallet-health-check.py (runtime 3.11.0, Python 3.14.6).
Only reading: nothing is sent, posted, switched or charged.

  ok    Python: 3.14.6
  ok    Currency: GBP, at the ECB rate of 2026-11-06 (1 US dollar = £0.75)
  ok    Runtime: 3.11.0 is the latest
  ok    Settings: read C:\\Users\\you\\second-thought.ini + C:\\Users\\you\\wallet-health-check\\second-thought.ini
  ok    Keys: ANTHROPIC_API_KEY (C:\\Users\\you\\second-thought.ini), EMAIL_PASSWORD (the keychain)
  ok    Package anthropic: 2.3.0
  ok    Claude: the key works (14 models)
  ok    Email (sending): signed in to smtp.gmail.com (nothing was sent)
  ok    MCP server “trustwallet”: 61 tools, MCP 2025-06-18 · 26 of them can change things
  NOTE  First run: not allowed on this computer yet. Run it once yourself and answer y (a scheduled run won't start until then).

Everything checked is ready. 1 note above.
"""
TERMINAL = """<!doctype html><html><head><meta charset=utf-8><style>
body{margin:0;background:transparent;font-family:system-ui,sans-serif}
.win{width:980px;border-radius:10px;overflow:hidden;box-shadow:0 10px 30px rgba(27,30,43,.18);border:1px solid #2a2d3a}
.bar{background:#2a2d3a;color:#c9cbd6;font-size:13px;padding:8px 14px}
pre{margin:0;background:#16181f;color:#e6e7ee;font:14px/1.45 'Cascadia Mono',Consolas,'DejaVu Sans Mono',monospace;padding:16px 18px;white-space:pre-wrap}
.ok{color:#6fd08c}.note{color:#e6c46a}.fail{color:#f07a7a}.dim{color:#8b8fa3}.head{color:#9db4ff;font-weight:600}
</style></head><body><div class=win><div class=bar>{title}</div><pre>{body}</pre></div></body></html>"""


def colour(text):
    out = []
    for line in html.escape(text).split("\n"):
        s = line.strip()
        if s.startswith("ok "):
            line = line.replace("ok ", '<span class=ok>ok</span> ', 1)
        elif s.startswith("NOTE"):
            line = line.replace("NOTE", "<span class=note>NOTE</span>", 1)
        elif s.startswith("FAIL"):
            line = line.replace("FAIL", "<span class=fail>FAIL</span>", 1)
        elif s.startswith("▸") or s.startswith("==="):
            line = f"<span class=head>{line}</span>"
        elif s.startswith("·"):
            line = f"<span class=dim>{line}</span>"
        out.append(line)
    return "\n".join(out)


DIAGRAMS = {
    "review-loop": """flowchart LR
    T["set task"] --> D["write a first draft"]
    D --> R{"review against<br/>your rules"}
    R -- "problems" --> V["revise to fix them"]
    V --> R
    R -- "approved,<br/>or out of rounds:<br/>the best draft" --> F["finish and show<br/>the result"]
    classDef task fill:#4C7EF3,stroke:#3a63c4,color:#fff
    classDef draft fill:#4C7EF3,stroke:#3a63c4,color:#fff
    classDef review fill:#8A55D7,stroke:#6b3fb0,color:#fff
    classDef finish fill:#2E9E5B,stroke:#237a46,color:#fff
    class T,D,V draft
    class R review
    class F finish""",
    "settings-layers": """flowchart TB
    E["Ordinary environment variables<br/><code>ANTHROPIC_API_KEY</code>, <code>RB_BUDGET</code><br/><i>win over everything</i>"]
    P["3. The program's own second-thought.ini<br/><i>what's particular to it</i>"]
    H["2. second-thought.ini in your home folder<br/><i>email, keys, currency your programs share</i>"]
    S["1. ST_ variables<br/><code>ST_EMAIL_ADDRESS</code>, <code>ST_CURRENCY</code><br/><i>every program on the computer</i>"]
    K["The keychain<br/><i>fills in any key still missing</i>"]
    E -- "over" --> P -- "over" --> H -- "over" --> S -- "then" --> K
    classDef top fill:#2F4BDB,stroke:#24399f,color:#fff
    classDef layer fill:#EEF1FD,stroke:#9aa8e8,color:#1B1E2B
    classDef keys fill:#F3F4F8,stroke:#c3c7d6,color:#1B1E2B
    class E top
    class P,H,S layer
    class K keys""",
}


async def page_shots():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1280, "height": 1300}, device_scale_factor=1)
        await pg.route("**/*", T.route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        for name, toggle in (("examples", "#ex-toggle"), ("export", "#io-toggle"), ("home-assistant", "#ha-toggle")):
            await pg.click(toggle)
            await pg.wait_for_timeout(700)
            panel = await pg.evaluate_handle(f"""() => {{ const b = document.querySelector('{toggle}');
                const id = b.getAttribute('aria-controls'); if (id) return document.getElementById(id);
                return [...document.querySelectorAll('section, .panel, details, div')].find(e => e.offsetParent && e.getBoundingClientRect().top > 260
                    && e.getBoundingClientRect().width > 1000 && e.getBoundingClientRect().height > 200); }}""")
            box = await panel.as_element().bounding_box()
            clip = {"x": 0, "y": 0, "width": 1280, "height": min(box["y"] + box["height"] + 16, 820 if name == "examples" else 900)}
            await pg.screenshot(path=str(OUT / f"{name}.png"), clip=clip)
            await pg.click(toggle)
            await pg.wait_for_timeout(300)
        await pg.select_option("#example", "a_house")
        await pg.click("#load")
        await pg.wait_for_timeout(800)
        await pg.evaluate("s => { window.__agentScript = s; window.__text = 'The house is fine apart from the back door and one battery.'; }", HOUSE_CHECK)
        await pg.click("#run")
        for _ in range(120):
            await pg.wait_for_timeout(250)
            if await pg.is_enabled("#run"):
                break
        # The run log's last two entries: the agent's answer and its summary (each tool, what went in, what came back).
        await pg.evaluate("""() => document.querySelectorAll('#steps details').forEach(d => d.open = false)""")
        steps = await pg.query_selector_all("#steps > .step")
        box_a, box_b = await steps[-2].bounding_box(), await steps[-1].bounding_box()
        await steps[-2].scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        box_a, box_b = await steps[-2].bounding_box(), await steps[-1].bounding_box()
        await pg.screenshot(path=str(OUT / "agent-run.png"), clip={"x": box_a["x"] - 8, "y": box_a["y"] - 8, "width": box_a["width"] + 16,
                                                                "height": box_b["y"] + box_b["height"] - box_a["y"] + 16})
        for name, title, text in (("terminal-run", "Command Prompt - run.bat", RUN), ("terminal-doctor", "Command Prompt", DOCTOR)):
            await pg.set_content(TERMINAL.replace("{title}", title).replace("{body}", colour(text)))
            await (await pg.query_selector(".win")).screenshot(path=str(OUT / f"{name}.png"), omit_background=True)
        await browser.close()


def diagrams():
    mmdc = shutil.which("mmdc")
    if not mmdc:
        print("mmdc isn't installed, so the diagrams weren't made (npm install -g @mermaid-js/mermaid-cli).")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for name, src in DIAGRAMS.items():
            path = pathlib.Path(tmp, name + ".mmd")
            path.write_text(src, encoding="utf-8")
            subprocess.run([mmdc, "-i", str(path), "-o", str(OUT / f"{name}.svg"), "-b", "transparent"], check=True, capture_output=True)


def shrink():
    """Keep the PNGs small: as few colours as look right, if pngquant is installed."""
    tool = shutil.which("pngquant")
    for png in ("examples", "export", "home-assistant", "agent-run", "terminal-run", "terminal-doctor"):
        if tool:
            subprocess.run([tool, "--force", "--skip-if-larger", "--quality", "70-95", "--output", str(OUT / f"{png}.png"), str(OUT / f"{png}.png")], check=False)
        print(f"screenshots/{png}.png  {(OUT / f'{png}.png').stat().st_size // 1024} KB")


if __name__ == "__main__":
    if not (T.VENDOR / "blockly").exists():
        sys.exit("Run tests/setup.sh first.")
    asyncio.run(page_shots())
    diagrams()
    shrink()
