"""
Script de utilidades para gestionar items de scraping
- Ver estadísticas
- Mover items entre estados del pipeline
- Detectar duplicados
- Limpiar datos
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Reconfigure stdout for Windows unicode support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Database connection
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}


async def show_stats(conn):
    """Muestra estadísticas de scraping"""
    print("\n" + "="*60)
    print("📊 ESTADÍSTICAS DE SCRAPING - LA GACETA")
    print("="*60)

    # Total de items
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM scraping_items WHERE source_media = 'lagaceta'"
    )
    print(f"\n📦 Total de items: {total}")

    # Por estado
    print("\n📈 Items por estado:")
    rows = await conn.fetch(
        """
        SELECT status, COUNT(*) as count
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        GROUP BY status
        ORDER BY count DESC
        """
    )
    for row in rows:
        print(f"   {row['status']:20} → {row['count']:5} items")

    # Últimos scrapes
    print("\n🕐 Últimos scrapes:")
    rows = await conn.fetch(
        """
        SELECT
            DATE_TRUNC('day', scraped_at) as day,
            COUNT(*) as count
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
        """
    )
    for row in rows:
        print(f"   {row['day'].strftime('%Y-%m-%d')} → {row['count']:5} items")

    # Duplicados detectados
    duplicates = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT content_hash)
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        HAVING COUNT(*) > 1
        """
    )
    if duplicates:
        print(f"\n⚠️ Duplicados detectados: {duplicates}")

    print("\n" + "="*60)


async def list_recent(conn, limit=10):
    """Lista los items más recientes"""
    print(f"\n📰 Últimos {limit} items scrapeados:\n")

    rows = await conn.fetch(
        """
        SELECT
            id,
            title,
            status,
            scraped_at,
            article_date
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        ORDER BY scraped_at DESC
        LIMIT $1
        """,
        limit
    )

    for i, row in enumerate(rows, 1):
        print(f"{i}. [{row['status']}] {row['title'][:60]}...")
        print(f"   Scrapeado: {row['scraped_at'].strftime('%Y-%m-%d %H:%M')}")
        if row['article_date']:
            print(f"   Publicado: {row['article_date'].strftime('%Y-%m-%d %H:%M')}")
        print()


async def mark_ready_for_ai(conn, hours_ago=24):
    """
    Marca items recientes como listos para procesamiento AI
    """
    print(f"\n🤖 Marcando items de últimas {hours_ago} horas como 'ready_for_ai'...")

    result = await conn.execute(
        """
        UPDATE scraping_items
        SET status = 'ready_for_ai',
            status_message = 'Auto-marked by manage script'
        WHERE source_media = 'lagaceta'
          AND status = 'scraped'
          AND scraped_at >= NOW() - INTERVAL '1 hour' * $1
        """,
        hours_ago
    )

    # Extraer número de filas afectadas
    count = int(result.split()[-1])
    print(f"✅ {count} items marcados como listos para AI")


async def detect_duplicates(conn):
    """Detecta y reporta duplicados"""
    print("\n🔍 Buscando duplicados por contenido...\n")

    rows = await conn.fetch(
        """
        SELECT
            content_hash,
            COUNT(*) as duplicate_count,
            array_agg(id) as item_ids,
            array_agg(title) as titles,
            MIN(scraped_at) as first_scraped,
            MAX(scraped_at) as last_scraped
        FROM scraping_items
        WHERE source_media = 'lagaceta'
        GROUP BY content_hash
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC
        LIMIT 10
        """
    )

    if not rows:
        print("✅ No se encontraron duplicados")
        return

    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['duplicate_count']} copias:")
        print(f"   Título: {row['titles'][0][:60]}...")
        print(f"   Primera vez: {row['first_scraped'].strftime('%Y-%m-%d %H:%M')}")
        print(f"   Última vez: {row['last_scraped'].strftime('%Y-%m-%d %H:%M')}")
        print(f"   IDs: {', '.join(str(id)[:8] for id in row['item_ids'])}")
        print()


async def cleanup_old_errors(conn, days_ago=7):
    """
    Limpia items con error muy antiguos
    """
    print(f"\n🧹 Limpiando items con error de hace más de {days_ago} días...")

    result = await conn.execute(
        """
        DELETE FROM scraping_items
        WHERE source_media = 'lagaceta'
          AND status = 'error'
          AND scraped_at < NOW() - INTERVAL '1 day' * $1
        """,
        days_ago
    )

    count = int(result.split()[-1])
    print(f"✅ {count} items eliminados")


async def show_menu():
    """Muestra menú interactivo"""
    print("\n" + "="*60)
    print("🔧 MENÚ DE GESTIÓN DE SCRAPING")
    print("="*60)
    print("\n1. Ver estadísticas")
    print("2. Listar items recientes (10)")
    print("3. Listar items recientes (50)")
    print("4. Marcar últimas 24h como 'ready_for_ai'")
    print("5. Detectar duplicados")
    print("6. Limpiar errores antiguos (>7 días)")
    print("7. Marcar últimas 48h como 'ready_for_ai'")
    print("0. Salir")
    print("\n" + "="*60)

    return input("Selecciona una opción: ").strip()


async def main():
    """Función principal con menú interactivo"""
    print("🚀 Gestor de Scraping - La Gaceta")

    # Conectar a la base de datos
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ Conectado a PostgreSQL\n")
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return

    try:
        while True:
            opcion = await show_menu()

            if opcion == "0":
                print("\n👋 ¡Hasta luego!")
                break
            elif opcion == "1":
                await show_stats(conn)
            elif opcion == "2":
                await list_recent(conn, 10)
            elif opcion == "3":
                await list_recent(conn, 50)
            elif opcion == "4":
                await mark_ready_for_ai(conn, 24)
            elif opcion == "5":
                await detect_duplicates(conn)
            elif opcion == "6":
                await cleanup_old_errors(conn, 7)
            elif opcion == "7":
                await mark_ready_for_ai(conn, 48)
            else:
                print("❌ Opción inválida")

            input("\nPresiona Enter para continuar...")

    finally:
        await conn.close()
        print("\n🔌 Conexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
