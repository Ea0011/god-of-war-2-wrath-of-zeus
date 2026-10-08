#!/usr/bin/env python3
"""Local web UI for per-encounter enemy swaps in God of War II level WADs.

Talks to a running god_of_war_browser (default http://localhost:8000) to list/download/upload
WADs, and to scripts/gow2_enemy_swap.py for the actual editing.

  python3 scripts/gow2_swap_ui.py [--browser http://localhost:8000] [--port 8787]
"""
import argparse, hashlib, json, os, re, struct, sys, threading, time, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gow2_enemy_swap as G  # noqa: E402

CACHE = os.path.join(ROOT, 'cache'); WADS = os.path.join(CACHE, 'wads')
OUT = os.path.join(ROOT, 'out'); BACKUPS = os.path.join(ROOT, 'backups')
for d in (CACHE, WADS, OUT, BACKUPS):
    os.makedirs(d, exist_ok=True)
INDEX_FILE = os.path.join(CACHE, 'index.json')
BROWSER = 'http://localhost:8000'
STATE = dict(scan=dict(running=False, done=0, total=0, msg='', error=None), index=None)
LOCK = threading.Lock()


# ------------------------------------------------------------------ browser client
def bget(path, timeout=600):
    return urllib.request.urlopen(BROWSER + path, timeout=timeout).read()


def pack_list():
    return json.loads(bget('/json/pack', 30))


def wad_json(name):
    return json.loads(bget(f'/json/pack/{name}'))


def fetch_wad(name, force=False):
    p = os.path.join(WADS, name)
    if force or not os.path.exists(p):
        open(p, 'wb').write(bget(f'/dump/pack/{name}'))
    return p


def upload_wad(name, data):
    boundary = 'XxGoW2xX'
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="data"; filename="{name}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(BROWSER + f'/upload/pack/{name}', data=body, method='POST',
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    return urllib.request.urlopen(req, timeout=900).read().decode('latin1', 'replace')


def dc_tags_from_json(name, j):
    """Build minimal Tag objects (RSRCS + DC_*) by dumping only those tags."""
    tags = []
    for t in j['Tags']:
        if t['Name'] == 'RSRCS' or (t['Name'].startswith('DC_') and 0x0B <= t['Tag'] <= 0x10):
            tg = G.Tag(); tg.tag, tg.flags, tg.size, tg.name = t['Tag'], t['Flags'], t['Size'], t['Name']
            tg.data = bget(f"/dump/pack/{name}/{t['Id']}")
            tags.append(tg)
    return tags


# ------------------------------------------------------------------ index (creatures + donors)
def load_index():
    if STATE['index'] is None and os.path.exists(INDEX_FILE):
        STATE['index'] = json.load(open(INDEX_FILE))
    return STATE['index'] or dict(creatures={}, levels={}, built=None)


def scan_worker(levels_only_regex):
    st = STATE['scan']
    try:
        idx = load_index()
        names = pack_list()
        rwads = [n for n in names if n.startswith('R_') and n.endswith('.WAD')]
        lwads = [n for n in names if n.endswith('.WAD') and not n.startswith('R_') and re.match(levels_only_regex, n)]
        st.update(total=len(rwads) + len(lwads), done=0, running=True, error=None)
        for w in rwads:
            st['msg'] = f'creature {w}'
            try:
                j = wad_json(w)
                top = [t for t in j['Tags'] if t['Tag'] == 0x0D and t['Name'].startswith('DC_')]
                if top:
                    b = bget(f"/dump/pack/{w}/{top[0]['Id']}")
                    tl = [n for _, n in G.parse_pairs(b)]
                    crt = [n[4:] for n in tl if n.startswith('CRT_')]
                    if crt:
                        c = idx['creatures'].setdefault(crt[0], {})
                        c.update(wad=w, bra=[n for n in tl if n.startswith('BRA_')],
                                 bytes=sum(t['Size'] for t in j['Tags'] if t['Tag'] != 0))
            except Exception as e:  # keep going
                st['msg'] = f'{w}: {e}'
            st['done'] += 1
        for w in lwads:
            st['msg'] = f'level {w}'
            try:
                j = wad_json(w)
                tags = dc_tags_from_json(w, j)
                info = G.level_info(tags)
                idx['levels'][w] = dict(rsrcs=info['rsrcs'], creatures=info['creatures'])
                for cn, blk in info['creatures'].items():
                    if blk:
                        c = idx['creatures'].setdefault(cn, {})
                        d = c.setdefault('donors', {})
                        d[w] = blk
            except Exception as e:
                st['msg'] = f'{w}: {e}'
            st['done'] += 1
        st['msg'] = 'summoners'
        scan_summons(idx, log=lambda m: None)
        idx['built'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with LOCK:
            STATE['index'] = idx
            json.dump(idx, open(INDEX_FILE, 'w'))
        st['msg'] = 'done'
    except Exception as e:
        st['error'] = str(e)
    finally:
        st['running'] = False


def shipped_level_path(name):
    bk = os.path.join(BACKUPS, name + '.orig')
    return bk if os.path.exists(bk) else fetch_wad(name)


def scan_summons(idx, log=print):
    """Record which creatures summon by calling a level entity, and a template of each such
    entity copied from an unmodified shipped level (prefer a level that ships the summoner)."""
    summoners = {}
    for c, v in idx['creatures'].items():
        w = v.get('wad')
        if not w:
            continue
        j = wad_json(w)
        tg = {t['Tag']: t['Id'] for t in j['Tags'] if t['Name'].startswith('DC_') and 0x0b <= t['Tag'] <= 0x10}
        if 0x0c not in tg:
            continue
        blob = bget(f'/dump/pack/{w}/{tg[0x0c]}'); f10 = bget(f'/dump/pack/{w}/{tg[0x10]}')
        names = G.summon_targets_from_dc(blob, G.fields_named(f10))
        v['summons'] = names
        if names:
            summoners[c] = names
    for c, names in summoners.items():
        tpls = {}
        order = sorted(idx['levels'], key=lambda l: (c not in idx['levels'][l]['rsrcs'], l))
        for ent in names:
            for lvl in order:
                try:
                    tags = G.read_wad(shipped_level_path(lvl))
                except Exception:
                    continue
                hit = G.find_entity(tags, ent)
                if hit:
                    e = hit[1]
                    crt = [x[4:] for _, x in G.entity_strings(e)[1] if x.startswith('CRT_')]
                    tpls[ent] = dict(level=lvl, entity=e.hex(), crt=crt[0] if crt else None,
                                     bra=[x for _, x in G.entity_strings(e)[1] if x.startswith('BRA_')])
                    break
        idx['creatures'][c]['summon_templates'] = tpls
        log(f'{c}: summons via {names}; templates from ' + ', '.join(f"{k}<-{v['level']} ({v['crt']})" for k, v in tpls.items()))
    return summoners


def creature_db(prefer_level=None):
    """{Creature: {bra, block}} choosing the donor with the largest N (or prefer_level)."""
    idx = load_index(); db = {}
    # merge names that differ only by case (hash lookups are case-insensitive; RSRCS casing varies)
    merged = {}
    for cn, c in idx['creatures'].items():
        key = next((k for k in merged if k.lower() == cn.lower()), None)
        if key is None:
            merged[cn] = dict(c, donors=dict(c.get('donors', {})))
        else:
            m = merged[key]
            m.setdefault('bra', c.get('bra', [])); m.setdefault('wad', c.get('wad'))
            m['donors'].update(c.get('donors', {}))
            if c.get('wad') and not m.get('wad'):
                m['wad'] = c['wad']; m['bra'] = c.get('bra', [])
    for cn, c in merged.items():
        donors = c.get('donors', {})
        blk = None
        # never take a block from a level we have modified ourselves (it has a backup); prefer shipped data
        shipped = {k: v for k, v in donors.items() if not os.path.exists(os.path.join(BACKUPS, k + '.orig'))} or donors
        if prefer_level in shipped:
            blk = shipped[prefer_level]
        elif shipped:
            blk = max(shipped.values(), key=lambda b: b['n'])
        db[cn] = dict(bra=c.get('bra', []), block=blk, wad=c.get('wad'), donors=sorted(donors), bytes=c.get('bytes'),
                      summons=c.get('summons', []), summon_templates=c.get('summon_templates', {}))
    return db


# ------------------------------------------------------------------ level ops
def budget(rsrcs, db=None):
    db = db or creature_db()
    rows = [(c, (db.get(c) or {}).get('bytes')) for c in rsrcs]
    return dict(rows=rows, total=sum(b or 0 for _, b in rows), unknown=[c for c, b in rows if b is None])


def level_load(name, force=False):
    p = fetch_wad(name, force)
    tags = G.read_wad(p)
    info = G.level_info(tags)
    info['budget'] = budget(info['rsrcs'])
    bk0 = os.path.join(BACKUPS, name + '.orig')
    if os.path.exists(bk0):
        info['budget_original'] = budget(G.level_info(G.read_wad(bk0))['rsrcs'])
    info['entity_names'] = sorted({G.entity_strings(e)[0] for t in tags if G.is_entities_script(t) for e in G.iter_entities(t.data)})
    info['file'] = p; info['size'] = os.path.getsize(p)
    info['sha256'] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    bk = os.path.join(BACKUPS, name + '.orig')
    info['backup'] = bk if os.path.exists(bk) else None
    return info


def level_apply(name, plan, upload):
    log = []
    p = fetch_wad(name)
    tags = G.read_wad(p)
    res = G.apply_plan(tags, plan, creature_db(), log=log.append)
    b = budget(res['rsrcs']); log.append(f"creature WAD payload now {b['total']/1024:.0f} KB for {res['rsrcs']}" + (f" (unknown size: {b['unknown']})" if b['unknown'] else ''))
    data = G.write_wad(tags)
    outp = os.path.join(OUT, name.replace('.WAD', '') + '.mod.WAD')
    open(outp, 'wb').write(data)
    sha = hashlib.sha256(data).hexdigest()
    log.append(f'wrote {outp} ({len(data)} bytes, sha256 {sha[:16]})')
    # sanity reparse
    G.level_info(G.read_wad(outp))
    bk = os.path.join(BACKUPS, name + '.orig')
    if upload:
        if not os.path.exists(bk):
            open(bk, 'wb').write(open(p, 'rb').read())
            log.append(f'backup saved: {bk}')
        r = upload_wad(name, data)
        log.append(f'upload response: {r or "ok"}')
        back = bget(f'/dump/pack/{name}')
        ok = hashlib.sha256(back).hexdigest() == sha
        log.append(f'readback {"matches" if ok else "DOES NOT MATCH"} the uploaded file')
        if ok:
            open(p, 'wb').write(data)   # cache now holds what the ISO holds
        res['uploaded'] = ok
    res['output'] = outp; res['sha256'] = sha; res['log'] = log; res['wad_bytes'] = len(data); res['budget'] = b
    return res


def level_restore(name):
    bk = os.path.join(BACKUPS, name + '.orig')
    if not os.path.exists(bk):
        raise FileNotFoundError(f'no backup for {name}')
    data = open(bk, 'rb').read()
    r = upload_wad(name, data)
    back = bget(f'/dump/pack/{name}')
    ok = hashlib.sha256(back).hexdigest() == hashlib.sha256(data).hexdigest()
    if ok:
        open(os.path.join(WADS, name), 'wb').write(data)
    return dict(restored=ok, response=r)


# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def _err(self, e):
        self._json(dict(error=str(e)), 500)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == '/':
                b = open(os.path.join(HERE, 'gow2_swap_ui.html'), 'rb').read()
                self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
            elif u.path == '/api/status':
                try:
                    pack_list(); ok = True
                except Exception:
                    ok = False
                idx = load_index()
                self._json(dict(browser=BROWSER, browser_ok=ok, scan=STATE['scan'], index_built=idx.get('built'),
                                creatures=len(idx['creatures']), levels=len(idx['levels'])))
            elif u.path == '/api/levels':
                names = [n for n in pack_list() if n.endswith('.WAD') and not n.startswith('R_')]
                self._json(names)
            elif u.path == '/api/creatures':
                self._json(creature_db(q.get('level', [None])[0]))
            elif u.path == '/api/level':
                self._json(level_load(q['name'][0], force=q.get('force', ['0'])[0] == '1'))
            else:
                self._json(dict(error='not found'), 404)
        except Exception as e:
            self._err(e)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
        try:
            if self.path == '/api/scan':
                if not STATE['scan']['running']:
                    threading.Thread(target=scan_worker, args=(body.get('levels', r'^[A-Z]+\d+\.WAD$'),), daemon=True).start()
                self._json(STATE['scan'])
            elif self.path == '/api/preview':
                tags = G.read_wad(fetch_wad(body['name'])); log = []
                res = G.apply_plan(tags, body['plan'], creature_db(), log=log.append)
                b = budget(res['rsrcs']); log.append(f"creature WAD payload now {b['total']/1024:.0f} KB for {res['rsrcs']}")
                res['log'] = log; res['budget'] = b; res['wad_bytes'] = len(G.write_wad(tags)); self._json(res)
            elif self.path == '/api/apply':
                self._json(level_apply(body['name'], body['plan'], bool(body.get('upload'))))
            elif self.path == '/api/restore':
                self._json(level_restore(body['name']))
            else:
                self._json(dict(error='not found'), 404)
        except Exception as e:
            self._err(e)


def main():
    global BROWSER
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default=BROWSER); ap.add_argument('--port', type=int, default=8787)
    a = ap.parse_args(); BROWSER = a.browser.rstrip('/')
    print(f'GoW2 swap UI on http://localhost:{a.port}  (browser: {BROWSER})')
    ThreadingHTTPServer(('127.0.0.1', a.port), H).serve_forever()


if __name__ == '__main__':
    main()
