#!/usr/bin/env python3
"""
gow2_dc_dump.py - dump the DC ("tweak") data of any God of War II WAD in readable form.

  python3 scripts/gow2_dc_dump.py R_PERMA.WAD                 # every top-level object
  python3 scripts/gow2_dc_dump.py R_PERMA.WAD --object GBL_Global --follow
  python3 scripts/gow2_dc_dump.py R_HERO00.WAD --set DC_WAD_R_Hero --grep MeterAdjust

WAD sources: a local file path, or a pack name fetched from god_of_war_browser (:8000).
Each 4-byte word is shown as: #name (a hash found in the WAD's 0x0f name table), an integer
(< 100000), a float (plausible magnitude), or hex. --follow resolves array references: a member
whose value is (relative_offset << 12) | count points to `count` entries starting at its own
address + relative_offset (e.g. GBL_Global.Medusa -> the 3 Head of Euryale level entries).
"""
import argparse, os, re, struct, sys, urllib.request, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gow2_enemy_swap as G
B = 'http://localhost:8000'


def dc_sets(path_or_pack):
    """{set name: {tag: bytes}} for every DC_* set in the WAD."""
    if os.path.exists(path_or_pack):
        tags = G.read_wad(path_or_pack)
        out = {}
        for t in tags:
            if t.name.startswith('DC_') and 0x0B <= t.tag <= 0x10:
                out.setdefault(t.name, {})[t.tag] = t.data
        return out
    j = json.load(urllib.request.urlopen(f'{B}/json/pack/{path_or_pack}', timeout=180))
    out = {}
    for t in j['Tags']:
        if t['Name'].startswith('DC_') and 0x0B <= t['Tag'] <= 0x10:
            out.setdefault(t['Name'], {})[t['Tag']] = urllib.request.urlopen(f"{B}/dump/pack/{path_or_pack}/{t['Id']}", timeout=180).read()
    return out


def word(raw, i, hm):
    u = struct.unpack_from('<I', raw, i)[0]; f = struct.unpack_from('<f', raw, i)[0]
    if u in hm and u:
        return f'#{hm[u]}'
    if u < 100000:
        return str(u)
    if 1e-4 < abs(f) < 1e7:
        return f'{f:g}'
    return f'{u:08x}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('wad'); ap.add_argument('--set', help='DC set name (default: the largest)')
    ap.add_argument('--object', help='only this top-level object'); ap.add_argument('--grep', help='only fields whose name matches')
    ap.add_argument('--follow', action='store_true', help='resolve (offset<<12)|count array references')
    a = ap.parse_args()
    sets = dc_sets(a.wad)
    if not sets:
        sys.exit('no DC data in this WAD')
    name = a.set or max(sets, key=lambda k: len(sets[k].get(0x0C, b'')))
    d = sets[name]
    blob = d[0x0C]; fl = sorted(G.fields_named(d[0x10])); hm = G.parse_hashes(d[0x0F])
    tops = sorted(G.parse_pairs(d[0x0D]))
    print(f'# {a.wad} {name}: {len(blob)} bytes, {len(fl)} fields, {len(tops)} top-level objects (sets: {", ".join(sets)})')
    offs = sorted({o for o, _, _ in fl})
    def span(o, limit):
        nxt = next((x for x in offs if x > o), limit)
        return min(nxt, limit)
    for ti, (to, tn) in enumerate(tops):
        if a.object and tn != a.object:
            continue
        tend = min([o for o, _ in tops if o > to] + [len(blob)])
        print(f'\n== {tn} @{to:#x} ({tend - to} bytes)')
        for o, n, t in fl:
            if not (to <= o < tend) or (a.grep and not re.search(a.grep, n, re.I)):
                continue
            e = span(o, tend)
            vals = [word(blob, i, hm) for i in range(o, e - 3, 4)]
            print(f'   +{o - to:05x} {n:30s} type={t:#04x} [{" ".join(vals)}]')
            if a.follow:
                for i in range(o, e - 3, 4):
                    v = struct.unpack_from('<I', blob, i)[0]; cnt, rel = v & 0xFFF, v >> 12
                    if 0 < cnt <= 256 and 0 < rel < 0x8000 and i + rel in offs:
                        heads = [x for x in fl if x[0] >= i + rel and x[1].startswith('t')][:cnt]
                        print(f'        -> array of {cnt} at +{i + rel - to:05x}: {[h[1] for h in heads][:8]}')


if __name__ == '__main__':
    main()
