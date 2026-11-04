"""Minimal PNG encoder (standard library only): 8-bit gray, RGB and indexed images (SPEC-004 REQ-SEX-01)."""
from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(width: int, height: int, samples: bytes, mode: str, palette: bytes | None = None) -> bytes:
    """mode: 'L' (gray), 'RGB' or 'P' (indexed, needs palette = RGB triples). samples: 8-bit, row after row, no padding."""
    channels = {"L": 1, "RGB": 3, "P": 1}[mode]
    color_type = {"L": 0, "RGB": 2, "P": 3}[mode]
    stride = width * channels
    if width <= 0 or height <= 0 or len(samples) != stride * height:
        raise ValueError("amostras não batem com as dimensões")
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter: none
        raw += samples[row * stride:(row + 1) * stride]
    out = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    if mode == "P":
        if not palette:
            raise ValueError("paleta ausente")
        out += _chunk(b"PLTE", palette[:768])
    out += _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b"")
    return out


def cmyk_to_rgb(samples: bytes) -> bytes:
    """Naive CMYK -> RGB (good enough to read text and charts; colours are approximate)."""
    out = bytearray(len(samples) // 4 * 3)
    j = 0
    for i in range(0, len(samples) - 3, 4):
        c, m, y, k = samples[i], samples[i + 1], samples[i + 2], samples[i + 3]
        out[j] = 255 - min(255, c + k)
        out[j + 1] = 255 - min(255, m + k)
        out[j + 2] = 255 - min(255, y + k)
        j += 3
    return bytes(out)


def expand_1bit_gray(data: bytes, width: int, height: int) -> bytes:
    """1-bit rows (padded to bytes) -> 8-bit gray."""
    row_bytes = (width + 7) // 8
    if len(data) < row_bytes * height:
        raise ValueError("dados curtos")
    out = bytearray()
    for r in range(height):
        row = data[r * row_bytes:(r + 1) * row_bytes]
        for x in range(width):
            out.append(255 if (row[x >> 3] >> (7 - (x & 7))) & 1 else 0)
    return bytes(out)


def decode_png_samples(png: bytes) -> tuple:
    """Reads back PNGs written by encode_png (filter 0 only): (width, height, color_type, samples). Used by Q12 and tests."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("assinatura PNG ausente")
    pos, idat, w, h, ct = 8, b"", 0, 0, 0
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        kind = png[pos + 4:pos + 8]
        body = png[pos + 8:pos + 8 + n]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != struct.unpack(">I", png[pos + 8 + n:pos + 12 + n])[0]:
            raise ValueError("crc inválido")
        if kind == b"IHDR":
            w, h, _bd, ct = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * {0: 1, 2: 3, 3: 1}[ct]
    out = b"".join(raw[1 + r * (stride + 1):(r + 1) * (stride + 1)] for r in range(h))
    if len(out) != stride * h:
        raise ValueError("dados incompletos")
    return w, h, ct, out
