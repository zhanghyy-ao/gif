from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import uuid
import asyncio
from pathlib import Path
import json

from app.services.qwen_video_generator import QwenVideoGenerator
from app.services.enhanced_video_prompt_builder import EnhancedVideoPromptBuilder
from app.services.pdf_parser import parse_pdf
from app.services.kg_builder import build_graph
from app.services.discipline_adapter import DisciplineAdapter
from app.services.reasoning_engine import DirectorReasoner

app = FastAPI(title="Director Mode API")

JOBS: Dict[str, Dict[str, Any]] = {}
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ADAPTER = DisciplineAdapter()

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
    storyboard_notes: Optional[List[str]] = None

class JobStatus(BaseModel):
    id: str
    status: str
    message: Optional[str] = None
    mp4_path: Optional[str] = None
    gif_path: Optional[str] = None
    prompt_preview: Optional[str] = None

@app.get("/api/director/disciplines")
async def list_disciplines():
    return {"disciplines": ADAPTER.list_disciplines()}

@app.post("/api/director/ingest-pdf")
async def ingest_pdf(pdf: UploadFile = File(...)):
    ingest_id = str(uuid.uuid4())
    tmp_dir = OUTPUT_DIR / "text" / ingest_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = tmp_dir / pdf.filename
    with open(pdf_path, "wb") as f:
        f.write(await pdf.read())
    paper_struct = parse_pdf(str(pdf_path))
    (tmp_dir / "paper_struct.json").write_text(json.dumps(paper_struct, ensure_ascii=False, indent=2), encoding="utf-8")
    graph = build_graph(paper_struct)
    (tmp_dir / "graph.json").write_text(json.dumps(graph.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    claims = paper_struct.get("abstract", "").split(".")[:3]
    goals = [n["name"] for n in graph.model_dump()["nodes"][:3]]
    return {
        "ingest_id": ingest_id,
        "title": paper_struct.get("title"),
        "abstract": paper_struct.get("abstract"),
        "claims": [c.strip() for c in claims if c.strip()],
        "goals": goals,
        "paths": {"paper_struct": str(tmp_dir / "paper_struct.json"), "graph": str(tmp_dir / "graph.json")}
    }

class GenerateFromGraphRequest(BaseModel):
    ingest_id: str
    style: str = "educational"
    duration_sec: int = 6
    fps: int = 24
    width: int = 720
    language: str = "en"
    discipline: Optional[str] = None
    reasoning: Optional[str] = Field(default="tot", description="cot|tot|none")

@app.post("/api/director/generate-from-graph", response_model=JobStatus)
async def generate_from_graph(req: GenerateFromGraphRequest):
    base = OUTPUT_DIR / "text" / req.ingest_id
    paper_struct = json.loads((base / "paper_struct.json").read_text(encoding="utf-8"))
    graph = json.loads((base / "graph.json").read_text(encoding="utf-8"))

    nodes = graph.get("nodes", [])
    top_names = [n.get("name") for n in nodes[:5] if n.get("name")]
    base_notes = [f"Emphasize concept: {name}" for name in top_names[:3]]

    adapted = ADAPTER.adapt(req.discipline or "", req.style, base_notes)

    # reasoning: CoT / ToT to synthesize goals/shots/notes
    reasoner = DirectorReasoner(discipline_style_desc=adapted.get("style_desc"))
    if req.reasoning == "cot":
        plan = reasoner.cot_plan(paper_struct, graph)
    elif req.reasoning == "none":
        plan = {"key_insights": top_names[:3], "scene_goals": top_names[1:4], "shots": []}
    else:
        plan = reasoner.tot_select(paper_struct, graph, k=3)

    storyboard_notes = reasoner.refine_prompt_notes(adapted["notes"] + plan.get("scene_goals", []))

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "PENDING", "message": "queued"}

    async def worker():
        try:
            JOBS[job_id] = {"status": "RUNNING", "message": "preparing prompt"}
            prompt = EnhancedVideoPromptBuilder.build_director_prompt(
                paper_title=paper_struct.get("title", "Untitled"),
                abstract=paper_struct.get("abstract", ""),
                concept_name=top_names[0] if top_names else "Core Idea",
                key_claims=plan.get("key_insights", [])[:3],
                scene_goals=plan.get("scene_goals", [])[:3],
                duration_sec=req.duration_sec,
                style=adapted["style"],
                resolution=f"{req.width*16//9}x{req.width}",
                fps=req.fps,
                language=req.language,
                storyboard_notes=storyboard_notes,
            )

            gen = QwenVideoGenerator()
            JOBS[job_id] = {"status": "RUNNING", "message": "calling Qwen"}
            result = await gen.generate_video_from_concept(
                concept_name=top_names[0] if top_names else "Core Idea",
                description=paper_struct.get("abstract", ""),
                visual_type="diagram",
                output_dir=str(OUTPUT_DIR / "videos"),
                duration=req.duration_sec,
                resolution="720p",
                style=adapted["style"],
                override_prompt=prompt,
                gif_fps=req.fps,
                gif_width=req.width,
            )

            if result.get("success"):
                JOBS[job_id] = {
                    "status": "SUCCEEDED",
                    "mp4_path": result.get("video_path"),
                    "gif_path": result.get("gif_path"),
                    "prompt_preview": result.get("prompt", "")[:500]
                }
            else:
                JOBS[job_id] = {"status": "FAILED", "message": result.get("error", "unknown error")}
        except Exception as e:
            JOBS[job_id] = {"status": "FAILED", "message": str(e)}

    asyncio.create_task(worker())
    return JobStatus(id=job_id, status="PENDING", message="queued")

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
                storyboard_notes=req.storyboard_notes or [],
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
                    "prompt_preview": result.get("prompt", "")[:500]
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
