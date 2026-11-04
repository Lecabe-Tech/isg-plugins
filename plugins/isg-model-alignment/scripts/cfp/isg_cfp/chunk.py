"""Chunking (SPEC-003 2.4): by headings, with a size cap, always with page ranges and page markers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .organize import Block, PageResult

DEFAULT_MAX_CHARS = 12000
DEFAULT_MIN_CHARS = 1500
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
FLAG_LONG_PARAGRAPH = "parágrafo longo dividido"


@dataclass
class Chunk:
    number: int = 0
    path: list = field(default_factory=list)
    sections: list = field(default_factory=list)  # headings contained
    blocks: list = field(default_factory=list)
    continuation: bool = False
    flags: set = field(default_factory=set)

    @property
    def text_size(self) -> int:
        return sum(len(b.text) for b in self.blocks)

    @property
    def pages(self) -> list:
        return sorted({b.page for b in self.blocks if b.page})

    @property
    def page_range(self) -> str:
        p = self.pages
        return f"{p[0]}-{p[-1]}" if p else ""


def stream_blocks(results: list) -> list:
    """All blocks of the document in order; every page starts with a 'pagestart' block (so no page can be lost)."""
    out = []
    for pr in results:
        out.append(Block("pagestart", "", pr.number))
        out.extend(pr.blocks)
    return out


def _split_long(block: Block, cap: int) -> list:
    if len(block.text) <= cap:
        return [block]
    pieces, cur = [], ""
    for sentence in SENTENCE_SPLIT.split(block.text):
        while len(sentence) > cap:  # a single sentence longer than the cap: cut at whitespace
            cut = sentence.rfind(" ", 0, cap)
            cut = cut if cut > 0 else cap
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(sentence[:cut])
            sentence = sentence[cut:].lstrip(" ")
        if cur and len(cur) + 1 + len(sentence) > cap:
            pieces.append(cur)
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip() if cur else sentence
    if cur:
        pieces.append(cur)
    return [Block("para_split", p, block.page) for p in pieces]


def make_chunks(results: list, cap: int = DEFAULT_MAX_CHARS, minimum: int = DEFAULT_MIN_CHARS) -> list:
    stream = stream_blocks(results)

    # 1. sections by heading
    sections: list = []  # {"path": [...], "blocks": [...]}
    stack: list = []
    current = {"path": [], "blocks": []}
    sections.append(current)
    for b in stream:
        if b.type == "heading":
            while stack and stack[-1][0] >= b.level:
                stack.pop()
            stack.append((b.level, b.text))
            # a page marker right before the heading belongs to the new section (the page starts with the heading)
            carried = []
            while current["blocks"] and current["blocks"][-1].type == "pagestart":
                carried.insert(0, current["blocks"].pop())
            current = {"path": [t for _, t in stack], "blocks": carried + [b]}
            sections.append(current)
        else:
            current["blocks"].append(b)
    sections = [s for s in sections if s["blocks"]]

    # 2. split each section at paragraph boundaries under the cap
    chunks: list = []
    for sec in sections:
        cur = Chunk(path=list(sec["path"]), sections=[sec["path"][-1]] if sec["path"] else [])
        first = True
        for b in sec["blocks"]:
            for piece in _split_long(b, cap):
                size = len(piece.text)
                if cur.blocks and cur.text_size + size > cap and cur.text_size > 0:
                    chunks.append(cur)
                    cur = Chunk(path=list(sec["path"]), sections=[sec["path"][-1]] if sec["path"] else [], continuation=True)
                if piece.type == "para_split":
                    cur.flags.add(FLAG_LONG_PARAGRAPH)
                    piece = Block("para", piece.text, piece.page)
                cur.blocks.append(piece)
            first = False
        chunks.append(cur)

    # 3. merge small chunks into the next one of the same parent heading (empty ones always merge)
    merged: list = []
    i = 0
    while i < len(chunks):
        c = chunks[i]
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        if nxt is not None and (c.text_size == 0 or (c.text_size < minimum and c.path[:-1] == nxt.path[:-1] and c.text_size + nxt.text_size <= cap * 1.25)):
            nxt.blocks = c.blocks + nxt.blocks
            if c.sections:
                nxt.sections = c.sections + [s for s in nxt.sections if s not in c.sections]
            if not nxt.path:
                nxt.path = c.path
            nxt.flags |= c.flags
            nxt.continuation = c.continuation and nxt.continuation
        else:
            merged.append(c)
        i += 1
    # a trailing chunk without text merges into the previous one
    if len(merged) > 1 and merged[-1].text_size == 0:
        last = merged.pop()
        merged[-1].blocks.extend(last.blocks)

    for n, c in enumerate(merged, 1):
        c.number = n
    return merged
