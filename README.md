# La Data Justa

Plataforma para scraping, procesamiento y publicación de datos.

## Requisitos

- **Python 3.11+**
- **Node.js 20+**
- **Docker** (para la base de datos)

## Inicio rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/gutierrezp22/ladatajusta.git
cd ladatajusta
```

### 2. Configurar variables de entorno

El archivo `backend/.env` ya viene configurado para desarrollo local. Si necesitas usar OpenAI, edita y agrega tu API key:

```env
OPENAI_API_KEY=tu-api-key-aqui
```

### 3. Iniciar la base de datos

```powershell
docker compose up db -d
```

Esto levanta PostgreSQL con pgvector en `localhost:5432`.

### 4. Iniciar el backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Iniciar el frontend

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

### 6. Crear usuario administrador

Para acceder al panel de administracion, primero crea el usuario admin:

```powershell
cd backend
python -m scripts.create_admin
```

Esto crea el usuario:
- **Email:** `admin@local.com`
- **Password:** `admin123`

Luego accede a: http://localhost:4321/admin

## URLs

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:4321 |
| Panel Admin | http://localhost:4321/admin |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

## Scripts de ayuda

Puedes usar el script `start-local.ps1` para simplificar el inicio:

```powershell
# Ver instrucciones
.\start-local.ps1

# Iniciar base de datos
.\start-local.ps1 db

# Iniciar backend (en otra terminal)
.\start-local.ps1 backend

# Iniciar frontend (en otra terminal)
.\start-local.ps1 frontend
```

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/scrape/fetch` | Obtener datos de una URL |
| POST | `/api/publications/process/{scraped_id}` | Procesar datos scrapeados |
| POST | `/api/publications/{id}/publish` | Publicar |
| GET | `/api/publications` | Listar publicaciones |
| GET | `/api/publications/{id}` | Obtener publicacion |
| POST | `/api/publications/{id}/vote` | Votar publicacion |

## Estructura del proyecto

```
ladatajusta/
├── backend/                 # API FastAPI
│   ├── app/
│   │   ├── api/            # Rutas y schemas
│   │   ├── core/           # Configuracion
│   │   ├── db/             # Base de datos
│   │   ├── ai/             # Pipeline de IA
│   │   └── scrape/         # Scraping
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Astro
│   ├── src/
│   └── package.json
├── docker-compose.yml      # Para produccion
├── start-local.ps1         # Script de inicio local
└── README.md
```

## Produccion

Para desplegar en servidor:

```bash
docker compose up -d
```

Esto levanta todos los servicios containerizados.
