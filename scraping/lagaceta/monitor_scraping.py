"""
Script para monitorear el progreso del scraping en tiempo real
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "ladatajusta"),
    "user": os.getenv("DB_USER", "ladatajusta"),
    "password": os.getenv("DB_PASSWORD", "ladatajusta"),
}


async def monitor():
    """Monitorea el progreso del scraping"""
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("[INFO] Conectado a PostgreSQL")
        print("[INFO] Monitoreando scraping en tiempo real...")
        print("[INFO] Presiona Ctrl+C para salir\n")

        last_count = 0

        while True:
            # Contar items scrapeados en la última hora
            count_hour = await conn.fetchval(
                """
                SELECT COUNT(*) FROM scraping_items
                WHERE source_media = 'lagaceta'
                  AND scraped_at >= NOW() - INTERVAL '1 hour'
                """
            )

            # Total de items de La Gaceta
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM scraping_items
                WHERE source_media = 'lagaceta'
                """
            )

            # Últimos 3 items
            last_items = await conn.fetch(
                """
                SELECT title, scraped_at
                FROM scraping_items
                WHERE source_media = 'lagaceta'
                ORDER BY scraped_at DESC
                LIMIT 3
                """
            )

            # Limpiar pantalla (opcional)
            print("\n" + "=" * 70)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Estado del Scraping")
            print("=" * 70)
            print(f"Total de items (La Gaceta): {total}")
            print(f"Scrapeados última hora: {count_hour}")
            print(f"Nuevos desde última vez: {count_hour - last_count}")

            if last_items:
                print("\nÚltimos 3 items scrapeados:")
                for i, item in enumerate(last_items, 1):
                    tiempo_ago = datetime.now(item['scraped_at'].tzinfo) - item['scraped_at']
                    minutos_ago = int(tiempo_ago.total_seconds() / 60)
                    print(f"  {i}. [{minutos_ago}m ago] {item['title'][:60]}...")

            last_count = count_hour

            # Esperar 5 segundos antes de actualizar
            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("\n\n[INFO] Monitoreo detenido por el usuario")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            print("[INFO] Conexión cerrada")


if __name__ == "__main__":
    asyncio.run(monitor())
