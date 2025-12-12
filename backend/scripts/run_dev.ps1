$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt
$env:APP_ENV='dev'
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
