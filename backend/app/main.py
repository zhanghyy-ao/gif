from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import uuid
import asyncio
from pathlib import Path

from app.services.qwen_video_generator import QwenVideoGenerator
from app.services.enhanced_video_prompt_builder import EnhancedVideoPromptBuilder

app = FastAPI(title="Director Mode API")

JOBS: Dict[str, Dict[str, Any]] = {}
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class DirectorRequest(BaseModel):
    paper_title: str
    abstract: str
    concept_name: str
    key_claims: List[str] = Field(default_factory=list)
    scene_goals: List[str] = Field(default_factory=list)
    duration_sec: int = 6
    style: str = "educational"
    fps: int = 24
    width: int = 720
    language: str = "en"

class JobStatus(BaseModel):
    id: str
    status: str
    message: Optional[str] = None
    mp4_path: Optional[str] = None
    gif_path: Optional[str] = None
    prompt_preview: Optional[str] = None

@app.post("/api/director/generate-from-paper", response_model=JobStatus)
async def generate_from_paper(req: DirectorRequest):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "PENDING", "message": "queued"}

    async def worker():
        try:
            JOBS[job_id] = {"status": "RUNNING", "message": "preparing prompt"}
            prompt = EnhancedVideoPromptBuilder.build_director_prompt(
                paper_title=req.paper_title,
                abstract=req.abstract,
                concept_name=req.concept_name,
                key_claims=req.key_claims,
                scene_goals=req.scene_goals,
                duration_sec=req.duration_sec,
                style=req.style,
                resolution=f"{req.width*16//9}x{req.width}",
                fps=req.fps,
                language=req.language,
            )

            gen = QwenVideoGenerator()
            JOBS[job_id] = {"status": "RUNNING", "message": "calling Qwen"}
            result = await gen.generate_video_from_concept(
                concept_name=req.concept_name,
                description=req.abstract,
                visual_type="diagram",
                output_dir=str(OUTPUT_DIR / "videos"),
                duration=req.duration_sec,
                resolution="720p",
                style=req.style,
                override_prompt=prompt,
                gif_fps=req.fps,
                gif_width=req.width,
            )

            if result.get("success"):
                JOBS[job_id] = {
                    "status": "SUCCEEDED",
                    "mp4_path": result.get("video_path"),
                    "gif_path": result.get("gif_path"),
                    "prompt_preview": result.get("prompt", "")[:300]
                }
            else:
                JOBS[job_id] = {"status": "FAILED", "message": result.get("error", "unknown error")}
        except Exception as e:
            JOBS[job_id] = {"status": "FAILED", "message": str(e)}

    asyncio.create_task(worker())
    return JobStatus(id=job_id, status="PENDING", message="queued")

@app.get("/api/director/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    data = JOBS.get(job_id)
    if not data:
        return JobStatus(id=job_id, status="NOT_FOUND", message="unknown job")
    return JobStatus(id=job_id, **data)
