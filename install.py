#!/usr/bin/env python3
"""Doom4Melee installer for RAGE 1 (Steam, 32-bit Rage.exe).

usage: py -3 install.py [game_dir] [--restore] [--dry-run]

Edits a few decls (text) in base/gameresources.resources by appending patched
blobs + a new index, and repoints the same rows in dlc/dlc3 to those blobs.
Backups: <file>.doom4melee-orig (16-byte header + LE u64 original length).
Re-running is safe: files are first truncated back to the original length.
"""
import json, os, struct, sys, zlib

DEFAULT = r"C:\Program Files (x86)\Steam\steamapps\common\RAGE"
HERE = os.path.dirname(os.path.abspath(__file__))
BK = ".doom4melee-orig"
OLD_BK = ".ragemod-orig"  # same format, written by the author's dev tooling


def die(msg):
    sys.exit("ERROR: " + msg)


def parse(d):
    """index bytes -> list of dicts (type, name, start, end, q=offset-field pos, rid)."""
    n = struct.unpack(">I", d[:4])[0]
    p = 4
    out = []
    for _ in range(n):
        st = p
        p += 4
        s = []
        for _ in range(3):
            l = struct.unpack("<I", d[p:p + 4])[0]
            s.append(bytes(d[p + 4:p + 4 + l]))
            p += 4 + l
        q = p
        x = struct.unpack(">I", d[q + 12:q + 16])[0]
        p += 36 + 24 * x
        out.append(dict(type=s[0].decode(), name=s[1].decode(), st=st, en=p, q=q,
                        rid=struct.unpack(">i", d[st:st + 4])[0],
                        off=struct.unpack(">I", d[q:q + 4])[0],
                        size=struct.unpack(">I", d[q + 4:q + 8])[0],
                        zsize=struct.unpack(">I", d[q + 8:q + 12])[0]))
    return out


def read_index(f, header=None):
    h = header if header is not None else (f.seek(0) or f.read(16))
    io, isz = struct.unpack(">II", h[4:12])
    f.seek(io)
    return io, isz, bytearray(f.read(isz))


def orig_info(path):
    """(16-byte header, original length) of the retail file, from our backup,
    else the dev backup, else the file itself (untouched)."""
    for ext in (BK, OLD_BK):
        if os.path.exists(path + ext):
            b = open(path + ext, "rb").read()
            return b[:16], struct.unpack("<Q", b[16:24])[0]
    with open(path, "rb") as f:
        return f.read(16), os.path.getsize(path)


def ensure_backup(path, keep_index=False):
    """keep_index: also store the retail index (needed for dlc3, whose index is
    rewritten in place and so cannot be recovered by truncating)."""
    bk = path + BK
    if os.path.exists(bk):
        return
    if os.path.exists(path + OLD_BK):
        open(bk, "wb").write(open(path + OLD_BK, "rb").read())
        if keep_index:
            print("WARNING: only a dev-tool backup exists for", path,
                  "- its index cannot be restored by --restore; verify the files in Steam if needed")
    else:
        with open(path, "rb") as f:
            h = f.read(16)
            ix = read_index(f, h)[2] if keep_index else b""
        open(bk, "wb").write(h + struct.pack("<Q", os.path.getsize(path)) + ix)


def blob(f, e):
    f.seek(e["off"])
    r = f.read(e["zsize"])
    return r if e["size"] == e["zsize"] else zlib.decompressobj(-15).decompress(r)


def nl(b):
    return b.decode("latin-1").replace("\r\n", "\n")


def apply_ops(name, text, ops):
    lines = text.splitlines(True)
    shift = 0
    for o in ops:
        a = o["at"] + shift
        if lines[a:a + len(o["old"])] != o["old"]:
            die("%s: edit at line %d does not match (game files differ from retail 9200?)"
                % (name, o["at"]))
        lines[a:a + len(o["old"])] = o["new"]
        shift += len(o["new"]) - len(o["old"])
    return "".join(lines).encode("latin-1")


def build(base, edits):
    """Return {name: (type, new_text_bytes)} from RETAIL text of base. Does not write."""
    h, ln = orig_info(base)
    out = {}
    with open(base, "rb") as f:
        _, _, idx = read_index(f, h)
        by = {(e["type"], e["name"]): e for e in parse(idx)}
        for name, ed in edits.items():
            e = by.get((ed["type"], name))
            if not e:
                die("%s not found in base index" % name)
            out[name] = (ed["type"], apply_ops(name, nl(blob(f, e)), ed["ops"]))
    return out


def restore(path):
    b = open(path + BK, "rb").read() if os.path.exists(path + BK) else None
    if b is None:
        return False
    with open(path, "r+b") as f:
        f.write(b[:16])
        f.truncate(struct.unpack("<Q", b[16:24])[0])
        if len(b) > 24:  # saved retail index (dlc3)
            f.seek(struct.unpack(">I", b[4:8])[0])
            f.write(b[24:])
    return True


def install(base, dlc3, edits):
    new = build(base, edits)  # also validates every edit before anything is written
    ensure_backup(base)
    ensure_backup(dlc3, keep_index=True)
    for p in (base, dlc3):
        restore(p)
    # --- base: append blobs, rewrite index
    with open(base, "r+b") as f:
        io, isz, idx = read_index(f)
        ents = parse(idx)
        by = {(e["type"], e["name"]): e for e in ents}
        f.seek(0, 2)
        end = f.tell()
        rep = {}
        for name, (t, raw) in new.items():
            e = by[(t, name)]
            c = zlib.compressobj(9, zlib.DEFLATED, -15)
            z = c.compress(raw) + c.flush()
            if len(z) == len(raw):
                die("%s: compressed size equals raw size (ambiguous)" % name)
            f.seek(end)
            f.write(z)
            rec = bytearray(idx[e["st"]:e["en"]])
            q = e["q"] - e["st"]
            rec[q:q + 12] = struct.pack(">III", end, len(raw), len(z))
            rep[e["st"]] = bytes(rec)
            e.update(off=end, size=len(raw), zsize=len(z))
            end += len(z)
        out = bytearray(struct.pack(">I", len(ents)))
        for e in ents:
            out += rep.get(e["st"], idx[e["st"]:e["en"]])
        f.seek(end)
        f.write(out)
        f.seek(4)
        f.write(struct.pack(">II", end, len(out)))
    newrows = {(t, n): by[(t, n)] for n, (t, _) in new.items()}
    # --- dlc3: repoint rows to base blobs (positive rid = blob lives in base file)
    with open(dlc3, "r+b") as f:
        io, isz, d = read_index(f)
        rows = parse(d)
        mods = set(newrows)
        mx = max(r["rid"] for r in rows if (r["type"], r["name"]) not in mods)
        i = 0
        for r in rows:
            k = (r["type"], r["name"])
            if k not in mods:
                continue
            i += 1
            b = newrows[k]
            d[r["st"]:r["st"] + 4] = struct.pack(">i", mx + i)
            d[r["q"]:r["q"] + 12] = struct.pack(">III", b["off"], b["size"], b["zsize"])
        f.seek(io)
        f.write(d)
    print("installed %d decls (dlc3 rows repointed: %d)" % (len(new), i))


def installed_text(base, dlc3, t, name):
    """Text the game would read now: dlc3 row (blob in base if rid>0), else base row."""
    with open(dlc3, "rb") as f:
        _, _, d = read_index(f)
    for r in parse(d):
        if r["name"] == name and r["type"] == t:
            if r["rid"] > 0:
                with open(base, "rb") as g:
                    return blob(g, r)
            with open(dlc3, "rb") as g:
                return blob(g, r)
    return None


def dry_run(base, dlc3, edits):
    new = build(base, edits)
    bad = 0
    for name, (t, raw) in new.items():
        cur = installed_text(base, dlc3, t, name)
        if cur is None:
            st = "edits apply (no dlc3 row)"
        elif nl(cur).encode("latin-1") == raw:
            st = "edits apply, equals current game text"
        elif nl(cur).encode("latin-1") == build_retail(base, t, name):
            st = "edits apply; mod not installed yet (game text is retail)"
        else:
            st = "edits apply; current game text DIFFERS from retail and from result"
            bad += 1
        print("%-36s %s" % (name, st))
    print("dry-run:", "FAIL" if bad else "OK", "(%d names)" % len(new))
    return bad


def build_retail(base, t, name):
    h, _ = orig_info(base)
    with open(base, "rb") as f:
        _, _, idx = read_index(f, h)
        for e in parse(idx):
            if e["type"] == t and e["name"] == name:
                return nl(blob(f, e)).encode("latin-1")


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    flags = {x for x in sys.argv[1:] if x.startswith("--")}
    game = a[0] if a else DEFAULT
    base = os.path.join(game, "base", "gameresources.resources")
    dlc3 = os.path.join(game, "dlc", "dlc3", "base", "gameresources.resources")
    for p in (base, dlc3):
        if not os.path.exists(p):
            die("missing " + p)
    if "--restore" in flags:
        for p in (base, dlc3):
            print(p, "restored" if restore(p) else "no backup, left alone")
        return
    edits = json.load(open(os.path.join(HERE, "edits.json")))
    if "--dry-run" in flags:
        sys.exit(1 if dry_run(base, dlc3, edits) else 0)
    install(base, dlc3, edits)


if __name__ == "__main__":
    main()
