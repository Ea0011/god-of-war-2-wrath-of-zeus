#!/usr/bin/env python3
"""
gow2_enemy_swap.py - decode God of War II (PS2) level WADs and swap one enemy type
for another.

Three places in a level WAD know which enemies the level uses:

  1. RSRCS tag (0x12)      list of 24-byte names -> enemy WADs to load (R_<NAME>.WAD)
  2. DC_WAD_* tags (0x0b..0x10)   the level "tweak" container.  Its WAD_<level> object
                           holds the object pools (tGOPool_N: hash(goXxx) -> count) and
                           memory pools (tMemoryPool_N: hash(system) -> count).  Without
                           a pool for goOrders02 (and its helper objects) the engine can
                           not instantiate the creature even if R_ORDERS02.WAD is loaded.
  3. ESC_* SCR_Entities scripts   spawners push the strings "CRT_<Enemy>" and "BRA_<Spawn
                           behaviour>" on the script stack.

Usage:
  gow2_enemy_swap.py dump  LEVEL.WAD
  gow2_enemy_swap.py swap  LEVEL.WAD --old Satyr10 --new Orders02 --donor LEVEL_WITH_ORDERS.WAD
                           [--count N] [--rename BRA_SpawnCeiling=BRA_Spawn ...] -o OUT.WAD
  gow2_enemy_swap.py selftest LEVEL.WAD...      (round-trip the WAD writer and DC serializers)
"""
import argparse
import re
import struct
import sys

M32 = 0xFFFFFFFF
TYPE_GOPOOL, TYPE_MEMPOOL, TYPE_WADOBJ = 0xE3, 0xE4, 0xE5


# ----------------------------------------------------------------------------- helpers
def ghash(s: str) -> int:
    """Engine string hash used by DC_WAD: h = h*127 + c over the UPPER-CASED name."""
    h = 0
    for c in s.upper().encode('latin1'):
        h = (h * 127 + c) & M32
    return h


def zstr(b, o):
    e = b.index(b'\0', o)
    return b[o:e].decode('latin1')


def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def align(x, a):
    return (x + a - 1) // a * a


# ----------------------------------------------------------------------------- WAD I/O
class Tag:
    __slots__ = ('tag', 'flags', 'size', 'name', 'data')

    def __repr__(self):
        return f'Tag({self.tag:#x},{self.name!r},{self.size})'


def read_wad(path):
    d = open(path, 'rb').read()
    pos, tags = 0, []
    while pos + 32 <= len(d):
        t = Tag()
        t.tag, t.flags, t.size = struct.unpack_from('<HHI', d, pos)
        t.name = d[pos + 8:pos + 32].split(b'\0')[0].decode('latin1')
        pos += 32
        if t.tag == 0:              # EntityCount: size field is a count, no payload
            t.data = None
        else:
            t.data = d[pos:pos + t.size]
            pos += t.size
        pos = align(pos, 16)
        tags.append(t)
    return tags


def write_wad(tags):
    out = bytearray()
    for t in tags:
        size = t.size if t.data is None else len(t.data)
        out += struct.pack('<HHI', t.tag, t.flags, size)
        nb = t.name.encode('latin1')[:24]
        out += nb + b'\0' * (24 - len(nb))
        if t.data is not None:
            out += t.data
            out += b'\0' * (align(len(out), 16) - len(out))
    return bytes(out)


# ----------------------------------------------------------------------------- DC_WAD
def parse_pairs(b):
    n = u32(b, 0)
    return [(u32(b, 4 + 8 * i), zstr(b, u32(b, 8 + 8 * i))) for i in range(n)]


def build_pairs(pairs):
    n = len(pairs)
    out = bytearray(struct.pack('<I', n))
    strs = bytearray()
    for off, name in pairs:
        out += struct.pack('<II', off, 4 + 8 * n + len(strs))
        strs += name.encode('latin1') + b'\0'
    out += strs
    out += b'\0' * (align(len(out), 4) - len(out))
    return bytes(out)


def parse_fields(b):
    n = u32(b, 0)
    return [list(struct.unpack_from('<III', b, 4 + 12 * i)) for i in range(n)]  # off, nameoff, type


def fields_named(b):
    return [(off, zstr(b, no), ty) for off, no, ty in parse_fields(b)]


def build_fields(fields):
    """fields: list of (off, name, type)"""
    n = len(fields)
    out = bytearray(struct.pack('<I', n))
    strs = bytearray()
    for off, name, ty in fields:
        out += struct.pack('<III', off, 4 + 12 * n + len(strs), ty)
        strs += name.encode('latin1') + b'\0'
    out += strs
    out += b'\0' * (align(len(out), 4) - len(out))
    return bytes(out)


def parse_hashes(b):
    """hash -> name.  Some shipped tables (e.g. RHOD10) have misaligned string offsets and
    duplicate strings, so names are recovered by re-hashing every string in the string area
    and only trusted when the hash matches; unmatched hashes keep whatever the offset says."""
    n = u32(b, 0)
    area = b[4 + 8 * n:]
    byhash = {ghash(s.decode('latin1')): s.decode('latin1') for s in area.split(b'\0') if s}
    for s in KNOWN_NAMES:
        byhash.setdefault(ghash(s), s)
    out = {}
    for i in range(n):
        h, o = u32(b, 4 + 8 * i), u32(b, 8 + 8 * i)
        name = zstr(b, o) if o < len(b) else ''
        if ghash(name) != h:
            name = byhash.get(h, name)
        out[h] = name
    return out


KNOWN_NAMES = set()


def learn_names(b):
    """remember every string of a hash table so other tables can resolve the same hashes."""
    n = u32(b, 0)
    for s in b[4 + 8 * n:].split(b'\0'):
        if s:
            KNOWN_NAMES.add(s.decode('latin1'))


def build_hashes(hm):
    items = sorted(hm.items())            # table is sorted by hash (binary search)
    n = len(items)
    out = bytearray(struct.pack('<I', n))
    strs = bytearray()
    for h, name in items:
        out += struct.pack('<II', h, 4 + 8 * n + len(strs))
        strs += name.encode('latin1') + b'\0'
    out += strs
    out += b'\0' * (align(len(out), 4) - len(out))
    return bytes(out)


class DC:
    def __init__(self, tags):
        self.ti = {}
        for i, t in enumerate(tags):
            if t.name.startswith('DC_') and 0x0B <= t.tag <= 0x10:
                self.ti[t.tag] = i
        if set(self.ti) != set(range(0x0B, 0x11)):
            raise SystemExit('DC_WAD tags 0x0b..0x10 not all present')
        self.tags = tags
        self.blob = bytes(tags[self.ti[0x0C]].data)
        self.fields = fields_named(tags[self.ti[0x10]].data)
        self.top = parse_pairs(tags[self.ti[0x0D]].data)
        self.imports = parse_pairs(tags[self.ti[0x0E]].data)
        learn_names(tags[self.ti[0x0F]].data)
        self.hashes = parse_hashes(tags[self.ti[0x0F]].data)

    def name_of(self, h):
        return self.hashes.get(h, '@hash(%08x)' % h)

    def pools(self):
        res = []
        for fi, (off, name, ty) in enumerate(self.fields):
            if ty in (TYPE_GOPOOL, TYPE_MEMPOOL):
                h, c = struct.unpack_from('<II', self.blob, off)
                res.append(dict(idx=int(name.rsplit('_', 1)[1]), kind='go' if ty == TYPE_GOPOOL else 'mem',
                                fi=fi, off=off, hash=h, count=c, name=self.name_of(h)))
        return res

    def wad_field(self):
        for fi, f in enumerate(self.fields):
            if f[2] == TYPE_WADOBJ:
                return fi
        raise SystemExit('no WAD_<level> object (type 0xe5) in DC_WAD')

    def store(self):
        """write parsed tables back into the tag list (blob is written by caller)."""
        self.tags[self.ti[0x0C]].data = bytes(self.blob)
        self.tags[self.ti[0x10]].data = build_fields(self.fields)
        self.tags[self.ti[0x0D]].data = build_pairs(self.top)
        self.tags[self.ti[0x0E]].data = build_pairs(self.imports)
        self.tags[self.ti[0x0F]].data = build_hashes(self.hashes)


def enemy_block(pools, enemy):
    """Return (go_entries, mem_entries) that the level generator emitted for `enemy`.

    tGOPool_N / tMemoryPool_N numbers are one global sequence in generation order:
    [enemy GO pools...][enemy memory pools...].  The block starts at the go<Enemy> entry."""
    target = ghash('go' + enemy)
    seq = sorted(pools, key=lambda p: p['idx'])
    starts = [k for k, p in enumerate(seq) if p['kind'] == 'go' and p['hash'] == target]
    if not starts:
        return None, None
    k = starts[0]
    go, mem = [], []
    fxbone = ghash('fxBoneData')
    # A creature block is one or more [GO run][MEM run] pairs; the generator nests helper groups
    # (e.g. Medusa: goStoneHero/goFreezeHero + MedusaEyeAttackData systems) and always closes the
    # creature with its systems block, whose last entry is fxBoneData x1.
    while k < len(seq):
        if seq[k]['kind'] == 'go' and (go or mem):
            if seq[k]['hash'] != target and _is_creature_start(seq[k]):
                break
        while k < len(seq) and seq[k]['kind'] == 'go':
            go.append(seq[k]); k += 1
        run = []
        while k < len(seq) and seq[k]['kind'] == 'mem':
            run.append(seq[k]); k += 1
        fx = next((i for i, x in enumerate(run) if x['hash'] == fxbone), None)
        if fx is None:
            mem.extend(run)
            if not run:
                break
            continue
        keep = run[:fx + 1]
        # one trailing creature-scaled entry may follow (Siren ConcussionInstanceData, Cerpup
        # GrowCharInstanceData, Tryng tValidityDisk); passive-object blocks (hfsmReactive...) never do
        if len(run) == fx + 2 and run[fx + 1]['name'] != 'hfsmReactive':
            keep.append(run[fx + 1])
        mem.extend(keep)
        break
    return go, mem


KNOWN_CREATURES = set()   # lower-case creature names (filled from RSRCS / index); used as block boundaries


def _is_creature_start(p):
    n = p['name'].lower()
    return n.startswith('go') and n[2:] in KNOWN_CREATURES


def scale_block(block, n_donor, n_new):
    out = []
    for p in block:
        c = p['count']
        if p['name'] != 'fxBoneData' and n_donor and c % n_donor == 0:
            c = c // n_donor * n_new
        out.append((p['hash'], c, p['name']))
    return out


def wad_header(n_go, n_mem):
    a = (0x8000 | n_go) if n_go else 0
    b = (n_go << 15) | 0x4000 | n_mem
    return struct.pack('<II', a, b)


def rebuild_pools(dc, old_go, old_mem, new_go, new_mem):
    """Replace one enemy's pool block in the DC blob and fix every table that holds offsets."""
    wfi = dc.wad_field()
    woff = dc.fields[wfi][0]
    a, b = struct.unpack_from('<II', dc.blob, woff)
    n_go_old, n_mem_old = a & 0x7FFF, b & 0x3FFF
    assert wad_header(n_go_old, n_mem_old) == dc.blob[woff:woff + 8], 'unexpected WAD object header'
    pools = dc.pools()
    go_list = sorted([p for p in pools if p['kind'] == 'go'], key=lambda p: p['off'])
    mem_list = sorted([p for p in pools if p['kind'] == 'mem'], key=lambda p: p['off'])
    assert len(go_list) == n_go_old and len(mem_list) == n_mem_old
    old_tail = woff + 8 + 8 * (n_go_old + n_mem_old)

    def splice(lst, old, new):
        if not old:
            return [dict(hash=h, count=c, name=n, idx=None) for h, c, n in new] + lst
        i = lst.index(old[0]); j = lst.index(old[-1]) + 1
        assert lst[i:j] == old, 'enemy pool block is not contiguous'
        return lst[:i] + [dict(hash=h, count=c, name=n, idx=None) for h, c, n in new] + lst[j:]

    go_new = splice(go_list, old_go, new_go)
    mem_new = splice(mem_list, old_mem, new_mem)

    # renumber tGOPool_N / tMemoryPool_N in generation order (old idx order, new block in place)
    seq = sorted(pools, key=lambda p: p['idx'])
    old_block = old_go + old_mem
    if old_block:
        i = seq.index(old_block[0])
        seq = seq[:i] + [None] * 1 + [p for p in seq if p not in old_block][i:]
    else:
        seq = [None] + seq
    newblock = [p for p in go_new if p['idx'] is None] + [p for p in mem_new if p['idx'] is None]
    merged = []
    for p in seq:
        merged.extend(newblock if p is None else [p])
    for n, p in enumerate(merged):
        p['newidx'] = n

    # blob
    body = bytearray()
    for p in go_new:
        body += struct.pack('<II', p['hash'], p['count'])
    for p in mem_new:
        body += struct.pack('<II', p['hash'], p['count'])
    new_blob = dc.blob[:woff] + wad_header(len(go_new), len(mem_new)) + bytes(body) + dc.blob[old_tail:]
    delta = len(new_blob) - len(dc.blob)

    # field table
    newfields = [f for f in dc.fields if f[0] < woff]
    newfields.append((woff, dc.fields[wfi][1], TYPE_WADOBJ))
    o = woff + 8
    for p in go_new:
        newfields.append((o, f"tGOPool_{p['newidx']}", TYPE_GOPOOL)); o += 8
    for p in mem_new:
        newfields.append((o, f"tMemoryPool_{p['newidx']}", TYPE_MEMPOOL)); o += 8
    for off, name, ty in dc.fields:
        if off >= old_tail:
            newfields.append((off + delta, name, ty))
    dc.fields = newfields
    dc.top = [(off + delta if off >= old_tail else off, n) for off, n in dc.top]
    dc.imports = [(off + delta if off >= old_tail else off, n) for off, n in dc.imports]

    # hash -> name table: add new names, drop names no longer referenced anywhere in the blob
    for h, c, n in new_go + new_mem:
        dc.hashes[h] = n
    dc.hashes = {h: n for h, n in dc.hashes.items() if struct.pack('<I', h) in new_blob}
    dc.blob = new_blob
    return delta


# ----------------------------------------------------------------------------- ESC scripts
def is_entities_script(t):
    return t.tag == 1 and t.data is not None and len(t.data) >= 0x24 and \
        t.data[:4] == b'\x04\x00\x01\x00' and t.data[4:16] == b'SCR_Entities'


def entity_strings(e):
    """Decode one SCR_Entities entity -> (name, [(operand_pos, string)], layout dict)."""
    hc, tc, ss = u16(e, 0x4E), u16(e, 0x50), u16(e, 0x52)
    hstart = 0x54
    sstart = hstart + hc * 4 + tc * 2          # stream: u16 0, opcodes, strings
    ostart = sstart + 2
    textstart = sstart + ss
    stream = e[ostart:textstart]
    refs, code_end = [], 0
    for i in range(hc):
        p = u16(e, hstart + i * 4 + 2)
        while True:
            op = stream[p]; p += 1
            if op >= 0x3A:
                break
            if op in (0x00, 0x01):
                p += 4
            elif 0x02 <= op <= 0x10:
                if op == 0x0E:
                    refs.append(p)
                p += 2
        code_end = max(code_end, p)
    name = zstr(e, textstart)
    strs = [(r, zstr(stream, u16(stream, r))) for r in refs]
    return name, strs, dict(hc=hc, tc=tc, ss=ss, ostart=ostart, textstart=textstart, code_end=code_end, stream=stream)


def patch_entity(e, renames):
    name, strs, L = entity_strings(e)
    if not any(s in renames for _, s in strs):
        return e, 0
    stream, code_end = L['stream'], L['code_end']
    for r, _ in strs:
        assert u16(stream, r) >= code_end, 'string inside code region?'
    newstream = bytearray(stream[:code_end])
    newoff, changed = {}, 0
    for r, s in sorted(strs, key=lambda x: u16(stream, x[0])):
        so = u16(stream, r)
        if so not in newoff:
            s2 = renames.get(s, s)
            changed += s2 != s
            newoff[so] = len(newstream)
            newstream += s2.encode('latin1') + b'\0'
    for r, _ in strs:
        struct.pack_into('<H', newstream, r, newoff[u16(stream, r)])
    tail = e[L['textstart']:]
    namelen = len(name) + 1
    assert tail[namelen:].strip(b'\0') == b'', 'unexpected data after entity name'
    ne = bytearray(e[:L['ostart']]) + newstream + tail[:namelen]
    ne += b'\0' * (align(len(ne), 4) - len(ne))
    struct.pack_into('<H', ne, 0x44, len(ne))
    struct.pack_into('<H', ne, 0x52, 2 + len(newstream))
    return bytes(ne), changed


def iter_entities(data):
    b = data[0x24:]
    pos = 0
    while pos + 0x54 <= len(b):
        size = u16(b, pos + 0x44)
        if size == 0:
            break
        yield b[pos:pos + size]
        pos += size


def patch_esc_tag(t, renames):
    out = bytearray(t.data[:0x24])
    changed = 0
    for e in iter_entities(t.data):
        ne, ch = patch_entity(e, renames)
        out += ne; changed += ch
    return bytes(out), changed


# ----------------------------------------------------------------------------- RSRCS
def rsrcs_names(t):
    return [t.data[i:i + 24].split(b'\0')[0].decode('latin1') for i in range(0, len(t.data), 24)]


def rsrcs_build(names):
    out = bytearray()
    for n in names:
        nb = n.encode('latin1')
        assert len(nb) < 24
        out += nb + b'\0' * (24 - len(nb))
    return bytes(out)


# ----------------------------------------------------------------------------- commands
def find_tag(tags, name):
    for t in tags:
        if t.name == name:
            return t
    return None


def cmd_dump(args):
    for extra in args.names or []:
        DC(read_wad(extra))
    tags = read_wad(args.wad)
    r = find_tag(tags, 'RSRCS')
    print(f'== {args.wad}: {len(tags)} tags')
    print('RSRCS (enemy WADs to load):', rsrcs_names(r) if r else '(none)')
    dc = DC(tags)
    print('DC_WAD top-level objects:', ', '.join(n for _, n in dc.top))
    if dc.imports:
        print('DC_WAD imports (offset -> external template):', dc.imports)
    pools = dc.pools()
    print(f'DC_WAD pools: {sum(p["kind"]=="go" for p in pools)} object pools, {sum(p["kind"]=="mem" for p in pools)} memory pools')
    seq = sorted(pools, key=lambda p: p['idx'])
    unres = [p for p in pools if ghash(p['name']) != p['hash']]
    if unres:
        print(f'   ({len(unres)} pool names could not be resolved from this WAD; pass more WADs via dump --names to learn them)')
    for p in seq:
        print(f"   {p['idx']:3d} {'GO ' if p['kind']=='go' else 'MEM'} {p['name']:24s} x{p['count']:<3d} (hash {p['hash']:08x})")
    if r:
        for en in rsrcs_names(r):
            go, mem = enemy_block(pools, en)
            if go is None:
                print(f'   !! {en}: no go{en} pool in DC_WAD')
            else:
                print(f'   block for {en}: N={go[0]["count"]} GO idx {go[0]["idx"]}..{go[-1]["idx"]}, MEM idx {mem[0]["idx"]}..{mem[-1]["idx"]}')
    print('Spawner scripts (ESC entities pushing CRT_/BRA_ strings):')
    for i, t in enumerate(tags):
        if is_entities_script(t):
            for e in iter_entities(t.data):
                name, strs, _ = entity_strings(e)
                crt = [s for _, s in strs if s.startswith('CRT_')]
                bra = [s for _, s in strs if s.startswith('BRA_')]
                if crt or bra:
                    print(f'   tag#{i} {t.name:28s} entity {name!r}: {sorted(set(crt))} {sorted(set(bra))}')


def cmd_swap(args):
    tags = read_wad(args.wad)
    donor = read_wad(args.donor)
    old, new = args.old, args.new
    renames = {f'CRT_{old}': f'CRT_{new}'}
    for r in args.rename or []:
        a, b = r.split('=', 1); renames[a] = b

    # 1. RSRCS
    r = find_tag(tags, 'RSRCS')
    names = rsrcs_names(r)
    if old not in names:
        raise SystemExit(f'RSRCS of {args.wad} = {names}; {old!r} not in it')
    if new in names:
        raise SystemExit(f'{new!r} already in RSRCS {names}')
    names[names.index(old)] = new
    r.data = rsrcs_build(names)
    print(f'RSRCS: {names}')

    # 2. DC_WAD pools
    ddc = DC(donor)
    dc = DC(tags)
    old_go, old_mem = enemy_block(dc.pools(), old)
    if old_go is None:
        raise SystemExit(f'go{old} pool not found in {args.wad}')
    new_go, new_mem = enemy_block(ddc.pools(), new)
    if new_go is None:
        raise SystemExit(f'go{new} pool not found in donor {args.donor}')
    n_old, n_donor = old_go[0]['count'], new_go[0]['count']
    n_new = args.count or n_old
    sgo, smem = scale_block(new_go, n_donor, n_new), scale_block(new_mem, n_donor, n_new)
    print(f'pools: removing {old} block ({len(old_go)} GO + {len(old_mem)} MEM, N={n_old}); '
          f'inserting {new} block from donor ({len(sgo)} GO + {len(smem)} MEM, donor N={n_donor} -> N={n_new})')
    for h, c, n in sgo + smem:
        print(f'      {n:24s} x{c}')
    delta = rebuild_pools(dc, old_go, old_mem, sgo, smem)
    dc.store()
    print(f'DC_WAD blob {len(dc.blob) - delta} -> {len(dc.blob)} bytes')

    # 3. ESC spawners
    total = 0
    for i, t in enumerate(tags):
        if is_entities_script(t):
            nd, ch = patch_esc_tag(t, renames)
            if ch:
                print(f'ESC tag#{i} {t.name}: {ch} string(s) renamed, {len(t.data)} -> {len(nd)} bytes')
                t.data = nd; total += ch
    if total == 0:
        print(f'WARNING: no spawner pushed CRT_{old}; nothing renamed in scripts')

    # behaviours still referenced next to the new creature
    bras = set()
    for t in tags:
        if is_entities_script(t):
            for e in iter_entities(t.data):
                _, strs, _ = entity_strings(e)
                ss = [s for _, s in strs]
                if f'CRT_{new}' in ss:
                    bras.update(s for s in ss if s.startswith('BRA_'))
    print(f'spawn behaviours used with CRT_{new}: {sorted(bras)}  <- must exist in R_{new.upper()}.WAD (use --rename to map)')

    out = write_wad(tags)
    open(args.output, 'wb').write(out)
    print(f'wrote {args.output} ({len(out)} bytes)')
    # sanity: re-read and dump block
    t2 = read_wad(args.output)
    dc2 = DC(t2)
    go, mem = enemy_block(dc2.pools(), new)
    assert go and mem, 'post-write check failed'
    print(f'verified: {new} block present in output (GO idx {go[0]["idx"]}..{go[-1]["idx"]}, MEM idx {mem[0]["idx"]}..{mem[-1]["idx"]})')


def cmd_selftest(args):
    ok = True
    for w in args.wads:
        raw = open(w, 'rb').read()
        tags = read_wad(w)
        rt = write_wad(tags)
        print(f'{w}: wad round-trip {"OK" if rt == raw else "MISMATCH"} ({len(tags)} tags)')
        ok &= rt == raw
        dc = DC(tags)
        for tg, builder, src in [(0x10, build_fields(dc.fields), 'fields'), (0x0D, build_pairs(dc.top), 'toplevel'),
                                 (0x0E, build_pairs(dc.imports), 'imports'), (0x0F, build_hashes(dc.hashes), 'hashes')]:
            same = builder == tags[dc.ti[tg]].data
            if tg == 0x0F and not same:
                print('   DC tag 0x0f (hashes) re-serialize differs: shipped table has bad string offsets, rebuilt cleanly')
            else:
                ok &= same
                print(f'   DC tag {tg:#04x} ({src}) re-serialize {"OK" if same else "MISMATCH"}')
        wfi = dc.wad_field(); woff = dc.fields[wfi][0]
        pools = dc.pools()
        n_go = sum(p['kind'] == 'go' for p in pools); n_mem = len(pools) - n_go
        same = wad_header(n_go, n_mem) == dc.blob[woff:woff + 8]
        ok &= same
        print(f'   WAD object header formula {"OK" if same else "MISMATCH"} (nGO={n_go}, nMem={n_mem})')
        # ESC: re-encode every entity with identity renames (forced) and compare
        bad = 0; n = 0; byp = 0
        for t in tags:
            if is_entities_script(t):
                for e in iter_entities(t.data):
                    name, strs, L = entity_strings(e)
                    n += 1
                    if strs:
                        ne, _ = patch_entity(e, {strs[0][1]: strs[0][1] + ''})  # no-op rename path
                        # force rebuild path
                        stream = L['stream']
                        ne2, _ = patch_entity(e, {'\0never': ''})
                        if ne != e:
                            hs, ost = entity_handlers(e)
                            if any(e[ost + st:ost + st + 3] == b'\x11\x38\x3a' for _, st in hs):
                                byp += 1        # bypassed handler: dead code after the forced exit is not reproduced
                            else:
                                bad += 1
        print(f'   ESC entities: {n} parsed, {bad} failed to re-encode identically' + (f' ({byp} bypassed entities skipped)' if byp else ''))
        ok &= bad == 0
    print('SELFTEST', 'PASSED' if ok else 'FAILED')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    d = sp.add_parser('dump'); d.add_argument('wad')
    d.add_argument('--names', action='append', help='other WADs whose hash tables help resolve names')
    d.set_defaults(fn=cmd_dump)
    s = sp.add_parser('swap'); s.add_argument('wad')
    s.add_argument('--old', required=True, help='enemy name as in RSRCS, e.g. Satyr10')
    s.add_argument('--new', required=True, help='replacement enemy name, e.g. Orders02')
    s.add_argument('--donor', required=True, help='a level WAD that already uses --new (source of its pool block)')
    s.add_argument('--count', type=int, help='max simultaneous instances N (default: same N as the old enemy)')
    s.add_argument('--rename', action='append', help='extra script string rename OLD=NEW (e.g. BRA_SpawnCeiling=BRA_Spawn)')
    s.add_argument('-o', '--output', required=True); s.set_defaults(fn=cmd_swap)
    t = sp.add_parser('selftest'); t.add_argument('wads', nargs='+'); t.set_defaults(fn=cmd_selftest)
    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)



# ============================================================================ spawner creature token
REMOVED = 'Nothing'      # pushed in place of CRT_<creature> to remove a spawner (confirmed in game)


def spawner_token(e, strs=None):
    """(token string, creature) for a spawner entity: ('CRT_Satyr10','Satyr10'), ('Nothing','Nothing')
    for a removed spawner, or (None, None) if the entity spawns nothing."""
    if strs is None:
        strs = entity_strings(e)[1]
    for _, x in strs:
        if x.startswith('CRT_'):
            return x, x[4:]
    if u16(e, 0x46) == 9 and any(x == REMOVED for _, x in strs):
        return REMOVED, REMOVED
    return None, None


def creature_token(c):
    return REMOVED if c == REMOVED else 'CRT_' + c


# ============================================================================ plan API (used by UI)
def level_info(tags):
    """Everything the UI needs about a level: RSRCS, creature blocks, encounters."""
    r = find_tag(tags, 'RSRCS')
    names = rsrcs_names(r) if r else []
    KNOWN_CREATURES.update(n.lower() for n in names)
    dc = DC(tags)
    pools = dc.pools()
    creatures = {}
    for en in names:
        go, mem = enemy_block(pools, en)
        creatures[en] = None if go is None else dict(
            n=go[0]['count'], go=[[p['hash'], p['count'], p['name']] for p in go],
            mem=[[p['hash'], p['count'], p['name']] for p in mem])
    encounters = []
    sc = spawner_counts(tags)
    for i, t in enumerate(tags):
        if is_entities_script(t):
            ents = []
            for e in iter_entities(t.data):
                name, strs, _ = entity_strings(e)
                ss = [s for _, s in strs]
                tok, cr = spawner_token(e, strs)
                bra = [s for s in ss if s.startswith('BRA_')]
                if cr:
                    c = sc.get((i, name), {})
                    ents.append(dict(name=name, crt=cr, removed=cr == REMOVED, bra=sorted(set(bra)), count=c.get('count'), alive=c.get('alive')))
            if ents:
                encounters.append(dict(tag=i, script=t.name, entities=ents))
    return dict(rsrcs=names, creatures=creatures, encounters=encounters, gates=level_gates(tags), gate_report=gate_report(tags),
                pools=[dict(idx=p['idx'], kind=p['kind'], name=p['name'], count=p['count']) for p in sorted(pools, key=lambda p: p['idx'])])


def apply_plan(tags, plan, creature_db, log=print):
    """plan = {assign: {"tag:entity": NewCreature}, counts: {Creature: N}, remove_unused: bool,
               bra_fallback: "BRA_Spawn", renames: {old: new}}
       creature_db = {Creature: {bra: [...], block: {n, go: [[h,c,name]], mem: [[h,c,name]]} or None}}"""
    assign = {tuple(k.split(':', 1)) if isinstance(k, str) else k: v for k, v in plan.get('assign', {}).items()}
    assign = {(int(a), b): v for (a, b), v in assign.items()}
    # --- summoners: make sure every summoner that will be in the level has its summon entities
    summons_plan = dict(plan.get('summons', {}))
    level_crts, summoner_host = set(), {}
    for i0, t0 in enumerate(tags):
        if is_entities_script(t0):
            for e0 in iter_entities(t0.data):
                nm0, st0, _ = entity_strings(e0)
                _, cr0 = spawner_token(e0, st0)
                if cr0:
                    pc = assign.get((i0, nm0), cr0)
                    level_crts.add(pc)
                    summoner_host.setdefault(pc, i0)          # first script that spawns this creature
    for summoner in sorted(level_crts):
        for ent in (creature_db.get(summoner) or {}).get('summons', []):
            if find_entity(tags, ent):
                continue
            tpl = ((creature_db.get(summoner) or {}).get('summon_templates') or {}).get(ent)
            if not tpl:
                log(f'WARNING: {summoner} calls {ent} but no donor template is known; its summon will not work')
                continue
            inject_entity(tags, bytes.fromhex(tpl['entity']), crt=summons_plan.get(ent), log=log,
                          host_tag=summoner_host.get(summoner))   # same script as the summoner: active whenever it is
    for ent, crt in summons_plan.items():          # retarget existing summon entities
        hit = find_entity(tags, ent)
        if hit:
            assign[(hit[0], ent)] = crt
    removed_keys = set(plan.get('remove', []))
    removed_set = {(int(k.split(':', 1)[0]), k.split(':', 1)[1]) for k in removed_keys}
    assign = {k: v for k, v in assign.items() if k not in removed_set}
    counts = dict(plan.get('counts', {}))
    fallback = plan.get('bra_fallback', 'BRA_Spawn')
    extra = dict(plan.get('renames', {}))

    # usage after assignment, and which creatures each replacement stands in for
    usage, replaces = {}, {}
    for i, t in enumerate(tags):
        if is_entities_script(t):
            for e in iter_entities(t.data):
                name, strs, _ = entity_strings(e)
                _, cr = spawner_token(e, strs)
                if cr and (i, name) not in removed_set:
                    cur = assign.get((i, name), cr)
                    if cur == REMOVED:
                        continue
                    usage[cur] = usage.get(cur, 0) + 1
                    if cur != cr and cr != REMOVED:
                        replaces.setdefault(cur, set()).add(cr)
    r = find_tag(tags, 'RSRCS')
    names = rsrcs_names(r) if r else []
    KNOWN_CREATURES.update(n.lower() for n in names)
    KNOWN_CREATURES.update(c.lower() for c in creature_db)
    dc = DC(tags)
    dc_changed = False
    # default N for a new creature: never below the pool size of what it replaces, so every
    # spawner that could get a slot before still can (destruction sensors depend on it)
    pools0 = dc.pools()
    sc = spawner_counts(tags)
    for c, olds in replaces.items():
        if c not in counts and (c not in names or enemy_block(pools0, c)[0] is None):
            n_old = [enemy_block(pools0, o)[0][0]['count'] for o in olds if enemy_block(pools0, o)[0]]
            blk = creature_db.get(c, {}).get('block')
            # concurrent demand = sum of 'alive' (or spawn count, or 1) over spawners assigned to c
            demand = 0
            for k, v in assign.items():
                if v == c:
                    info = sc.get(k, {})          # assign keys are (tag, name) tuples here
                    demand += info.get('alive') or info.get('count') or 1
            if n_old and blk:
                counts[c] = max(blk['n'], min(max(n_old), demand))
    # creatures that need a pool block: new ones, and ones listed in RSRCS without any pool
    # (e.g. Orders10 in the shipped RHOD10) once spawners are pointed at them
    added = [c for c in usage if c not in names or
             (c in replaces and enemy_block(pools0, c)[0] is None and creature_db.get(c, {}).get('block'))]
    removed = [c for c in names if c not in usage] if plan.get('remove_unused', True) else []

    for c in removed:
        go, mem = enemy_block(dc.pools(), c)
        if go:
            rebuild_pools(dc, go, mem, [], []); dc_changed = True
            log(f'pools: removed {c} block ({len(go)} GO + {len(mem)} MEM)')
        names.remove(c)
    for c in added:
        info = creature_db.get(c, {})
        blk = info.get('block')
        if not blk:
            raise ValueError(f'{c}: no donor pool block known (scan more levels)')
        n = counts.get(c, blk['n'])
        go = [dict(hash=h, count=k, name=nm) for h, k, nm in blk['go']]
        mem = [dict(hash=h, count=k, name=nm) for h, k, nm in blk['mem']]
        sgo, smem = scale_block(go, blk['n'], n), scale_block(mem, blk['n'], n)
        rebuild_pools(dc, [], [], sgo, smem); dc_changed = True
        if c not in names:
            names.append(c)
        log(f'pools: added {c} block ({len(sgo)} GO + {len(smem)} MEM, N={n}, donor N={blk["n"]})')
    for c, n in counts.items():
        if c in added or c in removed:
            continue
        go, mem = enemy_block(dc.pools(), c)
        if go and go[0]['count'] != n:
            rebuild_pools(dc, go, mem, scale_block(go, go[0]['count'], n), scale_block(mem, go[0]['count'], n)); dc_changed = True
            log(f'pools: rescaled {c} N {go[0]["count"]} -> {n}')
    if dc_changed:
        dc.store()
    if r and names != rsrcs_names(r):
        r.data = rsrcs_build(names)
    log(f'RSRCS: {names}')

    for key in removed_set:
        assign[key] = REMOVED                    # CRT_<creature> -> "Nothing": the spawner finds no creature
    if removed_set:
        log(f'removed {len(removed_set)} spawner(s): creature string set to "{REMOVED}"')
    total = 0
    for i, t in enumerate(tags):
        if not is_entities_script(t):
            continue
        out = bytearray(t.data[:0x24]); ch_tag = 0
        for e in iter_entities(t.data):
            name, strs, _ = entity_strings(e)
            ss = [s for _, s in strs]
            tok, cr = spawner_token(e, strs)
            ren = dict(extra)
            if cr and (i, name) in assign and assign[(i, name)] != cr:
                new = assign[(i, name)]
                ren[tok] = creature_token(new)
                avail = set(creature_db.get(new, {}).get('bra') or []) if new != REMOVED else set()
                for b in ss:
                    if b.startswith('BRA_') and avail and b not in avail:
                        ren[b] = fallback
            ne, ch = patch_entity(e, ren) if ren else (e, 0)
            out += ne; ch_tag += ch
        if ch_tag:
            t.data = bytes(out); total += ch_tag
            log(f'ESC tag#{i} {t.name}: {ch_tag} string(s) renamed')
    log(f'{total} script strings changed; RSRCS={names}')
    nsp = apply_spawns(tags, plan.get('spawns', {}), log=log) if plan.get('spawns') else 0
    ngates = apply_gates(tags, plan.get('gates', {}), log=log) if plan.get('gates') else 0
    nby = bypass_gates(tags, plan.get('bypass', []), log=log) if plan.get('bypass') else 0
    if plan.get('auto_total'):
        fix = {}
        for rep in gate_report(tags):
            cur = next(g['init'] for g in level_gates(tags) if g['var'] == rep['var'])
            if cur != rep['spawn_total'] and rep['var'] not in {int(v, 0) if isinstance(v, str) else int(v) for v in plan.get('bypass', [])}:
                fix[rep['var']] = rep['spawn_total']
        if fix:
            apply_gates(tags, fix, log=log); ngates += len(fix)
    for rep in gate_report(tags):
        if plan.get('bypass') and rep['var'] in {int(v, 0) if isinstance(v, str) else int(v) for v in plan['bypass']}:
            continue
        cur = next(g['init'] for g in level_gates(tags) if g['var'] == rep['var'])
        if cur != rep['spawn_total']:
            log(f"WARNING: total gate LevelData[{rep['var']:#x}] = {cur} but its spawners will produce {rep['spawn_total']} kills (== check): set it to {rep['spawn_total']}")
    return dict(rsrcs=names, added=added, removed=removed, strings_changed=total, gates_changed=ngates, spawns_changed=nsp, bypassed=nby, removed_spawners=len(removed_keys))


# ============================================================================ progression gates
OP_SIZES = {0x00: 4, 0x01: 4}
for _o in range(0x02, 0x11):
    OP_SIZES[_o] = 2
SCOPE_NAMES = {0: 'Entity', 1: 'Internal', 2: 'GlobalData', 3: 'LevelData'}
GET_TYPES = {0x02: 'float', 0x03: 'int', 0x04: 'bool', 0x05: 'string'}
SET_TYPES = {0x06: 'float', 0x07: 'int', 0x08: 'bool', 0x09: 'string'}
ENTITY_TYPE_LEVEL_DATA = 12


def walk_ops(stream, start):
    """yield (pos, opcode, operand bytes) until exit."""
    p = start
    while p < len(stream):
        op = stream[p]; p += 1
        if op >= 0x3A:
            yield p - 1, op, b''
            return
        n = OP_SIZES.get(op, 0)
        yield p - 1, op, stream[p:p + n]
        p += n


def entity_handlers(e):
    """[(handler id, stream offset of its first opcode)] + stream slice offsets."""
    hc, tc = u16(e, 0x4E), u16(e, 0x50)
    hstart = 0x54
    ostart = hstart + hc * 4 + tc * 2 + 2
    return [(u16(e, hstart + i * 4), u16(e, hstart + i * 4 + 2)) for i in range(hc)], ostart


def level_gates(tags):
    """Find every LevelData variable: initial constant (editable in place), who increments it,
    who compares it.  Returns a list of dicts sorted by variable index."""
    init, incr, reads, compares = {}, {}, {}, {}
    for ti, t in enumerate(tags):
        if not is_entities_script(t):
            continue
        epos = 0x24
        for e in iter_entities(t.data):
            name = entity_strings(e)[0]
            etype = u16(e, 0x46)
            handlers, ostart = entity_handlers(e)
            stream = e[ostart:]
            for hid, start in handlers:
                ops = list(walk_ops(stream, start))
                # initial value:  push_const ; set_scope LevelData[v]
                if etype == ENTITY_TYPE_LEVEL_DATA and len(ops) >= 2 and ops[1][1] in SET_TYPES:
                    scope, fid = u16(ops[1][2], 0) >> 12, u16(ops[1][2], 0) & 0xFFF
                    if scope == 3:
                        op0 = ops[0]
                        if op0[1] == 0x01:
                            val, kind = struct.unpack('<i', op0[2])[0], 'int'
                        elif op0[1] == 0x00:
                            val, kind = struct.unpack('<f', op0[2])[0], 'float'
                        elif op0[1] in (0x11, 0x12):
                            val, kind = op0[1] == 0x11, 'bool'
                        else:
                            continue
                        init[fid] = dict(var=fid, type=SET_TYPES[ops[1][1]], init=val, const_kind=kind,
                                         entity=name, handler=hid, tag=ti,
                                         file_off_in_tag=epos + ostart + op0[0] + 1 if kind != 'bool' else None)
                        continue
                # counters: get v ; push_int 1 ; sum ; set v
                codes = [o[1] for o in ops]
                for k in range(len(ops) - 3):
                    if codes[k] == 0x03 and codes[k + 1] == 0x01 and codes[k + 2] == 0x15 and codes[k + 3] == 0x07:
                        a, b = u16(ops[k][2], 0), u16(ops[k + 3][2], 0)
                        if a >> 12 == 3 and a == b:
                            incr.setdefault(a & 0xFFF, []).append(name)
                # compares: get a ; get b ; cmp
                for k in range(len(ops) - 2):
                    if codes[k] in GET_TYPES and codes[k + 1] in GET_TYPES and 0x2E <= codes[k + 2] <= 0x37:
                        a, b = u16(ops[k][2], 0), u16(ops[k + 1][2], 0)
                        if a >> 12 == 3 and b >> 12 == 3:
                            compares.setdefault(a & 0xFFF, set()).add((b & 0xFFF, name, codes[k + 2]))
                            compares.setdefault(b & 0xFFF, set()).add((a & 0xFFF, name, codes[k + 2]))
                for o in ops:
                    if o[1] in GET_TYPES and u16(o[2], 0) >> 12 == 3:
                        reads.setdefault(u16(o[2], 0) & 0xFFF, set()).add(name)
            epos += len(e)
    out = []
    for v in sorted(set(init) | set(incr) | set(reads)):
        d = dict(init.get(v, dict(var=v, type='?', init=None)))
        d['incremented_by'] = sorted(set(incr.get(v, [])))
        d['compared_with'] = sorted({o for o, _, _ in compares.get(v, set())})
        d['compared_in'] = sorted({n for _, n, _ in compares.get(v, set())})
        d['equality'] = any(op == 0x34 for _, _, op in compares.get(v, set()))   # 0x34 = int ==
        d['read_by'] = sorted(reads.get(v, set()))
        if d['incremented_by']:
            d['role'] = 'counter'
        elif d['compared_with'] and any(o in incr for o in d['compared_with']):
            d['role'] = 'threshold'
        elif d.get('type') == 'bool':
            d['role'] = 'flag'
        else:
            d['role'] = 'value'
        out.append(d)
    return out


def apply_gates(tags, values, log=print):
    """values: {var index (int or str): new number}. Patches the push_int/push_float operand in place."""
    gates = {g['var']: g for g in level_gates(tags)}
    n = 0
    for k, val in values.items():
        v = int(k, 0) if isinstance(k, str) else int(k)
        g = gates.get(v)
        if not g or g.get('file_off_in_tag') is None:
            raise ValueError(f'LevelData[{v:#x}] has no editable numeric initializer')
        t = tags[g['tag']]
        data = bytearray(t.data)
        off = g['file_off_in_tag']
        if g['const_kind'] == 'int':
            struct.pack_into('<i', data, off, int(val))
        else:
            struct.pack_into('<f', data, off, float(val))
        t.data = bytes(data); n += 1
        log(f"gate LevelData[{v:#x}] ({g['entity']} h{g['handler']}): {g['init']} -> {val}")
    return n


# ============================================================================ spawn counts
def entity_const_handlers(e):
    """{handler id: (value, offset_in_entity_of_operand)} for handlers that are just push_int N."""
    handlers, ostart = entity_handlers(e)
    stream = e[ostart:]
    out = {}
    for hid, start in handlers:
        ops = list(walk_ops(stream, start))
        if len(ops) >= 2 and ops[0][1] == 0x01 and ops[1][1] == 0x38:
            out[hid] = (struct.unpack('<i', ops[0][2])[0], ostart + ops[0][0] + 1)
    return out


def spawner_counts(tags):
    """{(tag, entity name): {count, alive, offsets}} for spawner entities (push CRT_)."""
    res = {}
    for ti, t in enumerate(tags):
        if not is_entities_script(t):
            continue
        epos = 0x24
        for e in iter_entities(t.data):
            name, strs, _ = entity_strings(e)
            tok, cr = spawner_token(e, strs)
            if cr:
                ch = entity_const_handlers(e)
                res[(ti, name)] = dict(removed=cr == REMOVED, count=ch.get(0, (None, None))[0], alive=ch.get(1, (None, None))[0],
                                       off_count=epos + ch[0][1] if 0 in ch else None,
                                       off_alive=epos + ch[1][1] if 1 in ch else None)
            epos += len(e)
    return res


def apply_spawns(tags, spawns, log=print):
    """spawns: {"tag:entity": {"count": n, "alive": m}} patched in place (push_int operands)."""
    sc = spawner_counts(tags)
    n = 0
    for k, v in spawns.items():
        ti, name = k.split(':', 1); ti = int(ti)
        info = sc.get((ti, name))
        if not info:
            raise ValueError(f'{k}: not a spawner')
        data = bytearray(tags[ti].data)
        for fld, off in (('count', info['off_count']), ('alive', info['off_alive'])):
            if fld in v and v[fld] is not None:
                if off is None:
                    log(f"spawn {fld} {name}: no such handler on this spawner, skipped")
                    continue
                struct.pack_into('<i', data, off, int(v[fld])); n += 1
                log(f"spawn {fld} {name}: {info[fld]} -> {v[fld]}")
        tags[ti].data = bytes(data)
    return n


def gate_report(tags, spawns_override=None):
    """For every '==' total gate: which spawners feed its counter and what the total should be."""
    gates = level_gates(tags)
    sc = spawner_counts(tags)
    sensors_script = {}
    for ti, t in enumerate(tags):
        if is_entities_script(t):
            for e in iter_entities(t.data):
                sensors_script[entity_strings(e)[0]] = ti
    out = []
    # the level total is the counter fed by the most death sensors; '==' gates on other counters
    # are per-wave checks (e.g. 'first kill of wave 4') and must not be forced to the spawn total
    maxinc = max([len(x['incremented_by']) for x in gates if x['role'] == 'counter'] or [0])
    for g in gates:
        if g['role'] != 'threshold' or not g.get('equality'):
            continue
        counters = [c for c in g['compared_with'] if any(x['var'] == c and x['role'] == 'counter' and len(x['incremented_by']) == maxinc for x in gates)]
        if not counters:
            continue
        cnt = next(x for x in gates if x['var'] == counters[0])
        scripts = {sensors_script.get(s) for s in cnt['incremented_by']} - {None}
        members = [(k, v) for k, v in sc.items() if k[0] in scripts]
        total = 0
        for (ti, name), v in members:
            if v.get('removed'):
                continue
            ov = (spawns_override or {}).get(f'{ti}:{name}', {})
            c = ov.get('count', v['count'])
            total += c if c is not None else 1
        out.append(dict(var=g['var'], init=g['init'], counter=cnt['var'], n_sensors=len(cnt['incremented_by']),
                        spawners=[f'{ti}:{name}' for (ti, name), _ in members], spawn_total=total))
    return out


# ============================================================================ gate bypass
def bypass_gates(tags, vars_, log=print):
    """Force every condition handler that compares one of `vars_` (LevelData indices) to return TRUE.
    The handler's first bytes become `push_bool TRUE ; pop_result ; exit` (11 38 3A); the rest of
    its bytecode is left in place but never executed. Entities that only *write* the variable
    (initialisers, counters) are untouched."""
    want = {int(v, 0) if isinstance(v, str) else int(v) for v in vars_}
    n = 0
    for ti, t in enumerate(tags):
        if not is_entities_script(t):
            continue
        data = bytearray(t.data)
        epos = 0x24
        changed = False
        for e in iter_entities(t.data):
            name = entity_strings(e)[0]
            handlers, ostart = entity_handlers(e)
            stream = e[ostart:]
            for hid, start in handlers:
                ops = list(walk_ops(stream, start))
                codes = [o[1] for o in ops]
                hit = False
                for k in range(len(ops) - 2):
                    if codes[k] in GET_TYPES and codes[k + 1] in GET_TYPES and 0x2E <= codes[k + 2] <= 0x37:
                        a, b = u16(ops[k][2], 0), u16(ops[k + 1][2], 0)
                        if (a >> 12 == 3 and (a & 0xFFF) in want) or (b >> 12 == 3 and (b & 0xFFF) in want):
                            hit = True
                if hit and (ops[-1][0] - start) >= 3:
                    off = epos + ostart + start
                    data[off:off + 3] = b'\x11\x38\x3a'
                    changed = True; n += 1
                    log(f'bypass: {name} h{hid} now always TRUE')
            epos += len(e)
        if changed:
            t.data = bytes(data)
    return n


# ============================================================================ spawner removal
def add_const_handler(e, hid, value):
    """Return a copy of entity `e` with a new handler `hid` whose code is `push_int value; pop_result; exit`.
    Header grows by 4 bytes (handler table), the code region by 7 bytes; string offsets are fixed."""
    name, strs, L = entity_strings(e)
    hc, tc = L['hc'], L['tc']
    handlers, ostart = entity_handlers(e)
    stream, code_end = L['stream'], L['code_end']
    newcode = bytearray(stream[:code_end]) + bytes([0x01]) + struct.pack('<i', int(value)) + b'\x38\x3a'
    shift = len(newcode) - code_end
    strings = bytearray(stream[code_end:])
    newstream = newcode + strings
    for r, _ in strs:                       # 0x0e operands point into the string area
        struct.pack_into('<H', newstream, r, u16(stream, r) + shift)
    hstart = 0x54
    table = bytearray(e[hstart:hstart + hc * 4]) + struct.pack('<HH', hid, code_end)
    targets = e[hstart + hc * 4:hstart + hc * 4 + tc * 2 + 2]
    tail = e[L['textstart']:L['textstart'] + len(name) + 1]
    ne = bytearray(e[:hstart]) + table + targets + newstream + tail
    ne += b'\0' * (align(len(ne), 4) - len(ne))
    struct.pack_into('<H', ne, 0x44, len(ne))
    struct.pack_into('<H', ne, 0x4E, hc + 1)
    struct.pack_into('<H', ne, 0x52, 2 + len(newstream))
    return bytes(ne)


def disable_spawners(tags, keys, log=print):
    """SUPERSEDED (count 0 does not stop spawns in game; apply_plan uses the "Nothing" token). Make spawners never spawn: handler 0 (count) and 1 (alive) set to 0, injected if missing."""
    want = {}
    for k in keys:
        ti, name = k.split(':', 1); want.setdefault(int(ti), set()).add(name)
    n = 0
    for ti, names in want.items():
        t = tags[ti]
        out = bytearray(t.data[:0x24])
        for e in iter_entities(t.data):
            nm = entity_strings(e)[0]
            if nm in names:
                ch = entity_const_handlers(e)
                ne = bytearray(e)
                for hid in (0, 1):
                    if hid in ch:
                        struct.pack_into('<i', ne, ch[hid][1], 0)
                    else:
                        ne = bytearray(add_const_handler(bytes(ne), hid, 0))
                log(f'removed spawner {nm}: spawn count 0 / alive 0' + ('' if 0 in ch else ' (handlers injected)'))
                e = bytes(ne); n += 1
            out += e
        t.data = bytes(out)
    return n


# ============================================================================ summoners
def summon_targets_from_dc(blob, fields):
    """Entity names a creature's tActionSpawn nodes call (creature WAD DC data)."""
    out = []
    for i, (off, name, ty) in enumerate(fields):
        if name.startswith('tActionSpawn'):
            end = fields[i + 1][0] if i + 1 < len(fields) else len(blob)
            for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{5,}', blob[off:end]):
                s = m.group().decode('latin1')
                if s not in out:
                    out.append(s)
    return out


def find_entity(tags, name):
    """(tag index, entity bytes) of the entity with this name, or None."""
    for ti, t in enumerate(tags):
        if is_entities_script(t):
            for e in iter_entities(t.data):
                if entity_strings(e)[0] == name:
                    return ti, e
    return None


def inject_entity(tags, entity, crt=None, log=print, host_tag=None):
    """Append a copied entity record to the level. It gets a fresh uid (= EntityCount), the
    level's EntityCount grows by one, its position is taken from an existing spawner of the
    host script, and optionally its CRT_ string is repointed. Returns (tag index, name)."""
    ec = next(t for t in tags if t.tag == 0)
    name = entity_strings(entity)[0]
    host = None
    if host_tag is not None:
        e0 = next((e for e in iter_entities(tags[host_tag].data) if spawner_token(e)[1]), None) or next(iter_entities(tags[host_tag].data))
        host = (host_tag, e0)
    for ti, t in enumerate(tags):            # fallback host: first script that has a creature spawner
        if host:
            break
        if is_entities_script(t):
            for e in iter_entities(t.data):
                if any(s.startswith('CRT_') for _, s in entity_strings(e)[1]):
                    host = (ti, e); break
        if host:
            break
    if host is None:
        host = next((ti, next(iter_entities(t.data))) for ti, t in enumerate(tags) if is_entities_script(t))
    ti, ref = host
    ne = bytearray(entity)
    ne[0:0x40] = ref[0:0x40]                 # world matrix of an existing spawner: a valid in-level spot
    uid = ec.size
    struct.pack_into('<H', ne, 0x48, uid)
    ne = bytes(ne)
    if crt:
        old = [s for _, s in entity_strings(ne)[1] if s.startswith('CRT_')]
        if old and old[0] != 'CRT_' + crt:
            ne, _ = patch_entity(ne, {old[0]: 'CRT_' + crt})
    tags[ti].data = tags[ti].data + ne
    ec.size = uid + 1
    log(f'summon entity {name} added to {tags[ti].name} as uid {uid}' + (f', spawns {crt}' if crt else '') + f'; EntityCount {uid} -> {uid + 1}')
    return ti, name


if __name__ == '__main__':
    main()
