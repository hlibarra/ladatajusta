Backend (FastAPI)

- Instalar deps:  python -m pip install -r requirements.txt
- Correr API:     python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Endpoints principales:
- GET  /health
- POST /api/scrape/fetch
- POST /api/publications/process/{scraped_id}
- POST /api/publications/{publication_id}/publish
- GET  /api/publications
- GET  /api/publications/{publication_id}
- POST /api/publications/{publication_id}/vote
