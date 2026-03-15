@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Quick start backend (Windows, PowerShell-free .bat)
REM - Creates venv under backend\.venv
REM - Installs deps
REM - Checks DASHSCOPE_API_KEY
REM - Runs FastAPI on :8080

pushd %~dp0
cd backend

if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -U pip
pip install -r requirements.txt

if "%DASHSCOPE_API_KEY%"=="" (
  echo [ERROR] Please set DASHSCOPE_API_KEY in your environment or .env (not committed).
  echo Example: set DASHSCOPE_API_KEY=sk-xxx
  goto :end
)

set OUTPUT_DIR=outputs
if not exist %OUTPUT_DIR% mkdir %OUTPUT_DIR%

python - <<PY
print('Health check: OK')
PY

uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

:end
popd
endlocal
