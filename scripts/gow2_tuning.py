#!/usr/bin/env python3
"""
gow2_tuning.py - read and edit the global tuning tables in R_PERMA.WAD (GBL_Global).

GBL_Global (top-level object of DC_WAD_R_Perm) holds array members encoded as
(relative_offset << 12) | count, pointing at per-entry tables:
  Difficulty x4 (Mortal, Spartan, God, Titan), Costume x17, Weapon x6 (Blades levels),
  Medusa/Earth/Electric/Wind x3 (magic levels), Bone/Hammer/Olympus x3 (sub-weapon levels).
Values inside entries are unnamed 4-byte words; this module exposes each word with its kind
(float / int / hash name / hex) and edits numeric words in place (blob size never changes).

  python3 scripts/gow2_tuning.py dump R_PERMA.WAD
  python3 scripts/gow2_tuning.py set R_PERMA.WAD out/R_PERMA.mod.WAD Difficulty 3 1 6.0
"""
import argparse, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gow2_enemy_swap as G

GROUPS = [  # (member, label, entry labels)
    ('Difficulty', 'Difficulty', ['Mortal', 'Spartan', 'God', 'Titan']),
    ('Weapon', 'Blades (levels)', [f'L{i + 1}' for i in range(6)]),
    ('Medusa', 'Head of Euryale (Medusa)', ['L1', 'L2', 'L3']),
    ('Earth', 'Atlas Quake (Earth)', ['L1', 'L2', 'L3']),
    ('Electric', "Cronos' Rage (Electric)", ['L1', 'L2', 'L3']),
    ('Wind', "Typhon's Bane (Wind)", ['L1', 'L2', 'L3']),
    ('Hammer', 'Barbarian Hammer', ['L1', 'L2', 'L3']),
    ('Bone', 'Spear of Destiny (Bone)', ['L1', 'L2', 'L3']),
    ('Olympus', 'Blade of Olympus', ['L1', 'L2', 'L3']),
    ('Costume', 'Costumes', [f'#{i}' for i in range(17)]),
]
NOTES = {  # observations only; column meanings are not confirmed in game
    'Difficulty': 'c0 falls with difficulty (2, 1, 1, 0.75): likely damage Kratos deals. c1 rises (0.5, 1, 2.5, 5): likely damage Kratos takes. Unconfirmed.',
    'Weapon': 'c4 rises 1, 1.5, 2, 2.5, 3 per Blades level (trail intensity?). Damage is not stored here.',
    'Medusa': 'Level 1 beam, level 2 adds goMedusaFlash, level 3 adds the bomb (ARRE_MEDUSA_BOMB). c3 = 100/200/300.',
    'Earth': 'c0 = 20/25/30 per level; later columns 100/500 -> 250/750.',
    'Electric': 'c1 = 10/12.5/16.5, c5 = 200/300/400 rise; c4 = 260/168/76 falls.',
    'Hammer': 'c0 = 1/1.75/3 per level (multiplier?).',
    'Bone': 'c0 = level number; c4 = 10/15/20.',
    'Olympus': 'c0 = level number.',
    'Costume': 'Per-costume multipliers (e.g. 0.5 / 2 / 5). Unconfirmed meanings.',
}


def perm_dc(tags):
    idx = {t.tag: i for i, t in enumerate(tags) if t.name.startswith('DC_WAD_R_Perm') and 0x0B <= t.tag <= 0x10}
    if 0x0C not in idx:
        raise ValueError('not R_PERMA: no DC_WAD_R_Perm')
    return idx


def kind_of(raw, i, hm):
    u = struct.unpack_from('<I', raw, i)[0]; f = struct.unpack_from('<f', raw, i)[0]
    if u in hm and u:
        return 'hash', hm[u]
    if u < 100000:
        return 'int', u
    if 1e-4 < abs(f) < 1e7:
        return 'float', round(f, 6)
    if u == 0:
        return 'int', 0
    return 'hex', f'{u:08x}'


def read_tables(tags):
    ix = perm_dc(tags)
    blob = tags[ix[0x0C]].data; fl = sorted(G.fields_named(tags[ix[0x10]].data)); hm = G.parse_hashes(tags[ix[0x0F]].data)
    base = next(o for o, n, t in fl if n == 'GBL_Global')
    gend = min([o for o, _ in G.parse_pairs(tags[ix[0x0D]].data) if o > base] + [len(blob)])
    offs = sorted({o for o, _, _ in fl})
    out = []
    for mem, label, elabels in GROUPS:
        fo = next(o for o, n, t in fl if n == mem and base <= o < gend)
        v = struct.unpack_from('<I', blob, fo)[0]; cnt, rel = v & 0xFFF, v >> 12
        start = fo + rel
        heads = [x for x in fl if x[0] >= start and x[1].startswith('tStage')][:cnt]
        entries = []
        for k, (o, n, t) in enumerate(heads):
            if k + 1 < len(heads):
                end = heads[k + 1][0]
            else:                                   # last entry: same length as the previous one
                end = o + (heads[k][0] - heads[k - 1][0] if k else 32)
            members = {x[0] - o: x[1] for x in fl if o < x[0] < end and not x[1].startswith('tStage')}
            words = []
            for i in range(o, end - 3, 4):
                kd, val = kind_of(blob, i, hm)
                words.append(dict(off=i, kind=kd, value=val, member=members.get(i - o)))
            entries.append(dict(label=elabels[k] if k < len(elabels) else f'#{k}', stage=n, words=words))
        # a stored 0 can be int or float: take the kind from the same column in sibling entries
        for col in range(max((len(e['words']) for e in entries), default=0)):
            kinds = {e['words'][col]['kind'] for e in entries if col < len(e['words']) and e['words'][col]['value'] not in (0, 0.0)}
            for e in entries:
                if col < len(e['words']):
                    w = e['words'][col]
                    if w['kind'] == 'int' and w['value'] == 0 and kinds == {'float'}:
                        w['kind'], w['value'] = 'float', 0.0
        out.append(dict(member=mem, label=label, note=NOTES.get(mem, ''), entries=entries))
    return out


def word_kinds(tags):
    return {w['off']: w['kind'] for g in read_tables(tags) for e in g['entries'] for w in e['words']}


def apply_edits(tags, edits, log=print):
    """edits: {blob offset (int or str): value}; floats stay floats, ints stay ints."""
    ix = perm_dc(tags)
    t = tags[ix[0x0C]]; data = bytearray(t.data)
    hm = G.parse_hashes(tags[ix[0x0F]].data)
    kinds = word_kinds(tags)
    n = 0
    for k, val in edits.items():
        off = int(k)
        _, old = kind_of(bytes(data), off, hm)
        kd = kinds.get(off)
        if kd is None:
            raise ValueError(f'offset {off:#x} is not inside a GBL_Global table')
        if kd == 'float':
            struct.pack_into('<f', data, off, float(val))
        elif kd == 'int':
            struct.pack_into('<I', data, off, int(val))
        else:
            raise ValueError(f'offset {off:#x} holds a {kd}, not editable')
        n += 1
        log(f'GBL+{off:#x}: {old} -> {val}')
    t.data = bytes(data)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    d = sp.add_parser('dump'); d.add_argument('wad')
    s = sp.add_parser('set'); s.add_argument('wad'); s.add_argument('out'); s.add_argument('group'); s.add_argument('entry', type=int); s.add_argument('col', type=int); s.add_argument('value')
    a = ap.parse_args()
    tags = G.read_wad(a.wad); tables = read_tables(tags)
    if a.cmd == 'dump':
        for g in tables:
            print(f"\n== {g['label']} ({g['member']})  {g['note']}")
            for e in g['entries']:
                print(f"   {e['label']:8s} " + ' '.join(str(w['value']) if w['kind'] in ('int', 'float') else ('#' + str(w['value']) if w['kind'] == 'hash' else '.') for w in e['words']))
    else:
        g = next(x for x in tables if x['member'] == a.group)
        w = g['entries'][a.entry]['words'][a.col]
        apply_edits(tags, {w['off']: a.value})
        open(a.out, 'wb').write(G.write_wad(tags)); print('wrote', a.out)


if __name__ == '__main__':
    main()
