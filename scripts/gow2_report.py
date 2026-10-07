#!/usr/bin/env python3
"""
gow2_report.py - build the shareable "Enemy layout" report (HTML + PDF) from the cached level WADs.

  python3 scripts/gow2_report.py                 # -> report/gow2_enemy_layout.html (+ .pdf if Chrome found)
  python3 scripts/gow2_report.py --levels RHOD10 RHOD20 --no-pdf

Inputs: cache/wads/*.WAD (shipped copies, backups/<L>.WAD.orig preferred), cache/index.json,
optional pictures renders/creatures/<Creature>.png and renders/levels/<LEVEL>.png.
The HTML is self-contained except for those pictures; it has a proposal form whose "Export
proposals" button downloads JSON in the swap tool's plan format ({level: plan}).
"""
import argparse, base64, html, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gow2_enemy_swap as G

FAMILY_ORDER = ['RHOD', 'PEGA', 'ISLE', 'BOG', 'ATLAS', 'PAL', 'SPIR', 'ZEUS', 'CMBT', 'FREE']
TYPE_NAMES = {0: 'sensor', 2: 'creation sensor', 3: 'destruction sensor', 4: 'zone/trigger', 5: 'animation', 6: 'visibility',
              7: 'event', 9: 'spawner', 10: 'chest', 12: 'level data', 13: 'marker'}
BRA_WORDS = {'BRA_Spawn': 'drops in', 'BRA_SpawnJump': 'jumps in', 'BRA_SpawnCeiling': 'from the ceiling', 'BRA_SpawnWall': 'from a wall',
             'BRA_SpawnDive': 'dives in', 'BRA_SpawnFall': 'falls in', 'BRA_SpawnBogRope': 'bog rope', 'BRA_SpawnJumpWater': 'jumps from water',
             'BRA_RhodesSpawn': 'Rhodes entrance', 'BRA_SpawnBog80': 'bog spawn'}


def level_sort_key(name):
    m = re.match(r'([A-Z]+)(\d+)', name)
    fam, num = (m.group(1), int(m.group(2))) if m else (name, 0)
    return (FAMILY_ORDER.index(fam) if fam in FAMILY_ORDER else 99, num)


def level_path(code):
    bk = os.path.join(ROOT, 'backups', code + '.WAD.orig')
    return bk if os.path.exists(bk) else os.path.join(ROOT, 'cache', 'wads', code + '.WAD')


def entity_graph(tags):
    """uid -> name/type, and for every entity the list of entities that target it."""
    uid, refby, targets = {}, {}, {}
    for ti, t in enumerate(tags):
        if not G.is_entities_script(t):
            continue
        for e in G.iter_entities(t.data):
            name = G.entity_strings(e)[0]
            hc, tc = G.u16(e, 0x4E), G.u16(e, 0x50)
            tg = [G.u16(e, 0x54 + hc * 4 + 2 * k) for k in range(tc)]
            uid[G.u16(e, 0x48)] = (name, G.u16(e, 0x46))
            targets[name] = tg
    for src, tg in targets.items():
        for u in tg:
            if u in uid:
                refby.setdefault(uid[u][0], []).append(src)
    return uid, refby


def classify(creature, idx):
    c = idx['creatures'].get(creature) or next((v for k, v in idx['creatures'].items() if k.lower() == creature.lower()), {})
    blocks = (c.get('donors') or {}).values()
    combat = any(any(n == 'hfsmEnemy1' for h, k, n in b['mem']) for b in blocks)
    return ('combat' if combat else 'other'), c


def build_level(code, idx, img_dir):
    tags = G.read_wad(level_path(code))
    info = G.level_info(tags)
    uid, refby = entity_graph(tags)
    # per-creature spawn totals
    totals = {}
    for enc in info['encounters']:
        for e in enc['entities']:
            totals[e['crt']] = totals.get(e['crt'], 0) + (e['count'] if e['count'] is not None else 1)
    gates = [g for g in info['gates'] if g['role'] in ('threshold', 'counter')]
    report = {g['var']: g for g in info['gate_report']}
    return dict(code=code, info=info, totals=totals, refby=refby, uid=uid, gates=gates, report=report,
                img=os.path.join(img_dir, 'levels', code + '.png'))


def esc(s):
    return html.escape(str(s))


def render(levels, idx, out_html, img_dir, title):
    creatures_all = sorted({c for L in levels for c in L['info']['rsrcs']} | {e['crt'] for L in levels for enc in L['info']['encounters'] for e in enc['entities']})
    cinfo = {c: classify(c, idx) for c in creatures_all}
    sizes = {c: (cinfo[c][1].get('bytes') or 0) for c in creatures_all}
    all_opts = ''.join(f'<option value="{esc(c)}">' for c in ['remove'] + sorted(idx['creatures'], key=str.lower))
    css = """
:root{--bg:#fbf8f1;--fg:#1d1a16;--mut:#6a6358;--line:#d8d0c0;--card:#fff;--acc:#8d1d1d;--yl:#fff3b0;--gate:#e5f0ff;--other:#f1efe9;--ok:#2d6a3e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.4 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
header.top{padding:28px 36px;border-bottom:3px solid var(--acc)}h1{margin:0 0 6px;font-size:26px}h2{font-size:20px;margin:0 0 4px}h3{font-size:14px;margin:14px 0 6px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.mut{color:var(--mut)}.wrap{padding:0 36px 36px}.level{page-break-before:always;padding-top:24px}
.hdr{display:grid;grid-template-columns:1fr 280px;gap:18px;align-items:start}.hdr img{width:280px;border:1px solid var(--line);border-radius:6px;background:#eee}
table{border-collapse:collapse;width:100%;margin:6px 0 10px}th,td{text-align:left;padding:4px 7px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
tr.scripted td{background:var(--yl)}tr.other td{background:var(--other);color:var(--mut)}td.enc{background:#efe9dc;font-weight:600}
.gate{background:var(--gate);border-left:4px solid #3b6fb6;padding:8px 12px;margin:8px 0;border-radius:4px}.gate b{color:#1d3f6e}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 7px;font-size:11px;margin:1px;background:#fff}
.legend span{margin-right:14px}.sw{display:inline-block;width:14px;height:12px;vertical-align:-2px;border:1px solid var(--line);margin-right:4px}
.prop input,.prop select{font:inherit;padding:2px 4px;border:1px solid #bbb;border-radius:3px;background:#fff}.prop input[type=number]{width:52px}.prop select{max-width:150px}
.toolbar{position:sticky;top:0;background:var(--bg);padding:8px 36px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;z-index:2}
button{font:inherit;padding:5px 10px;border:1px solid #999;border-radius:5px;background:#fff;cursor:pointer}
.best{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:10px;page-break-inside:avoid}.card img{width:100%;aspect-ratio:1;object-fit:contain;background:#eee;border-radius:4px}
.toc{columns:3;font-size:12px}.toc a{text-decoration:none;color:var(--fg)}
@media print{.toolbar,.noprint{display:none}body{background:#fff}.prop input{border:1px solid #999;background:#fff;color:#000}.prop input::placeholder{color:transparent}a{color:inherit}.level{page-break-before:always}tr{page-break-inside:avoid}}
"""
    js = """
const PLAN={};
function key(level,tag,name){return level+'|'+tag+':'+name}
const NAMES=[...document.querySelectorAll('#creatures option')].map(o=>o.value);
function onAssign(sel){const [lvl,k]=sel.dataset.k.split('|');const p=PLAN[lvl]=PLAN[lvl]||{assign:{},remove:[],spawns:{},counts:{}};p.remove=p.remove.filter(x=>x!==k);delete p.assign[k];
 let v=sel.value.trim();if(v){const m=NAMES.find(n=>n.toLowerCase()===v.toLowerCase());if(!m){sel.style.borderColor='red';sel.title='unknown creature';return;}v=m;sel.value=m;}sel.style.borderColor='';sel.title='';
 if(v==='remove')p.remove.push(k);else if(v&&v!==sel.dataset.orig)p.assign[k]=v;sel.style.background=(v&&v!==sel.dataset.orig)?'#fde7e7':'#fff';}
function onSpawn(inp){const [lvl,k]=inp.dataset.k.split('|');const p=PLAN[lvl]=PLAN[lvl]||{assign:{},remove:[],spawns:{},counts:{}};const f=inp.dataset.f;const v=inp.value===''?null:+inp.value;p.spawns[k]=p.spawns[k]||{};if(v===null||v===+inp.dataset.orig)delete p.spawns[k][f];else p.spawns[k][f]=v;if(!Object.keys(p.spawns[k]).length)delete p.spawns[k];}
function onCount(inp){const lvl=inp.dataset.l,c=inp.dataset.c;const p=PLAN[lvl]=PLAN[lvl]||{assign:{},remove:[],spawns:{},counts:{}};if(inp.value===''||+inp.value===+inp.dataset.orig)delete p.counts[c];else p.counts[c]=+inp.value;}
function exportPlan(){const out={};for(const [l,p] of Object.entries(PLAN)){if(Object.keys(p.assign).length+p.remove.length+Object.keys(p.spawns).length+Object.keys(p.counts).length)out[l+'.WAD']=Object.assign({auto_total:true},p);}
 const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='gow2_proposals.json';a.click();}
function clearPlan(){for(const k in PLAN)delete PLAN[k];document.querySelectorAll('.prop input').forEach(i=>{i.value='';i.style.background='#fff'});}
"""
    H = []
    H.append(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{css}</style></head><body>')
    H.append('<div class="toolbar noprint"><b>Proposal form</b><span class="mut">pick a replacement creature or "remove", change counts, then</span><button onclick="exportPlan()">Export proposals (JSON)</button><button onclick="clearPlan()">Clear</button><button onclick="window.print()">Print / PDF</button></div>')
    H.append(f'<header class="top"><h1>{esc(title)}</h1><div class="mut">God of War II (PS2) · every spawner in every level, what it spawns and how many · generated from the game files by scripts/gow2_report.py</div>'
             '<div class="legend" style="margin-top:10px"><span><i class="sw" style="background:var(--yl)"></i>scripted entity (cutscene / set piece: change with care)</span>'
             '<span><i class="sw" style="background:var(--other)"></i>non-combat spawner (bodies, civilians, props)</span>'
             '<span><i class="sw" style="background:var(--gate)"></i>progression gate</span></div>'
             '<p class="mut" style="max-width:900px">How to read a row: <b>count</b> is how many enemies the spawner produces over the encounter, <b>alive</b> how many at once; starters without numbers spawn one. '
             '<b>Pool N</b> in the level header is how many of that creature can exist simultaneously anywhere in the level. The memory figures are advisory: the creature WAD payload the level streams; staying near the shipped total is a good first guess, not a proven limit.</p></header>')
    # TOC
    H.append('<div class="wrap"><h3>Levels</h3><div class="toc">' + ''.join(f'<div><a href="#L{esc(L["code"])}">{esc(L["code"])}</a> <span class="mut">{", ".join(esc(c) for c in L["info"]["rsrcs"]) or "no creatures"}</span></div>' for L in levels) + '</div></div>')
    for L in levels:
        info, code = L['info'], L['code']
        shipped_kb = sum(sizes.get(c, 0) for c in info['rsrcs']) // 1024
        H.append(f'<section class="level wrap" id="L{esc(code)}"><div class="hdr"><div><h2>{esc(code)}</h2>')
        H.append('<table><tr><th>creature</th><th>kind</th><th>spawned in level</th><th>pool N (at once)</th><th>WAD</th><th>size</th><th>proposed pool N</th></tr>')
        for c in info['rsrcs']:
            blk = info['creatures'].get(c); kind = cinfo.get(c, ('?', {}))[0]
            H.append(f'<tr class="{"other" if kind=="other" else ""}"><td><b>{esc(c)}</b></td><td>{kind}</td><td>{L["totals"].get(c, 0)}</td><td>{blk["n"] if blk else "<span class=mut>none</span>"}</td><td class="mut">{esc(cinfo[c][1].get("wad",""))}</td><td>{sizes.get(c,0)//1024} KB</td>'
                     f'<td class="prop"><input type="number" min="1" max="64" placeholder="{blk["n"] if blk else ""}" data-l="{esc(code)}" data-c="{esc(c)}" data-orig="{blk["n"] if blk else 0}" onchange="onCount(this)"></td></tr>')
        H.append(f'<tr><th colspan="2">total</th><th>{sum(L["totals"].values())}</th><th></th><th></th><th>{shipped_kb} KB <span class="mut" style="font-weight:400">(advisory)</span></th><th></th></tr></table>')
        # gates
        thr = [g for g in L['gates'] if g['role'] == 'threshold']
        if thr:
            H.append('<div class="gate"><b>Progression gates</b><br>')
            for g in thr:
                rep = L['report'].get(g['var'])
                ctr = next((x for x in L['gates'] if x['var'] in g['compared_with'] and x['role'] == 'counter'), None)
                how = f"kills counted by {len(ctr['incremented_by'])} death sensors" if ctr else ''
                where = ', '.join(g['compared_in'][:3]) + ('…' if len(g['compared_in']) > 3 else '')
                kind = 'TOTAL (must equal exactly)' if rep else 'wave threshold (at least)'
                H.append(f'<div>· <b>{g["init"]} kills</b> — {kind}{"; spawners in this chain produce "+str(rep["spawn_total"]) if rep else ""}. {how}. Checked by <span class="mut">{esc(where)}</span></div>')
            H.append('</div>')
        H.append('</div>')
        H.append(f'<img src="{esc(os.path.relpath(L["img"], os.path.dirname(out_html)))}" alt="" onerror="this.style.display=\'none\'"></div>')
        # encounters
        H.append('<h3>Encounters</h3><table><tr><th>script</th><th>spawner</th><th>creature</th><th>count</th><th>alive</th><th>entrance</th><th>triggered by</th><th>proposed creature</th><th>count / alive</th></tr>')
        for enc in info['encounters']:
            H.append(f'<tr><td class="enc" colspan="9">{esc(enc["script"])} <span class="mut" style="font-weight:400">({len(enc["entities"])} spawners)</span></td></tr>')
            for e in enc['entities']:
                scripted = any(not b.startswith('BRA_Spawn') for b in e['bra'])
                kind = cinfo.get(e['crt'], ('?', {}))[0]
                cls = 'scripted' if scripted else ('other' if kind == 'other' else '')
                bra = ', '.join(BRA_WORDS.get(b, b.replace('BRA_', '')) for b in e['bra']) or '—'
                trig = ', '.join(f'{esc(r)} <span class="mut">({TYPE_NAMES.get(next((t for n,(nm,t) in L["uid"].items() if nm==r), -1), "")})</span>' for r in L['refby'].get(e['name'], [])[:3]) or '<span class="mut">on level script</span>'
                k = f'{code}|{enc["tag"]}:{e["name"]}'
                H.append(f'<tr class="{cls}"><td></td><td>{esc(e["name"])}{" <span class=pill>scripted</span>" if scripted else ""}</td><td><b>{esc(e["crt"])}</b></td><td>{e["count"] if e["count"] is not None else "1"}</td><td>{e["alive"] if e["alive"] is not None else "—"}</td><td>{esc(bra)}</td><td>{trig}</td>'
                         f'<td class="prop"><input list="creatures" placeholder="keep" data-k="{esc(k)}" data-orig="{esc(e["crt"])}" onchange="onAssign(this)" style="width:130px"></td>'
                         f'<td class="prop"><input type="number" min="0" max="64" placeholder="{e["count"] if e["count"] is not None else 1}" data-k="{esc(k)}" data-f="count" data-orig="{e["count"] if e["count"] is not None else 1}" onchange="onSpawn(this)"> / <input type="number" min="0" max="64" placeholder="{e["alive"] if e["alive"] is not None else ""}" data-k="{esc(k)}" data-f="alive" data-orig="{e["alive"] if e["alive"] is not None else 0}" onchange="onSpawn(this)"></td></tr>')
        H.append('</table></section>')
    # bestiary
    H.append('<section class="level wrap"><h2>Bestiary</h2><div class="mut">every creature the game can stream into a level; "used in" lists the shipped levels</div><div class="best">')
    for c in sorted(idx['creatures'], key=str.lower):
        ci = idx['creatures'][c]; kind = classify(c, idx)[0]
        used = sorted(l[:-4] for l, v in idx['levels'].items() if c in v['rsrcs'])
        bras = sorted(set(BRA_WORDS.get(b, b.replace('BRA_', '')) for b in ci.get('bra', []) if b.startswith('BRA_Spawn')))
        img = os.path.relpath(os.path.join(img_dir, 'creatures', c + '.png'), os.path.dirname(out_html))
        H.append(f'<div class="card"><img src="{esc(img)}" alt="" onerror="this.style.display=\'none\'"><b>{esc(c)}</b> <span class="mut">{kind}</span><br><span class="mut">{esc(ci.get("wad",""))} · {(ci.get("bytes") or 0)//1024} KB</span><br>entrances: {esc(", ".join(bras) or "drops in")}<br><span class="mut">used in: {esc(", ".join(used) or "—")}</span></div>')
    H.append('</div></section>')
    H.append(f'<datalist id="creatures">{all_opts}</datalist><script>{js}</script></body></html>')
    open(out_html, 'w').write('\n'.join(H))


def to_pdf(html_path, pdf_path):
    for chrome in ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', 'google-chrome', 'chromium', 'chromium-browser']:
        try:
            subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}', 'file://' + os.path.abspath(html_path)],
                           check=True, capture_output=True, timeout=600)
            return chrome
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--levels', nargs='*', help='level codes (default: all cached)')
    ap.add_argument('--out', default=os.path.join(ROOT, 'report', 'gow2_enemy_layout.html'))
    ap.add_argument('--images', default=os.path.join(ROOT, 'report', 'renders'))
    ap.add_argument('--title', default='God of War II — Enemy Layout Reference')
    ap.add_argument('--no-pdf', action='store_true')
    a = ap.parse_args()
    idx = json.load(open(os.path.join(ROOT, 'cache', 'index.json')))
    G.KNOWN_CREATURES.update(c.lower() for c in idx['creatures'])
    codes = a.levels or [l[:-4] for l in idx['levels']]
    codes = sorted(codes, key=level_sort_key)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    levels = []
    for c in codes:
        try:
            levels.append(build_level(c, idx, a.images))
        except Exception as e:
            print(f'{c}: skipped ({e})', file=sys.stderr)
    render(levels, idx, a.out, a.images, a.title)
    print(f'wrote {a.out} ({len(levels)} levels, {sum(len(L["info"]["encounters"]) for L in levels)} encounter scripts, {sum(len(e["entities"]) for L in levels for e in L["info"]["encounters"])} spawners)')
    if not a.no_pdf:
        pdf = a.out[:-5] + '.pdf'
        used = to_pdf(a.out, pdf)
        print(f'wrote {pdf} via {used}' if used else 'no headless Chrome found; open the HTML and print to PDF')


if __name__ == '__main__':
    main()
