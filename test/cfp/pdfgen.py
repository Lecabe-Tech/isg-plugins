"""Test-only: writes small PDFs with KNOWN text so CFP can be checked against ground truth.

Standard Helvetica fonts with WinAnsiEncoding (Portuguese accents work); one 1x1 image; no external libraries.
"""
from __future__ import annotations

import zlib


def _esc(text: str) -> bytes:
    raw = text.encode("cp1252")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class PdfDoc:
    def __init__(self, title: str = "", encrypt: bool = False):
        self.pages: list = []
        self.title = title

    def add_page(self, ops: list, width: int = 595, height: int = 842, rotate: int = 0):
        self.pages.append((ops, width, height, rotate))

    @staticmethod
    def text(x, y, text, font="F1", size=11):
        return {"t": text, "x": x, "y": y, "font": font, "size": size}

    @staticmethod
    def image(x, y, w=100, h=60):
        return {"img": True, "x": x, "y": y, "w": w, "h": h}

    def all_text(self) -> list:
        return [op["t"] for ops, *_ in self.pages for op in ops if "t" in op]

    def to_bytes(self) -> bytes:
        objs: list = []

        def add(data: bytes) -> int:
            objs.append(data)
            return len(objs)

        add(b"")  # 1 catalog (patched below)
        add(b"")  # 2 pages tree (patched)
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        img = add(b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream")
        info = add(b"<< /Title (" + _esc(self.title) + b") >>") if self.title else None
        kids = []
        for ops, width, height, rotate in self.pages:
            content = bytearray()
            for op in ops:
                if "t" in op:
                    content += b"BT /%s %g Tf 1 0 0 1 %g %g Tm (" % (op["font"].encode(), op["size"], op["x"], op["y"]) + _esc(op["t"]) + b") Tj ET\n"
                else:
                    content += b"q %g 0 0 %g %g %g cm /Im1 Do Q\n" % (op["w"], op["h"], op["x"], op["y"])
            stream = zlib.compress(bytes(content))
            cid = add(b"<< /Length %d /Filter /FlatDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
            objs[cid - 1] = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream"
            pid = add(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Rotate %d /Contents %d 0 R /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> /XObject << /Im1 %d 0 R >> >> >>"
                % (width, height, rotate, cid, f1, f2, img)
            )
            kids.append(pid)
        objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objs[1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids) + b"] /Count %d >>" % len(kids)
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for off in offsets:
            out += b"%010d 00000 n \n" % off
        trailer = b"trailer\n<< /Size %d /Root 1 0 R" % (len(objs) + 1)
        if info:
            trailer += b" /Info %d 0 R" % info
        out += trailer + b" >>\nstartxref\n%d\n%%%%EOF\n" % xref
        return bytes(out)

    def save(self, path) -> None:
        with open(path, "wb") as f:
            f.write(self.to_bytes())
