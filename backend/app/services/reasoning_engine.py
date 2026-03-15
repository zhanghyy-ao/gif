# -*- coding: utf-8 -*-
"""
reasoning_engine.py - CoT/ToT-style structured reasoning for director planning
Notes:
- Implements structured, JSON-only reasoning scaffolds (no free-form chain text exposed via API)
- CoT: produce a draft plan (insights, goals, 3-shot storyboard)
- ToT: generate multiple candidates, score with criteria, select best
- Critique: optional refinement pass for clarity/consistency/discipline fit
- Backed by DashScope text-generation if available; falls back to heuristics
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import json
import requests

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
GEN_URL = f"{BASE_URL}/services/aigc/text-generation/generation"


def _dashscope_generate(prompt: str, model: str = "qwen-max") -> Optional[str]:
    if not DASHSCOPE_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "message"}
    }
    try:
        r = requests.post(GEN_URL, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            return None
        data = r.json()
        # message-style format
        content = data.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content")
        if isinstance(content, list):
            # multi-part content; join text parts
            text = "\n".join([c.get("text", "") for c in content if isinstance(c, dict)])
        else:
            text = str(content)
        return text
    except Exception:
        return None


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        return None


class DirectorReasoner:
    """CoT/ToT scaffolds for director planning (JSON-only outputs)."""

    def __init__(self, discipline_style_desc: Optional[str] = None):
        self.discipline_style_desc = discipline_style_desc or ""

    def cot_plan(self, paper_struct: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce a structured plan:
        - key_insights: list[str]
        - scene_goals: list[str]
        - shots: list[ {title, subject, action, env, camera, motion, notes} ] (3 items)
        """
        title = paper_struct.get("title", "Untitled")
        abstract = paper_struct.get("abstract", "")
        nodes = graph.get("nodes", []) if graph else []
        top_names = [n.get("name") for n in nodes[:5] if n.get("name")]

        base_prompt = f"""
You are a director-planner for a short academic video. Return STRICT JSON only.
Task: Convert paper understanding into a 3-shot plan.
Discipline style hint: {self.discipline_style_desc}
Fields required:
{{
  "key_insights": ["..."],
  "scene_goals": ["..."],
  "shots": [
    {{"title":"...","subject":"...","action":"...","env":"...","camera":"...","motion":"...","notes":["...","..."]}},
    {{...}},
    {{...}}
  ]
}}
Paper title: {title}
Abstract: {abstract[:1000]}
Key terms: {top_names}
Constraints: concise, technical clarity, minimal text overlays, coherent transitions.
Output JSON only.
""".strip()
        txt = _dashscope_generate(base_prompt) or ""
        data = _safe_json_parse(txt) or {}
        # fallback heuristic if LLM unavailable
        if not data:
            data = {
                "key_insights": top_names[:3] or ["Core idea"],
                "scene_goals": top_names[1:4] or ["Clarity"],
                "shots": [
                    {"title": "Problem", "subject": title, "action": "Introduce context", "env": "Clean background", "camera": "Medium → push-in", "motion": "Keywords appear", "notes": []},
                    {"title": "Method", "subject": top_names[0] if top_names else "Approach", "action": "Show pipeline", "env": "Blocks+arrows", "camera": "Top-down to 3/4", "motion": "Sequential reveal", "notes": []},
                    {"title": "Results", "subject": "Findings", "action": "Compare before/after", "env": "Split view", "camera": "Slow pan", "motion": "Highlight improvements", "notes": []},
                ]
            }
        return data

    def tot_select(self, paper_struct: Dict[str, Any], graph: Dict[str, Any], k: int = 3) -> Dict[str, Any]:
        """
        Generate k candidate plans and select the best by scoring criteria.
        Returns the winning plan dict with added {"score": float}.
        """
        candidates: List[Dict[str, Any]] = []
        for i in range(k):
            plan = self.cot_plan(paper_struct, graph)
            score = self._score_plan(plan)
            plan["score"] = score
            candidates.append(plan)
        # pick the max score
        best = max(candidates, key=lambda d: d.get("score", 0.0)) if candidates else {}
        # hide scores/diagnostics from API; keep only core fields
        return {
            "key_insights": best.get("key_insights", []),
            "scene_goals": best.get("scene_goals", []),
            "shots": best.get("shots", [])
        }

    def _score_plan(self, plan: Dict[str, Any]) -> float:
        # simple scoring: presence/length balance & motion/camera variety
        shots = plan.get("shots", [])
        variety = len({s.get("camera") for s in shots if s.get("camera")}) + len({s.get("motion") for s in shots if s.get("motion")})
        coverage = len(plan.get("key_insights", [])) + len(plan.get("scene_goals", []))
        return 0.6 * variety + 0.4 * coverage

    def refine_prompt_notes(self, notes: List[str], max_notes: int = 10) -> List[str]:
        # optional light refinement (deduplicate, trim)
        seen, out = set(), []
        for n in notes:
            t = n.strip()
            if t and t not in seen:
                out.append(t)
                seen.add(t)
        return out[:max_notes]
