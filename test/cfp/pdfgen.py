"""Test-only: writes small PDFs with KNOWN text so CFP can be checked against ground truth.

Standard Helvetica fonts with WinAnsiEncoding (Portuguese accents work); one 1x1 image; no external libraries.
"""
from __future__ import annotations

import zlib


# Known image data for SPEC-004 tests (no imaging library is available, so the pixels are generated).
IM4_PIXELS = bytes((x + y * 3 + c * 50) % 256 for y in range(240) for x in range(240) for c in range(3))  # RGB 240x240, raw
IM5_JPEG = b"\xff\xd8\xff\xe0JFIF-test-bytes-not-decoded" + bytes(range(200)) + b"\xff\xd9"  # passthrough: copied byte for byte
IM7_INDEXES = bytes((x // 30) % 2 for y in range(240) for x in range(240))  # indexed 240x240, 2-colour palette


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
    def image(x, y, w=100, h=60, name="Im1"):
        return {"img": True, "x": x, "y": y, "w": w, "h": h, "name": name}

    @staticmethod
    def vector_chart(x, y, bars=130):
        """A chart drawn with filled rectangles (no image file): many painting operators."""
        nl = bytes([10])
        rects = b"".join(b"%g %g 3 %g re f" % (x + i * 4, y, 10 + (i * 7) % 90) + nl for i in range(bars))
        lines = (b"%g %g m %g %g l S" % (x, y, x + bars * 4, y) + nl) * 80
        return {"raw": rects + lines}

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
        img2 = add(b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 4 >>\nstream\n\x80\x80\x80\x80\nendstream")
        img3 = add(b"<< /Type /XObject /Subtype /Image /Width 3 /Height 3 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 9 >>\nstream\n" + b"\x80" * 9 + b"\nendstream")
        stream4 = zlib.compress(IM4_PIXELS)
        img4 = add(b"<< /Type /XObject /Subtype /Image /Width 240 /Height 240 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % len(stream4) + stream4 + b"\nendstream")
        img5 = add(b"<< /Type /XObject /Subtype /Image /Width 300 /Height 300 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % len(IM5_JPEG) + IM5_JPEG + b"\nendstream")
        img6 = add(b"<< /Type /XObject /Subtype /Image /Width 240 /Height 240 /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /CCITTFaxDecode /Length 4 >>\nstream\nABCD\nendstream")
        stream7 = zlib.compress(IM7_INDEXES)
        img7 = add(b"<< /Type /XObject /Subtype /Image /Width 240 /Height 240 /ColorSpace [/Indexed /DeviceRGB 1 <FF0000 0000FF>] /BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % len(stream7) + stream7 + b"\nendstream")
        info = add(b"<< /Title (" + _esc(self.title) + b") >>") if self.title else None
        kids = []
        for ops, width, height, rotate in self.pages:
            content = bytearray()
            for op in ops:
                if "raw" in op:
                    content += op["raw"]
                elif "t" in op:
                    content += b"BT /%s %g Tf 1 0 0 1 %g %g Tm (" % (op["font"].encode(), op["size"], op["x"], op["y"]) + _esc(op["t"]) + b") Tj ET\n"
                else:
                    content += b"q %g 0 0 %g %g %g cm /%s Do Q\n" % (op["w"], op["h"], op["x"], op["y"], op.get("name", "Im1").encode())
            stream = zlib.compress(bytes(content))
            cid = add(b"<< /Length %d /Filter /FlatDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
            objs[cid - 1] = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream"
            pid = add(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Rotate %d /Contents %d 0 R /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> /XObject << /Im1 %d 0 R /Im2 %d 0 R /Im3 %d 0 R /Im4 %d 0 R /Im5 %d 0 R /Im6 %d 0 R /Im7 %d 0 R >> >> >>"
                % (width, height, rotate, cid, f1, f2, img, img2, img3, img4, img5, img6, img7)
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
