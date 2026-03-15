# -*- coding: utf-8 -*-
"""
Enhanced Video Prompt Builder
将论文信息转为“导演分镜式”提示词，适配 Qwen 文生视频（更稳定、可控）。
"""
from typing import List, Dict, Optional
import textwrap


class EnhancedVideoPromptBuilder:
    """
    生成结构化的导演式提示词：
    - 片名/主题
    - 概要/目标
    - 分镜（每镜头含：主体、动作、场景、机位、运动、风格、色彩、时长）
    - 技术限制与避免项
    """

    @staticmethod
    def build_director_prompt(
        paper_title: str,
        abstract: str,
        concept_name: str,
        key_claims: List[str],
        scene_goals: List[str],
        duration_sec: int = 6,
        style: str = "educational",
        resolution: str = "1280x720",
        fps: int = 24,
        language: str = "en",
        avoid_items: Optional[List[str]] = None,
    ) -> str:
        avoid_items = avoid_items or [
            "blurry frames",
            "text walls",
            "rapid flashing",
            "violent or sensitive content",
            "unrelated scenes",
        ]

        style_map = {
            "educational": "clean educational visualization, clear diagrams, subtle motion graphics, easy to understand",
            "cinematic": "cinematic, shallow depth of field, dramatic lighting, film grain subtle",
            "3d": "high quality 3D render, global illumination, physically based rendering",
            "animation": "flat animation, bold shapes, smooth tweening, vibrant colors",
            "realistic": "photorealistic, professional lighting, natural camera movement",
        }
        style_desc = style_map.get(style, style_map["educational"])

        # 生成 3 个镜头模板，覆盖“问题→方法→结果/应用”
        shots = [
            {
                "title": "Problem Setup",
                "subject": f"Core idea of {concept_name}",
                "action": "Introduce the problem context and motivation",
                "env": "Minimal studio background or abstract shapes related to topic",
                "camera": "Medium shot → slow push-in",
                "motion": "Key terms appear next to elements, subtle parallax",
                "duration": f"{max(2, duration_sec//3)}s",
            },
            {
                "title": "Method Overview",
                "subject": "Proposed approach pipeline",
                "action": "Animate the flow: inputs → transformation → outputs",
                "env": "Diagram/blocks with arrows, nodes and edges",
                "camera": "Top-down to 3/4 view pan",
                "motion": "Elements enter sequentially, highlight important steps",
                "duration": f"{max(2, duration_sec//3)}s",
            },
            {
                "title": "Results & Impact",
                "subject": "Key results or qualitative examples",
                "action": "Show before/after or comparison and the impact",
                "env": "Two-column or split view, metric badges",
                "camera": "Slow pan left-right",
                "motion": "Glow highlight on improvements, conclude with title card",
                "duration": f"{max(2, duration_sec - 2*(duration_sec//3))}s",
            },
        ]

        claims_block = "\n".join([f"- {c}" for c in key_claims[:5]])
        goals_block = "\n".join([f"- {g}" for g in scene_goals[:5]])
        avoid_block = "\n".join([f"- {a}" for a in avoid_items])
        shots_block = "\n".join(
            [
                textwrap.dedent(
                    f"""
                    - Shot: {s['title']}
                      Subject: {s['subject']}
                      Action: {s['action']}
                      Environment: {s['env']}
                      Camera: {s['camera']}
                      Motion: {s['motion']}
                      Visual Style: {style_desc}
                      Color: academic palette, high contrast labels
                      Duration: {s['duration']}
                    """
                ).strip()
                for s in shots
            ]
        )

        prompt = f"""
        Title: {paper_title} — {concept_name}
        Language: {language}
        Target: short video for paper homepage hero GIF

        Paper Abstract:
        {abstract}

        Key Claims:
        {claims_block}

        Scene Goals:
        {goals_block}

        Global Look & Feel:
        - {style_desc}
        - Resolution: {resolution}, FPS: {fps}
        - Academic tone, minimal text overlays, strong visual clarity

        Shots Plan:
        {shots_block}

        Constraints (Important):
        {avoid_block}

        Output:
        - Generate a {duration_sec}s video, coherent across shots, with smooth transitions.
        - Avoid hallucinated text; prefer icons, arrows, and simple labels.
        - Keep composition clean for later GIF conversion.
        """
        return textwrap.dedent(prompt).strip()
