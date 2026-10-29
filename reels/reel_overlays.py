"""Rend les calques texte (PNG transparents 1080x1920) et les cartes plein écran des reels."""
import sys, json, asyncio
from playwright.async_api import async_playwright
sys.path.insert(0, '/home/claude/build')
from lib import CSS

LOGO = 'file:///home/claude/rs-automation-brewfactory/assets/logo-brewfactory.png'
LOGO_W = 'file:///home/claude/rs-automation-brewfactory/assets/logo-brewfactory-blanc.png'

BASE = CSS + """
html,body{background:transparent !important;margin:0}
.f{width:1080px;height:1920px;position:relative;overflow:hidden}
.cap{position:absolute;left:70px;right:70px;top:1180px;display:flex;flex-direction:column;align-items:center;gap:16px}
.tag{background:var(--yellow);color:var(--brown);font:800 30px/1 'Hanken';letter-spacing:3px;text-transform:uppercase;padding:14px 22px;border-radius:10px}
.box{background:var(--bg);color:var(--brown);font:700 60px/1.08 'Bodoni';padding:22px 34px 26px;border-radius:18px;text-align:center;box-shadow:0 12px 30px rgba(0,0,0,.25)}
.box .acc{color:var(--yellow)}
.wm{position:absolute;top:110px;left:56px;width:250px;background:var(--bg);padding:12px 18px;border-radius:14px;box-shadow:0 6px 18px rgba(0,0,0,.2)}
.title{position:absolute;left:60px;right:60px;top:300px;text-align:center}
.title .box{font-size:84px;display:inline-block}
"""

def caption(tag, text, title=None):
    t = f'<div class="title"><div class="box">{title}</div></div>' if title else ''
    tg = f'<div class="tag">{tag}</div>' if tag else ''
    bx = f'<div class="box">{text}</div>' if text else ''
    return f'<div class="f"><img class="wm" src="{LOGO}">{t}<div class="cap">{tg}{bx}</div></div>'

def card_end(line1, line2, sub):
    wave = '<svg style="position:absolute;left:0;bottom:0" width="1080" height="420" viewBox="0 0 1080 300" preserveAspectRatio="none"><path d="M0 170 C260 90 460 230 700 150 C860 95 980 120 1080 90 V300 H0z" fill="var(--orange)"/><path d="M0 235 C300 170 520 290 780 220 C920 185 1010 200 1080 190 V300 H0z" fill="var(--peach)"/></svg>'
    return f'''<div class="f" style="background:var(--bg)">
<img src="{LOGO}" style="position:absolute;top:470px;left:50%;transform:translateX(-50%);width:620px">
<h1 style="position:absolute;top:760px;left:0;right:0;text-align:center;font-size:104px">{line1}<br><span class="acc">{line2}</span></h1>
<div class="rule" style="position:absolute;top:1030px;left:465px"></div>
<p style="position:absolute;top:1080px;left:120px;right:120px;text-align:center;font-size:40px">{sub}</p>
<div style="position:absolute;top:1260px;left:0;right:0;text-align:center"><span class="pill" style="font-size:38px;padding:18px 34px">brewfactory.fr</span></div>
{wave}</div>'''

async def render(items, outdir):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        for name, html in items:
            tmp = f'{outdir}/{name}.html'
            open(tmp, 'w').write(f'<!doctype html><html><head><meta charset="utf-8"><style>{BASE}</style></head><body>{html}</body></html>')
            await pg.goto('file://' + tmp)
            await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(250)
            await pg.screenshot(path=f'{outdir}/{name}.png', omit_background=True)
        await b.close()

if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    items = []
    for s in spec['segments']:
        if s['kind'] == 'end':
            items.append((s['name'], card_end(*s['end'])))
        else:
            items.append((s['name'], caption(s.get('tag'), s.get('text'), s.get('title'))))
    asyncio.run(render(items, sys.argv[2]))
