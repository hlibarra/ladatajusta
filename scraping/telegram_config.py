"""
Telegram notification message templates
"""

from datetime import datetime


class MessageTemplates:
    """HTML-formatted message templates for Telegram notifications"""

    SERVICE_START = """🟢 <b>Servicio de Scraping Iniciado</b>

📊 Intervalos:
• Scraping: cada {scrape_interval}min
• Procesamiento IA: cada {ai_interval}min

🔧 Servicios Automáticos:
{services_status}

🌐 API: {control_url}

⏰ {timestamp}"""

    SERVICE_STOP = """🔴 <b>Servicio de Scraping Detenido</b>

📊 Estadísticas:
• Tiempo activo: {uptime}
• Items scrapeados: {items_scraped}
• Items procesados por IA: {items_ai_processed}

⏰ {timestamp}"""

    SCRAPE_START = """🔄 <b>Scraping Iniciado</b>

📋 Fuentes ({source_count}):
{source_list}
🎯 Modo: {mode}{user_info}

⏰ {timestamp}"""

    SCRAPE_COMPLETE = """✅ <b>Scraping Completado</b>

📊 Resultados:
• Items scrapeados: {total_items}
• Fuentes procesadas: {sources_processed}
• Duración: {duration}

⏰ {timestamp}"""

    SOURCE_ERROR = """❌ <b>Error en Fuente</b>

📰 Fuente: <b>{source_name}</b>
🔴 Error: {error_message}
⚠️ Errores consecutivos: {consecutive_errors}

⏰ {timestamp}"""

    SOURCE_DISABLED = """⚠️ <b>Fuente Deshabilitada Automáticamente</b>

📰 Fuente: <b>{source_name}</b>
🔴 Motivo: Demasiados errores consecutivos ({count})

⏰ {timestamp}"""

    AI_START = """🤖 <b>Procesamiento IA Iniciado</b>

📋 Items pendientes: {pending_count}
🎯 Modo: {mode}

⏰ {timestamp}"""

    AI_COMPLETE = """✅ <b>Procesamiento IA Completado</b>

📊 Resultados:
• Items procesados: {processed}
• Items fallidos: {failed}
• Duración: {duration}

⏰ {timestamp}"""

    AUTO_PREPARE_START = """📋 <b>Auto-Preparación Iniciada</b>

📋 Items pendientes: {pending_count}
🎯 Modo: {mode}

⏰ {timestamp}"""

    AUTO_PREPARE = """✅ <b>Auto-Preparación Completada</b>

📊 Resultados:
• ✓ Listos para publicar: {ready}
• ⚠️ Duplicados: {duplicates}
• ❌ Calidad insuficiente: {quality_failed}

⏰ {timestamp}"""

    AUTO_PUBLISH_START = """📰 <b>Auto-Publicación Iniciada</b>

📋 Items pendientes: {pending_count}
🎯 Modo: {mode}

⏰ {timestamp}"""

    AUTO_PUBLISH = """✅ <b>Auto-Publicación Completada</b>

📊 Resultados:
• Publicados: {published}

⏰ {timestamp}"""

    CURATOR_COMPLETE = """🎯 <b>Curación de Noticias Completada</b>

📊 Resultados:
• Publicados: {published}
• Disponibles: {available}
• Seleccionados de: {selected}

⏰ {timestamp}"""

    TASK_ERROR = """🚨 <b>Error en Tarea</b>

⚙️ Tarea: <b>{task_name}</b>
🔴 Error: {error_message}

⏰ {timestamp}"""

    TEST_MESSAGE = """🧪 <b>Notificación de Prueba</b>

Este es un mensaje de prueba del servicio de scraping de La Data Justa.

⏰ {timestamp}"""

    CONFIG_CHANGED = """⚙️ <b>Configuración Actualizada</b>

📋 Cambios:
{changes}

⏰ {timestamp}"""

    RESTART_REQUESTED = """🔄 <b>Reinicio de Servicio Solicitado</b>

El servicio de scraping se está reiniciando...

⏰ {timestamp}"""


def format_timestamp() -> str:
    """Format current timestamp in Argentine format"""
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format"""
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minutos"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        return f"{days}d {hours}h"
