# -*- coding: utf-8 -*-
"""
pdf_parser.py - Lightweight PDF → structured text extractor
- Uses PyMuPDF (fitz) to extract title, sections, paragraphs
- Heuristics for figures/tables/equations and key sentences
- Outputs a dict; caller may persist to JSON
"""
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import re
from pathlib import Path
import fitz  # PyMuPDF


@dataclass
class Section:
    title: str
    level: int
    content: str
    pages: List[int]


def guess_title(doc: fitz.Document) -> str:
    # pick largest font text on first 1-2 pages as title
    try:
        page = doc[0]
        blocks = page.get_text("dict").get("blocks", [])
        candidates = []
        for b in blocks:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    txt = s.get("text", "").strip()
                    if len(txt) > 5:
                        candidates.append((s.get("size", 0), txt))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1][:256]
    except Exception:
        pass
    return "Untitled Paper"


def extract_sections(doc: fitz.Document) -> List[Section]:
    # simple heuristic: headings as lines with ALL CAPS or numbered like 1., 1.1 etc
    sections: List[Section] = []
    current = Section(title="Introduction", level=1, content="", pages=[0])
    for i, page in enumerate(doc):
        text = page.get_text("text")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for ln in lines:
            if re.match(r"^(\d+\.){0,2}\d+\s+.+$", ln) or (ln.isupper() and len(ln) < 120):
                # start new section
                if current.content.strip():
                    sections.append(current)
                lvl = 1 if re.match(r"^\d+\.\s", ln) else 2
                current = Section(title=ln, level=lvl, content="", pages=[i])
            else:
                # append to current
                current.content += ln + "\n"
    if current.content.strip():
        sections.append(current)
    return sections


def detect_figures_tables(text: str) -> Dict[str, List[str]]:
    figures = re.findall(r"(?i)(figure\s*\d+[:\.]\s[^\n]+)", text)
    tables = re.findall(r"(?i)(table\s*\d+[:\.]\s[^\n]+)", text)
    return {"figures": figures[:20], "tables": tables[:20]}


def detect_equations(text: str) -> List[str]:
    # heuristics: lines with many math symbols
    equations = []
    for ln in text.splitlines():
        if sum(ch in "=+−-*/<>∑∏∫√≈≠≤≥()[]{}|" for ch in ln) >= 3 and len(ln) > 10:
            equations.append(ln)
    return equations[:20]


def key_sentences_from_abstract(abstract: str) -> List[str]:
    sents = re.split(r"(?<=[.!?])\s+", abstract.strip())
    # keep 3 most informative sentences by keywords
    kw = ["we ", "our ", "propose", "introduce", "state-of-the-art", "significant", "improve", "outperform"]
    scored = []
    for s in sents:
        score = sum(1 for k in kw if k in s.lower()) + len(s) / 200.0
        scored.append((score, s))
    scored.sort(reverse=True)
    return [s for _, s in scored[:3]]


def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    doc = fitz.open(pdf_path)
    title = guess_title(doc)
    sections = extract_sections(doc)
    full_text = "\n".join(sec.content for sec in sections)
    ft = detect_figures_tables(full_text)
    eqs = detect_equations(full_text)
    abstract = ""
    # try find abstract in first section
    for s in sections[:2]:
        m = re.search(r"(?i)abstract\s*\n(.+?)\n\s*keywords|(?i)abstract\s*\n(.+)$", s.content, re.S)
        if m:
            abstract = (m.group(1) or m.group(2) or "").strip()[:2000]
            break
    paper_struct = {
        "title": title,
        "abstract": abstract,
        "sections": [asdict(s) for s in sections],
        "figures": ft["figures"],
        "tables": ft["tables"],
        "equations": eqs,
    }
    if not abstract:
        # fallback: first 5 lines of first section
        if sections:
            ab = " ".join(sections[0].content.splitlines()[:5])
            paper_struct["abstract"] = ab[:800]
    return paper_struct
