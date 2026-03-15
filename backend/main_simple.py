# -*- coding: utf-8 -*-
"""
main_simple.py — No FastAPI. Edit the variables below and run directly.
Pipeline: PDF → parse → KG → (discipline + CoT/ToT) → director prompt → Qwen T2V → MP4+GIF
Requirements: set DASHSCOPE_API_KEY in environment; install backend/requirements.txt
Usage:  python backend/main_simple.py
"""
import os
import json
from pathlib import Path
import asyncio

# ====== EDIT THESE ======
PDF_PATH = r"C:\path\to\your\paper.pdf"  # ← 修改为你的论文PDF路径
DISCIPLINE = ""  # 例如: "physics", "biology", "cs_ml", "economics", "medicine", "social_science", "mathematics"; 留空则默认
REASONING = "tot"  # 可选: "tot" | "cot" | "none"
STYLE = "educational"  # 风格: educational/cinematic/3d/animation/realistic
DURATION = 6
FPS = 24
WIDTH = 720
LANGUAGE = "en"
# ========================

# Paths
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.getenv("OUTPUT_DIR", ROOT / "outputs"))

# Imports from services
from app.services.pdf_parser import parse_pdf
from app.services.kg_builder import build_graph
from app.services.discipline_adapter import DisciplineAdapter
from app.services.reasoning_engine import DirectorReasoner
from app.services.enhanced_video_prompt_builder import EnhancedVideoPromptBuilder
from app.services.qwen_video_generator import QwenVideoGenerator


def check_env():
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is not set. Please set it in your environment.")


def ensure_dirs(stem: str):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "text" / stem).mkdir(parents=True, exist_ok=True)
    (OUT / "videos").mkdir(parents=True, exist_ok=True)


async def run_once():
    check_env()

    pdf = Path(PDF_PATH)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")
    stem = pdf.stem
    ensure_dirs(stem)

    # 1) parse
    paper = parse_pdf(str(pdf))
    # 2) KG
    graph = build_graph(paper)

    # persist text artifacts
    (OUT / "text" / stem / "paper_struct.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "text" / stem / "graph.json").write_text(json.dumps(graph.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) discipline + reasoning
    adapter = DisciplineAdapter()
    nodes = graph.model_dump().get("nodes", [])
    top_names = [n.get("name") for n in nodes[:5] if n.get("name")]
    base_notes = [f"Emphasize concept: {name}" for name in top_names[:3]]

    adapted = adapter.adapt(DISCIPLINE or "", STYLE, base_notes)
    reasoner = DirectorReasoner(discipline_style_desc=adapted.get("style_desc"))
    if REASONING == "cot":
        plan = reasoner.cot_plan(paper, graph.model_dump())
    elif REASONING == "none":
        plan = {"key_insights": top_names[:3], "scene_goals": top_names[1:4], "shots": []}
    else:
        plan = reasoner.tot_select(paper, graph.model_dump(), k=3)

    storyboard_notes = reasoner.refine_prompt_notes(adapted["notes"] + plan.get("scene_goals", []))

    # 4) director prompt
    prompt = EnhancedVideoPromptBuilder.build_director_prompt(
        paper_title=paper.get("title", "Untitled"),
        abstract=paper.get("abstract", ""),
        concept_name=top_names[0] if top_names else "Core Idea",
        key_claims=plan.get("key_insights", [])[:3],
        scene_goals=plan.get("scene_goals", [])[:3],
        duration_sec=DURATION,
        style=adapted["style"],
        resolution=f"{WIDTH*16//9}x{WIDTH}",
        fps=FPS,
        language=LANGUAGE,
        storyboard_notes=storyboard_notes,
    )
    (OUT / "text" / stem / "prompt.txt").write_text(prompt, encoding="utf-8")

    # 5) Qwen → MP4 + GIF
    gen = QwenVideoGenerator()
    result = await gen.generate_video_from_concept(
        concept_name=top_names[0] if top_names else "Core Idea",
        description=paper.get("abstract", ""),
        visual_type="diagram",
        output_dir=str(OUT / "videos"),
        duration=DURATION,
        resolution="720p",
        style=adapted["style"],
        override_prompt=prompt,
        gif_fps=FPS,
        gif_width=WIDTH,
    )

    print(json.dumps({
        "pdf": str(pdf),
        "discipline": DISCIPLINE,
        "reasoning": REASONING,
        "style": STYLE,
        "result": result
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(run_once())
    except Exception as e:
        print(f"[ERROR] {e}")
        raise
