# Director Mode for Paper → Video → GIF

Backend (FastAPI)
- POST /api/director/generate-from-paper
- GET /api/director/jobs/{id}

Env
- DASHSCOPE_API_KEY=<your_key>
- OUTPUT_DIR=outputs

Quick start (Python)
- python backend/start_backend.py --port 8080 --reload
  - optional: --run-demo --paper-json backend/demo_paper.json

Run local (manual)
- cd backend
- python -m venv .venv && .venv\Scripts\activate
- pip install -r requirements.txt
- uvicorn app.main:app --reload --port 8080

Notes
- Output MP4 then auto-convert to GIF (palettegen/paletteuse, lanczos), target ≤12MB, default 720px width, 24fps.
- Large binaries, venv, outputs are ignored by git.
