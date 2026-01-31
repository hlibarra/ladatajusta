-- Migration 010: Create site_config table
-- Configuración del sitio almacenada en base de datos
-- Permite cambiar comportamientos sin modificar código

CREATE TABLE IF NOT EXISTS site_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES users(id)
);

-- Índice para búsqueda por categoría
CREATE INDEX IF NOT EXISTS idx_site_config_category ON site_config(category);

-- Configuraciones iniciales
INSERT INTO site_config (key, value, description, category) VALUES
    ('display.show_images', 'false', 'Mostrar imágenes en cards de noticias y páginas de detalle', 'display'),
    ('display.card_style', '"compact"', 'Estilo de cards: compact (sin imagen), standard (con imagen), minimal (solo título)', 'display'),
    ('display.show_author', 'true', 'Mostrar autor en las noticias', 'display'),
    ('display.show_reading_time', 'true', 'Mostrar tiempo de lectura estimado', 'display'),
    ('display.show_source_media', 'true', 'Mostrar medio fuente', 'display'),
    ('features.anticlickbait_images', 'true', 'Habilitar generación de imágenes anti-clickbait', 'features'),
    ('features.reading_levels', 'true', 'Habilitar niveles de lectura (sin vueltas, lo central, en profundidad)', 'features')
ON CONFLICT (key) DO NOTHING;

-- Función para actualizar timestamp automáticamente
CREATE OR REPLACE FUNCTION update_site_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar timestamp
DROP TRIGGER IF EXISTS site_config_updated_at ON site_config;
CREATE TRIGGER site_config_updated_at
    BEFORE UPDATE ON site_config
    FOR EACH ROW
    EXECUTE FUNCTION update_site_config_timestamp();

-- Comentarios
COMMENT ON TABLE site_config IS 'Configuración dinámica del sitio';
COMMENT ON COLUMN site_config.key IS 'Clave única de configuración (ej: display.show_images)';
COMMENT ON COLUMN site_config.value IS 'Valor en formato JSON (puede ser boolean, string, number, object)';
COMMENT ON COLUMN site_config.category IS 'Categoría para agrupar configuraciones (display, features, etc)';
