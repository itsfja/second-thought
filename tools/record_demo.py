#!/usr/bin/env python3
"""Record screenshots/demo.gif and screenshots/editor.png: the Review loop example running, then the export panel.

It drives the real page in the test suite's headless browser, so run tests/setup.sh once first. Claude's
replies are scripted below (nothing calls a real model), so the run looks the same every time.
Needs ffmpeg on the PATH for the GIF.

    python tools/record_demo.py
"""
import asyncio
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
sys.path.insert(0, str(ROOT / "tests"))
import run_tests as T  # noqa: E402  the test suite's page, CDN stand-ins and route()

# Stand-ins for the page's runtime capabilities, with believable replies streamed word by word.
MOCK = r"""(function(){
const sleep = ms => new Promise(r => setTimeout(r, ms));
const DRAFTS = [
  "Autolyse is a rest you give flour and water before the salt and starter go in. The flour hydrates, enzymes start breaking down starch and protein, and gluten begins to form on its own. Rest 30–60 minutes.",
  "Autolyse is a rest you give flour and water before adding the salt and starter.\n\nWhat it is: during the rest the flour soaks up the water, and natural enzymes start loosening the gluten, so it forms on its own with no kneading.\n\nWhy bakers use it: the dough becomes smoother and stretchier, it's easier to shape, and the crumb comes out more open.\n\nHow long: 30 to 60 minutes for white flour. Wholemeal can take up to 2 hours, because the bran is slower to absorb water."];
let drafts = 0, reviews = 0;
const stream = async (t, o) => { let s = ""; for (const w of t.split(/(?<= )/)) { s += w; o.onText && o.onText({ text:s, delta:w }); await sleep(35); }
  return { text:t, truncated:false }; };
window.claude = { use: async n => {
  if (n === 'db') { const c = { limit(){ return c; }, onSnapshot(fn){ setTimeout(() => fn({ docs:[], size:0, empty:true, docChanges:() => [], metadata:{} }), 10); return () => {}; },
                               doc(){ return { set:async () => {}, delete:async () => {} }; } }; return { collection:() => c }; }
  if (n === 'user') return { id:async () => 'demo' };
  if (n === 'downloads') return { save:async () => ({ status:'saved' }) };
  if (n !== 'sample') return null;
  const f = async (input, o = {}) => { await sleep(500); return stream(DRAFTS[Math.min(drafts++, 1)], o); };
  f.json = async () => { await sleep(1100); reviews++;
    return reviews === 1 ? { approved:false, problems:["Doesn't say why bakers use it", "Jargon: 'enzymes' and 'gluten' aren't explained for a beginner"] }
                         : { approved:true, problems:[] }; };
  f.limits = async () => ({ maxPromptBytes:262144, images:{ maxCount:5, maxInputBytes:20000000, mediaTypes:['image/png'] } });
  return f; } };
})();"""


async def record(frames: pathlib.Path):
    from playwright.async_api import async_playwright
    n = 0

    async def shot(pg, hold=1):
        nonlocal n
        await pg.evaluate("window.scrollTo(0, 0)")
        for _ in range(hold):
            await pg.screenshot(path=str(frames / f"{n:04d}.png"))
            n += 1

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1280, "height": 720})
        await pg.route("**/*", T.route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=str(OUT / "editor.png"))
        await shot(pg, 6)
        await pg.hover("#run")
        await shot(pg, 2)
        await pg.click("#run")
        for _ in range(160):
            await pg.wait_for_timeout(250)
            await shot(pg)
            if n > 20 and await pg.is_disabled("#stop"):
                break
        await shot(pg, 10)
        await pg.hover("text=Import / export")
        await shot(pg, 3)
        await pg.click("text=Import / export")
        await pg.wait_for_timeout(600)
        await shot(pg, 4)
        await pg.hover("text=Save Python (.zip)")
        await shot(pg, 14)
        await browser.close()


def main() -> int:
    if not (T.VENDOR / "blockly").exists():
        sys.exit("Run tests/setup.sh first.")
    if not shutil.which("ffmpeg"):
        sys.exit("This needs ffmpeg on the PATH to make the GIF.")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = pathlib.Path(tmp)
        asyncio.run(record(frames))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "4", "-i", str(frames / "%04d.png"), "-vf",
                        "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                        "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", str(OUT / "demo.gif")], check=True)
    print(f"Wrote {OUT / 'demo.gif'} and {OUT / 'editor.png'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
