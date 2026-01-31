-- Migration 011: Add missing site configuration values
-- Agrega configuraciones faltantes que el frontend espera

INSERT INTO site_config (key, value, description, category) VALUES
    ('features.voting_enabled', 'true', 'Habilitar sistema de votos en noticias', 'features'),
    ('features.social_sharing', 'false', 'Mostrar botones para compartir en redes sociales', 'features'),
    ('features.related_news', 'true', 'Mostrar noticias relacionadas al final de cada artículo', 'features')
ON CONFLICT (key) DO NOTHING;
