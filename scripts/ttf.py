"""Minimal TrueType reader: glyph outlines as SVG path data, advances, cmap.

Stdlib only. Enough for static TTFs with a glyf table (simple and composite
glyphs). Used to draw Archivo text as paths, because GitHub serves README
images through a proxy that blocks web fonts.
"""
import struct


class Font:
    def __init__(self, path):
        self.d = d = open(path, "rb").read()
        n = struct.unpack(">H", d[4:6])[0]
        self.t = {}
        for i in range(n):
            tag, _, off, ln = struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])
            self.t[tag.decode()] = (off, ln)
        head = self.t["head"][0]
        self.upm = struct.unpack(">H", d[head + 18:head + 20])[0]
        self.loc_long = struct.unpack(">h", d[head + 50:head + 52])[0] == 1
        self.n_glyphs = struct.unpack(">H", d[self.t["maxp"][0] + 4:self.t["maxp"][0] + 6])[0]
        hhea = self.t["hhea"][0]
        self.n_hm = struct.unpack(">H", d[hhea + 34:hhea + 36])[0]
        self.cmap = self._cmap()
        self._paths = {}

    def _u16(self, o):
        return struct.unpack(">H", self.d[o:o + 2])[0]

    def _cmap(self):
        d, base = self.d, self.t["cmap"][0]
        n = self._u16(base + 2)
        recs = {}
        for i in range(n):
            pid, eid, off = struct.unpack(">HHI", d[base + 4 + 8 * i:base + 12 + 8 * i])
            recs[(pid, eid)] = base + off
        m = {}
        for key in ((3, 10), (0, 4), (3, 1), (0, 3)):
            if key not in recs:
                continue
            o = recs[key]
            fmt = self._u16(o)
            if fmt == 12:
                groups = struct.unpack(">I", d[o + 12:o + 16])[0]
                for g in range(groups):
                    s, e, gid = struct.unpack(">III", d[o + 16 + 12 * g:o + 28 + 12 * g])
                    for c in range(s, e + 1):
                        m[c] = gid + c - s
                return m
            if fmt == 4:
                seg = self._u16(o + 6) // 2
                ends, starts = o + 14, o + 16 + 2 * seg
                deltas, ranges = starts + 2 * seg, starts + 4 * seg
                for s in range(seg):
                    end, start = self._u16(ends + 2 * s), self._u16(starts + 2 * s)
                    delta = struct.unpack(">h", d[deltas + 2 * s:deltas + 2 * s + 2])[0]
                    ro = self._u16(ranges + 2 * s)
                    for c in range(start, end + 1):
                        if c == 0xFFFF:
                            continue
                        if ro == 0:
                            gid = (c + delta) & 0xFFFF
                        else:
                            gid = self._u16(ranges + 2 * s + ro + 2 * (c - start))
                            if gid:
                                gid = (gid + delta) & 0xFFFF
                        m[c] = gid
                return m
        raise ValueError("no usable cmap")

    def gid(self, ch):
        g = self.cmap.get(ord(ch), 0)
        if not g:
            raise ValueError(f"glyph missing for {ch!r}")
        return g

    def advance(self, gid):
        hm = self.t["hmtx"][0]
        i = min(gid, self.n_hm - 1)
        return self._u16(hm + 4 * i)

    def width(self, s, size, tracking=0.0):
        """Advance width of s in px at size, tracking in em."""
        if not s:
            return 0.0
        units = sum(self.advance(self.gid(c)) for c in s)
        return units * size / self.upm + tracking * size * (len(s) - 1)

    def _glyph_offset(self, gid):
        loca = self.t["loca"][0]
        if self.loc_long:
            a, b = struct.unpack(">II", self.d[loca + 4 * gid:loca + 4 * gid + 8])
        else:
            a, b = (x * 2 for x in struct.unpack(">HH", self.d[loca + 2 * gid:loca + 2 * gid + 4]))
        return a, b

    def _contours(self, gid, m=(1, 0, 0, 1, 0, 0)):
        """List of contours, each a list of (x, y, on_curve), transformed by m."""
        d = self.d
        a, b = self._glyph_offset(gid)
        if a == b:
            return []
        o = self.t["glyf"][0] + a
        nc = struct.unpack(">h", d[o:o + 2])[0]
        p = o + 10
        out = []
        if nc >= 0:
            ends = list(struct.unpack(f">{nc}H", d[p:p + 2 * nc]))
            p += 2 * nc
            p += 2 + self._u16(p)
            npts = ends[-1] + 1 if ends else 0
            flags = []
            while len(flags) < npts:
                f = d[p]
                p += 1
                flags.append(f)
                if f & 8:
                    r = d[p]
                    p += 1
                    flags.extend([f] * r)
            xs, ys = [], []
            for coords, short, same in ((xs, 2, 16), (ys, 4, 32)):
                v = 0
                for f in flags:
                    if f & short:
                        dv = d[p]
                        p += 1
                        v += dv if f & same else -dv
                    elif not f & same:
                        v += struct.unpack(">h", d[p:p + 2])[0]
                        p += 2
                    coords.append(v)
            a_, b_, c_, d_, e_, f_ = m
            start = 0
            for end in ends:
                out.append([(a_ * xs[i] + c_ * ys[i] + e_, b_ * xs[i] + d_ * ys[i] + f_, flags[i] & 1)
                            for i in range(start, end + 1)])
                start = end + 1
            return out
        while True:
            fl, g = struct.unpack(">HH", d[p:p + 4])
            p += 4
            if fl & 1:
                dx, dy = struct.unpack(">hh", d[p:p + 4])
                p += 4
            else:
                dx, dy = struct.unpack(">bb", d[p:p + 2])
                p += 2
            sa, sb, sc, sd = 1.0, 0.0, 0.0, 1.0
            if fl & 8:
                sa = sd = struct.unpack(">h", d[p:p + 2])[0] / 16384
                p += 2
            elif fl & 0x40:
                sa, sd = (v / 16384 for v in struct.unpack(">hh", d[p:p + 4]))
                p += 4
            elif fl & 0x80:
                sa, sb, sc, sd = (v / 16384 for v in struct.unpack(">hhhh", d[p:p + 8]))
                p += 8
            a_, b_, c_, d_, e_, f_ = m
            sub = (a_ * sa + c_ * sb, b_ * sa + d_ * sb, a_ * sc + c_ * sd, b_ * sc + d_ * sd,
                   a_ * dx + c_ * dy + e_, b_ * dx + d_ * dy + f_)
            out.extend(self._contours(g, sub))
            if not fl & 0x20:
                break
        return out

    def path(self, gid):
        """SVG path data in font units (y up)."""
        if gid in self._paths:
            return self._paths[gid]
        parts = []
        fmt = lambda v: str(round(v)) if abs(v - round(v)) < 0.05 else f"{v:.1f}"
        for c in self._contours(gid):
            if not c:
                continue
            n = len(c)
            # start on an on-curve point (or the midpoint of two off-curve points)
            s = next((i for i in range(n) if c[i][2]), None)
            if s is None:
                x0, y0 = (c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2
                start = (x0, y0)
                seq = c[1:] + c[:1]
            else:
                start = c[s][:2]
                seq = c[s + 1:] + c[:s]
            parts.append(f"M{fmt(start[0])} {fmt(start[1])}")
            ctrl = None
            for x, y, on in seq + [(start[0], start[1], 1)]:
                if on:
                    if ctrl:
                        parts.append(f"Q{fmt(ctrl[0])} {fmt(ctrl[1])} {fmt(x)} {fmt(y)}")
                        ctrl = None
                    else:
                        parts.append(f"L{fmt(x)} {fmt(y)}")
                else:
                    if ctrl:
                        mx, my = (ctrl[0] + x) / 2, (ctrl[1] + y) / 2
                        parts.append(f"Q{fmt(ctrl[0])} {fmt(ctrl[1])} {fmt(mx)} {fmt(my)}")
                    ctrl = (x, y)
            parts.append("Z")
        self._paths[gid] = "".join(parts)
        return self._paths[gid]
