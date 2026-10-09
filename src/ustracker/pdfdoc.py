"""2.8.0 — PDF simples (A4) sem biblioteca externa: texto Helvetica, linhas, retângulos e QR Code.

Coordenadas em pontos a partir do canto SUPERIOR esquerdo (y cresce para baixo). Texto em
WinAnsi (cp1252), que cobre os acentos do português.
"""
from __future__ import annotations

import zlib

W, H = 595.28, 841.89
# larguras Helvetica (1/1000 em) dos caracteres usados em valores e datas, para alinhar à direita
_WIDTH = {**{d: 556 for d in '0123456789'}, ' ': 278, ',': 278, '.': 278, '/': 278, '-': 333, 'R': 722, '$': 556, ':': 278}


def _esc(text: str) -> bytes:
    raw = str(text).encode('cp1252', 'replace')
    return raw.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def text_width(text: str, size: float) -> float:
    return sum(_WIDTH.get(c, 556 if c.isupper() else 500) for c in str(text)) * size / 1000


class PDF:
    def __init__(self, title: str = 'UStracker'):
        self.title = title
        self.pages: list[list[bytes]] = []
        self.page()

    def page(self) -> None:
        self.pages.append([])

    def _op(self, s: str | bytes) -> None:
        self.pages[-1].append(s if isinstance(s, bytes) else s.encode('ascii'))

    def text(self, x: float, y: float, text: str, size: float = 10, bold: bool = False, color=(0.09, 0.13, 0.2), align: str = 'left') -> None:
        if align == 'right':
            x -= text_width(text, size)
        r, g, b = color
        self._op(f'BT {r:.3f} {g:.3f} {b:.3f} rg /{"F2" if bold else "F1"} {size:.1f} Tf {x:.2f} {H - y:.2f} Td ('.encode('ascii') + _esc(text) + b') Tj ET')

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float = 0.6, color=(0.86, 0.89, 0.92)) -> None:
        r, g, b = color
        self._op(f'{r:.3f} {g:.3f} {b:.3f} RG {width:.2f} w {x1:.2f} {H - y1:.2f} m {x2:.2f} {H - y2:.2f} l S')

    def rect(self, x: float, y: float, w: float, h: float, fill=(0.95, 0.96, 0.98)) -> None:
        r, g, b = fill
        self._op(f'{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {H - y - h:.2f} {w:.2f} {h:.2f} re f')

    def qr(self, matrix: list[list[bool]], x: float, y: float, size: float) -> None:
        n = len(matrix)
        cell = size / n
        ops = ['0 0 0 rg']
        for row_i, row in enumerate(matrix):
            col = 0
            while col < n:
                if row[col]:
                    start = col
                    while col < n and row[col]:
                        col += 1
                    ops.append(f'{x + start * cell:.3f} {H - y - (row_i + 1) * cell:.3f} {(col - start) * cell:.3f} {cell:.3f} re')
                else:
                    col += 1
        ops.append('f')
        self._op('\n'.join(ops))

    def output(self) -> bytes:
        objs: list[bytes] = []
        n_pages = len(self.pages)
        page_ids = [5 + 2 * i for i in range(n_pages)]
        objs.append(b'<< /Type /Catalog /Pages 2 0 R >>')
        objs.append(f'<< /Type /Pages /Kids [{" ".join(f"{p} 0 R" for p in page_ids)}] /Count {n_pages} >>'.encode())
        objs.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
        objs.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
        for i, ops in enumerate(self.pages):
            body = zlib.compress(b'\n'.join(ops))
            objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> '
                        f'/Contents {page_ids[i] + 1} 0 R >>'.encode())
            objs.append(f'<< /Length {len(body)} /Filter /FlateDecode >>\nstream\n'.encode() + body + b'\nendstream')
        out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = []
        for i, obj in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
        xref = len(out)
        out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
        for off in offsets:
            out += f'{off:010d} 00000 n \n'.encode()
        out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(out)
