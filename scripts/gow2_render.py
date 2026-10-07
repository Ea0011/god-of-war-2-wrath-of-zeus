#!/usr/bin/env python3
"""
gow2_render.py - render creature pictures for the report by driving god_of_war_browser's WebGL
viewer headlessly (Playwright + Chromium). Pictures land in report/renders/creatures/<Creature>.png
and are picked up by gow2_report.py automatically.

  cache/venv/bin/python scripts/gow2_render.py [--only Medusa00 Satyr10] [--force] [--size 900]

Requires: the browser on http://localhost:8000 (scripts/start_swap_ui.sh or bin/god_of_war_browser),
cache/index.json, and `cache/venv/bin/pip install playwright && cache/venv/bin/playwright install chromium`.
"""
import argparse, asyncio, json, math, os, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
B = 'http://localhost:8000'
# recorded vertex extents: injected into RenderMesh's constructor (positions are flat xyz triples)
INJECT = """
        if(!window.__bbox)window.__bbox=[Infinity,Infinity,Infinity,-Infinity,-Infinity,-Infinity];
        if(vertexArray&&vertexArray.length%3===0){const b=window.__bbox;for(let i=0;i+2<vertexArray.length;i+=3){const x=vertexArray[i],y=vertexArray[i+1],z=vertexArray[i+2];if(x<b[0])b[0]=x;if(y<b[1])b[1]=y;if(z<b[2])b[2]=z;if(x>b[3])b[3]=x;if(y>b[4])b[4]=y;if(z>b[5])b[5]=z;}window.__meshes=(window.__meshes||0)+1;}
"""


def model_tag(wad, creature):
    """Prefer the creature's object node (unnamed tag right after go<creature>: skeleton + model,
    renders assembled); fall back to the first model header tag."""
    t = json.load(urllib.request.urlopen(f'{B}/json/pack/{wad}', timeout=120))['Tags']
    go = [x for x in t if x['Tag'] == 1 and x['Name'].lower() == 'go' + creature.lower()]
    if go:
        after = [x for x in t if go[0]['Id'] < x['Id'] <= go[0]['Id'] + 6 and x['Tag'] == 1 and x['Name'] == '' and x['Size'] > 500]
        if after:
            return after[0]['Id']
    mdl = [x for x in t if x['Tag'] == 1 and x['Name'].startswith('MDL_') and x['Size'] == 88]
    return mdl[0]['Id'] if mdl else None


async def render_all(jobs, out_dir, size, rotation):
    import io, math
    from PIL import Image
    from playwright.async_api import async_playwright
    FOV = 55.0
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        page = await browser.new_page(viewport={'width': size + 640, 'height': size + 100})

        async def patch_renderer(route):
            resp = await route.fetch()
            body = await resp.text()
            body = body.replace('this.indexesCount = indexArray.length;', 'this.indexesCount = indexArray.length;' + INJECT, 1)
            body = body.replace('new ObjectTreeNodeModel("pivot", RenderHelper.Pivot()),', '')     # no axis helper in pictures
            await route.fulfill(response=resp, body=body, headers={**resp.headers, 'cache-control': 'no-store'})
        await page.route('**/static/js/Renderer.js', patch_renderer)

        async def set_cam(target, dist, rot):
            await page.evaluate(f"""() => {{ const c = gr_instance.cameraModels; c.setTarget([{target[0]},{target[1]},{target[2]}]); c.distance = {dist}; c.rotation = [{rot[0]},{rot[1]},0]; gr_instance.requestRedraw(); }}""")
            await page.wait_for_timeout(450)

        async def measure(canvas):
            """pixel bbox of everything that is not the flat grey background -> (x0,y0,x1,y1,W,H) or None"""
            png = await canvas.screenshot()
            im = Image.open(io.BytesIO(png)).convert('RGB')
            W, H = im.size
            bg = im.getpixel((2, H - 3))
            px = im.load(); xs, ys = [], []
            for y in range(0, H, 2):
                for x in range(0, W, 2):
                    r, g, b = px[x, y]
                    if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 40:
                        xs.append(x); ys.append(y)
            if len(xs) < 6:
                return None
            return min(xs), min(ys), max(xs), max(ys), W, H

        done = 0
        for creature, wad, tag in jobs:
            out = os.path.join(out_dir, creature + '.png')
            await page.goto('about:blank')
            await page.goto(f'{B}/#/{wad}/{tag}', wait_until='networkidle')
            await page.add_style_tag(content='.view-3d-helpers{display:none!important}')   # keep the overlay out of the pixels
            await page.evaluate("""() => { for (const id of ['show-skeleton-ids','show-skeleton','show-collision','show-collision-static','show-collision-dbg','show-light']) {
                const el = document.querySelector('#view-3d-config input#'+id); if (el && el.checked) { el.checked = false; el.dispatchEvent(new Event('change', {bubbles:true})); } } }""")
            last, stable = None, 0
            for _ in range(80):                      # meshes keep arriving after networkidle; wait until the count settles
                await page.wait_for_timeout(500)
                cur = await page.evaluate('window.__meshes||0')
                stable = stable + 1 if (cur and cur == last) else 0
                last = cur
                if stable >= 4:
                    break
            canvas = await page.query_selector('#view-3d canvas')
            # pass 1/2: axis-aligned views give world X,Y (yaw 0) and Z,Y (yaw 90) extents from pixels
            target, dist = [0.0, 0.0, 0.0], 300.0
            ext = None
            for it in range(12):
                boxes = {}
                for yaw in (0, 90):
                    await set_cam(target, dist, (0, yaw))
                    m = await measure(canvas)
                    if m is None:
                        break
                    boxes[yaw] = m
                touching = any(m[0] <= 2 or m[1] <= 2 or m[2] >= m[4] - 3 or m[3] >= m[5] - 3 for m in boxes.values())
                if len(boxes) < 2 or touching:
                    dist *= 2.5                       # too close (model fills/exceeds the frame) or too small to see: back off
                    if dist > 300000:
                        break
                    continue
                def world(m, yaw):
                    x0, y0, x1, y1, W, H = m
                    k = 2 * dist * math.tan(math.radians(FOV / 2)) / H
                    cxp, cyp = (x0 + x1) / 2 - W / 2, H / 2 - (y0 + y1) / 2
                    return cxp * k, cyp * k, (x1 - x0) * k, (y1 - y0) * k
                ax, ay, aw, ah = world(boxes[0], 0)      # screen-right = +X
                bz, by, bw, bh = world(boxes[90], 90)    # screen-right = +Z
                target = [target[0] + ax, target[1] + (ay + by) / 2, target[2] + bz]
                ext = max(aw, bw, ah, bh)
                dist = (ext / 2) / math.tan(math.radians(FOV / 2)) * 1.6 + 1.0
            if ext is None:
                print(f'{creature}: nothing visible ({wad} tag {tag})'); continue
            # final 3/4 view, framed a bit tighter
            await set_cam(target, (ext / 2) / math.tan(math.radians(FOV / 2)) * 1.25 + 1.0, rotation)
            await page.wait_for_timeout(600)
            await canvas.screenshot(path=out)
            done += 1
            print(f'{creature}: ok  extent {ext:.0f}  meshes {last}  -> {os.path.relpath(out, ROOT)}')
        await browser.close()
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='*'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--size', type=int, default=900); ap.add_argument('--rotation', nargs=2, type=float, default=[12, 215], help='pitch yaw (models face -Z, so ~215 is a front 3/4 view)')
    ap.add_argument('--out', default=os.path.join(ROOT, 'report', 'renders', 'creatures'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    idx = json.load(open(os.path.join(ROOT, 'cache', 'index.json')))
    jobs = []
    for c, v in sorted(idx['creatures'].items(), key=lambda x: x[0].lower()):
        if a.only and c not in a.only:
            continue
        if not v.get('wad'):
            continue
        if not a.force and os.path.exists(os.path.join(a.out, c + '.png')):
            continue
        tag = model_tag(v['wad'], c)
        if tag is None:
            print(f'{c}: no model tag in {v["wad"]}'); continue
        jobs.append((c, v['wad'], tag))
    print(f'{len(jobs)} creatures to render')
    n = asyncio.run(render_all(jobs, a.out, a.size, a.rotation))
    print(f'rendered {n}')


if __name__ == '__main__':
    main()
