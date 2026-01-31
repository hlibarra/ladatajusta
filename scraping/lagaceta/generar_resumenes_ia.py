import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

# 🔐 Cargar API key desde .env
load_dotenv()
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key="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")

# 📦 Configuración base de datos
DB_CONFIG = {
    "user": "postgres",
    "password": "hugoluis",
    "database": "datajusta",
    "host": "localhost",
    "port": 5432,
}

# 🔧 Parámetros generales
MAX_RESUMENES = 5
MODEL = "gpt-3.5-turbo"

async def obtener_noticias(conn):
    query = """
    SELECT id, titulo, contenido
    FROM noticias_scrapeadas
    WHERE resumen_ia IS NULL AND contenido IS NOT NULL
    ORDER BY fecha_ingreso
    LIMIT $1
    """
    return await conn.fetch(query, MAX_RESUMENES)

async def generar_resumen(contenido, titulo):
    prompt = f"""
Resumí de forma clara y concisa la siguiente noticia para que cualquier lector entienda de qué trata, en no más de 5 líneas. No repitas el título, si el titulo es una pregunta, contesta dicha pregunta:

Título: {titulo}

Contenido:
{contenido}
"""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error con OpenAI: {e}")
        return None

async def guardar_resumen(conn, noticia_id, resumen):
    await conn.execute("""
    UPDATE noticias_scrapeadas
    SET resumen_ia = $1
    WHERE id = $2
    """, resumen, noticia_id)

async def main():
    conn = await asyncpg.connect(**DB_CONFIG)
    noticias = await obtener_noticias(conn)
    print(f"🧠 Generando resúmenes para {len(noticias)} noticias...\n")

    for noticia in noticias:
        print(f"➡️ {noticia['titulo'][:60]}...")
        resumen = await generar_resumen(noticia["contenido"], noticia["titulo"])
        if resumen:
            await guardar_resumen(conn, noticia["id"], resumen)
            print(f"✅ Resumen guardado:\n{resumen[:200]}...\n")
        else:
            print("⚠️ Falló el resumen.\n")

    await conn.close()
    print("🏁 Proceso finalizado.")

if __name__ == "__main__":
    asyncio.run(main())
