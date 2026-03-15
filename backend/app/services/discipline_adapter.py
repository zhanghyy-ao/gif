# -*- coding: utf-8 -*-
"""
discipline_adapter.py - Adapt prompts and storyboard notes to specific disciplines
"""
from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import json

PRESETS_PATH = Path(__file__).resolve().parents[1] / "resources" / "discipline_presets.json"

class DisciplineAdapter:
    def __init__(self):
        self.presets = {}
        if PRESETS_PATH.exists():
            self.presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))

    def list_disciplines(self) -> List[str]:
        return list(self.presets.keys())

    def adapt(self, discipline: str, base_style: str, storyboard_notes: List[str]) -> Dict[str, Any]:
        p = self.presets.get(discipline)
        if not p:
            return {"style": base_style, "notes": storyboard_notes, "palette": None, "shot_titles": None, "style_desc": None}
        notes = storyboard_notes + p.get("notes_templates", [])
        # de-duplicate while preserving order
        seen = set()
        dedup_notes = []
        for n in notes:
            if n not in seen:
                dedup_notes.append(n)
                seen.add(n)
        return {
            "style": base_style,
            "notes": dedup_notes[:10],
            "palette": p.get("palette"),
            "shot_titles": p.get("shot_titles"),
            "style_desc": p.get("style_desc"),
        }
