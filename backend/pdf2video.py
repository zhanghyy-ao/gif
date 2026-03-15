#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf2video.py - One-shot: PDF → parse → graph → director prompt → Qwen → MP4+GIF
Usage:
  python backend/pdf2video.py --pdf D:/paper.pdf --style educational --duration 6 --fps 24 --width 720
Requires: DASHSCOPE_API_KEY in environment.
"""
import argparse
import json
import os
from pathlib import Path
import asyncio

from app.services.pdf_parser import parse_pdf
from app.services.kg_builder import build_graph
from app.services.enhanced_video_prompt_builder import EnhancedVideoPromptBuilder
from app.services.qwen_video_generator import QwenVideoGenerator

OUT = Path(os.getenv("OUTPUT_DIR", "outputs"))

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--style", default="educational")
    ap.add_argument("--duration", type=int, default=6)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=720)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    paper = parse_pdf(args.pdf)
    graph = build_graph(paper)

    base = OUT / "text" / (Path(args.pdf).stem)
    base.mkdir(parents=True, exist_ok=True)
    (base / "paper_struct.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "graph.json").write_text(graph.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")

    nodes = graph.model_dump()["nodes"]
    top_names = [n["name"] for n in nodes[:5] if n.get("name")]
    storyboard_notes = [f"Emphasize concept: {name}" for name in top_names[:3]]

    prompt = EnhancedVideoPromptBuilder.build_director_prompt(
        paper_title=paper.get("title", "Untitled"),
        abstract=paper.get("abstract", ""),
        concept_name=top_names[0] if top_names else "Core Idea",
        key_claims=[s for s in paper.get("abstract", "").split(".")[:3] if s.strip()],
        scene_goals=top_names[1:4] if len(top_names) > 1 else ["Clarity"],
        duration_sec=args.duration,
        style=args.style,
        resolution=f"{args.width*16//9}x{args.width}",
        fps=args.fps,
        language="en",
        storyboard_notes=storyboard_notes,
    )

    gen = QwenVideoGenerator()
    res = await gen.generate_video_from_concept(
        concept_name=top_names[0] if top_names else "Core Idea",
        description=paper.get("abstract", ""),
        visual_type="diagram",
        output_dir=str(OUT / "videos"),
        duration=args.duration,
        resolution="720p",
        style=args.style,
        override_prompt=prompt,
        gif_fps=args.fps,
        gif_width=args.width,
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
