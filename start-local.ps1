# Script para iniciar el proyecto localmente
# Uso: .\start-local.ps1 [backend|frontend|db|all]

param(
    [string]$Component = "all"
)

$ErrorActionPreference = 'Stop'

function Start-Database {
    Write-Host "Iniciando base de datos PostgreSQL con Docker..." -ForegroundColor Cyan
    docker compose up -d db
    Write-Host "Base de datos iniciada en localhost:5432" -ForegroundColor Green
}

function Start-Backend {
    Write-Host "Iniciando backend..." -ForegroundColor Cyan
    Push-Location backend
    try {
        if (-not (Test-Path ".venv")) {
            Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
            python -m venv .venv
        }
        Write-Host "Activando entorno virtual e instalando dependencias..." -ForegroundColor Yellow
        .\.venv\Scripts\Activate.ps1
        python -m pip install -r requirements.txt -q
        Write-Host "Iniciando servidor FastAPI en http://localhost:8000" -ForegroundColor Green
        python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
    finally {
        Pop-Location
    }
}

function Start-Frontend {
    Write-Host "Iniciando frontend..." -ForegroundColor Cyan
    Push-Location frontend
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "Instalando dependencias npm..." -ForegroundColor Yellow
            npm install
        }
        Write-Host "Iniciando servidor Astro en http://localhost:4321" -ForegroundColor Green
        npm run dev
    }
    finally {
        Pop-Location
    }
}

switch ($Component) {
    "db" {
        Start-Database
    }
    "backend" {
        Start-Backend
    }
    "frontend" {
        Start-Frontend
    }
    "all" {
        Write-Host "=== LA DATA JUSTA - Inicio Local ===" -ForegroundColor Magenta
        Write-Host ""
        Write-Host "Para iniciar todo el proyecto:" -ForegroundColor White
        Write-Host "  1. Abrir terminal 1: .\start-local.ps1 db" -ForegroundColor Gray
        Write-Host "  2. Abrir terminal 2: .\start-local.ps1 backend" -ForegroundColor Gray
        Write-Host "  3. Abrir terminal 3: .\start-local.ps1 frontend" -ForegroundColor Gray
        Write-Host ""
        Write-Host "O usar Docker Compose para todo:" -ForegroundColor White
        Write-Host "  docker compose up" -ForegroundColor Gray
        Write-Host ""
        Write-Host "URLs:" -ForegroundColor White
        Write-Host "  Frontend: http://localhost:4321" -ForegroundColor Gray
        Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Gray
        Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Gray
    }
    default {
        Write-Host "Componente no reconocido: $Component" -ForegroundColor Red
        Write-Host "Uso: .\start-local.ps1 [backend|frontend|db|all]" -ForegroundColor Yellow
    }
}
