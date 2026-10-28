"""Read Marathon 2 / Aleph One Shapes files (8-bit) and write shapes patches.

Layout follows Source_Files/RenderMain/shapes.cpp (load_collection,
load_collection_definition, load_high_level_shape, load_low_level_shape,
load_bitmap, load_clut, load_shapes_patch).
"""
import struct

def be16(b, o): return struct.unpack_from('>h', b, o)[0]
def ube16(b, o): return struct.unpack_from('>H', b, o)[0]
def be32(b, o): return struct.unpack_from('>i', b, o)[0]

ANIM_VIEWS = {1: 1, 10: 1, 3: 4, 4: 4, 9: 5, 5: 5, 11: 8, 2: 8, 8: 8}

class Collection:
    pass

def read_collection(data, index, true_color=True):
    """true_color: read the copy the game uses in 16/32-bit colour (and
    OpenGL), which has its own palette; falls back to the 8-bit copy."""
    hdr = 32 * index
    status, flags, offset, length, offset16, length16 = struct.unpack_from('>hhiiii', data, hdr)
    if true_color and offset16 != -1:
        offset = offset16
    if offset == -1:
        return None
    o = offset
    c = Collection()
    (c.version, c.type, c.flags, c.color_count, c.clut_count, c.color_table_offset,
     c.hls_count, c.hls_table, c.lls_count, c.lls_table, c.bitmap_count, c.bitmap_table,
     c.pixels_to_world) = struct.unpack_from('>hhhhhihihihih', data, o)
    # colors: each 8 bytes: flags(1) value(1) r g b (16 bit)
    c.cluts = []
    p = o + c.color_table_offset
    for t in range(c.clut_count):
        tab = []
        for i in range(c.color_count):
            fl, val, r, g, b = struct.unpack_from('>BBHHH', data, p)
            tab.append((fl, val, r, g, b))
            p += 8
        c.cluts.append(tab)
    c.hls = []
    for i in range(c.hls_count):
        so = o + be32(data, o + c.hls_table + 4 * i)
        typ, fl = struct.unpack_from('>hh', data, so)
        name = data[so + 4: so + 4 + 34].split(b'\0')[0].decode('latin-1')
        nviews, fpv, tpf, key, tm, tmp, s1, s2, s3, ptw, loop = struct.unpack_from('>hhhhhhhhhhh', data, so + 38)
        nv = ANIM_VIEWS.get(nviews, nviews)
        idx_off = so + 38 + 22 + 28
        llis = [be16(data, idx_off + 2 * j) for j in range(nv * fpv)]
        c.hls.append(dict(name=name, number_of_views=nviews, frames_per_view=fpv, ticks_per_frame=tpf,
                          key_frame=key, transfer_mode=tm, transfer_mode_period=tmp,
                          first_frame_sound=s1, key_frame_sound=s2, last_frame_sound=s3,
                          pixels_to_world=ptw, loop_frame=loop, lls=llis, type=typ, flags=fl, offset=so))
    c.lls = []
    for i in range(c.lls_count):
        so = o + be32(data, o + c.lls_table + 4 * i)
        fl, minlight, bm, ox, oy, kx, ky, wl, wr, wt, wb, wx0, wy0 = struct.unpack_from('>hihhhhhhhhhhh', data, so)
        c.lls.append(dict(flags=fl, minimum_light_intensity=minlight, bitmap_index=bm, origin_x=ox, origin_y=oy,
                          key_x=kx, key_y=ky, world_left=wl, world_right=wr, world_top=wt, world_bottom=wb,
                          world_x0=wx0, world_y0=wy0))
    c.bitmaps = []
    for i in range(c.bitmap_count):
        so = o + be32(data, o + c.bitmap_table + 4 * i)
        w, h, bpr, fl, depth = struct.unpack_from('>hhhhh', data, so)
        column = bool(fl & 0x8000)
        rows, rowlen = (w, h) if column else (h, w)
        p = so + 10 + 16 + (rows + 1) * 4
        pix = [[0] * w for _ in range(h)]
        for r in range(rows):
            if bpr == -1:
                first, last = be16(data, p), be16(data, p + 2)
                p += 4
                seg = data[p:p + last - first]
                p += last - first
                line = [0] * rowlen
                line[first:last] = seg
            else:
                line = list(data[p:p + bpr][:rowlen]); p += bpr
            for k in range(rowlen):
                if column: pix[k][r] = line[k]
                else: pix[r][k] = line[k]
        c.bitmaps.append(dict(width=w, height=h, flags=fl, bytes_per_row=bpr, column=column, pixels=pix))
    return c

# ---------------------------------------------------------------- writing
def tag(s): return struct.unpack('>i', s.encode())[0]

def bitmap_record(pixels, column=True, transparent=True):
    """Encode an 8-bit bitmap as Marathon stores sprites: column order,
    RLE (one opaque run per column, index 0 transparent)."""
    h = len(pixels); w = len(pixels[0])
    flags = (0x8000 if column else 0) | (0x4000 if transparent else 0)
    rows = w if column else h
    out = bytearray(struct.pack('>hhhHh', w, h, -1, flags, 8))
    out += bytes(16)
    out += bytes(4 * (rows + 1))  # row pointers, ignored by the loader
    for r in range(rows):
        line = [pixels[k][r] for k in range(h)] if column else pixels[r]
        nz = [i for i, v in enumerate(line) if v]
        if not nz:
            first = last = 0
        else:
            first, last = nz[0], nz[-1] + 1
        out += struct.pack('>hh', first, last) + bytes(line[first:last])
    return bytes(out)

def lls_record(d):
    return struct.pack('>hihhhhhhhhhhh', d['flags'], d['minimum_light_intensity'], d['bitmap_index'],
                       d['origin_x'], d['origin_y'], d['key_x'], d['key_y'], d['world_left'], d['world_right'],
                       d['world_top'], d['world_bottom'], d['world_x0'], d['world_y0']) + bytes(8)

def hls_record(d):
    name = d['name'].encode('latin-1')[:33]
    out = struct.pack('>hh', d['type'], d['flags']) + name + bytes(34 - len(name))
    out += struct.pack('>hhhhhhhhhhh', d['number_of_views'], d['frames_per_view'], d['ticks_per_frame'],
                       d['key_frame'], d['transfer_mode'], d['transfer_mode_period'], d['first_frame_sound'],
                       d['key_frame_sound'], d['last_frame_sound'], d['pixels_to_world'], d['loop_frame'])
    out += bytes(28)
    out += b''.join(struct.pack('>h', i) for i in d['lls'])
    return out

def write_patch(collection_index, bitmaps={}, lls={}, hls={}):
    """bitmaps: {index: bytes from bitmap_record}; lls/hls: {index: dict}."""
    out = bytearray(struct.pack('>ii', collection_index, 8))
    for i, rec in sorted(hls.items()):
        body = hls_record(rec)
        out += struct.pack('>iii', tag('hlsh'), i, len(body)) + body
    for i, rec in sorted(lls.items()):
        out += struct.pack('>ii', tag('llsh'), i) + lls_record(rec)
    for i, rec in sorted(bitmaps.items()):
        out += struct.pack('>iii', tag('bmap'), i, len(rec)) + rec
    out += struct.pack('>i', tag('endc'))
    return bytes(out)
