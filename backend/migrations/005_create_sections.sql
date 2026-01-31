-- Migration to create sections system for dynamic navigation menu
-- Sections are top-level navigation items that group multiple categories

-- Create sections table
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    icon VARCHAR(50), -- Icon name for UI (e.g., 'newspaper', 'globe', 'briefcase')
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for ordering
CREATE INDEX idx_sections_order ON sections(display_order, is_active);

-- Create category_section_mapping table
-- Maps publication categories to sections (many-to-many)
CREATE TABLE category_section_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    category_name VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(section_id, category_name)
);

-- Create indexes for performance
CREATE INDEX idx_category_section_mapping_section ON category_section_mapping(section_id);
CREATE INDEX idx_category_section_mapping_category ON category_section_mapping(category_name);

-- Insert default sections
INSERT INTO sections (name, slug, description, icon, display_order, is_active) VALUES
    ('Últimas Noticias', 'ultimas-noticias', 'Las noticias más recientes', 'newspaper', 1, true),
    ('Política', 'politica', 'Noticias de política nacional e internacional', 'landmark', 2, true),
    ('Economía', 'economia', 'Actualidad económica y financiera', 'trending-up', 3, true),
    ('Sociedad', 'sociedad', 'Noticias sociales y de interés general', 'users', 4, true),
    ('Mundo', 'mundo', 'Noticias internacionales', 'globe', 5, true),
    ('Deportes', 'deportes', 'Actualidad deportiva', 'target', 6, true),
    ('Tecnología', 'tecnologia', 'Innovación y tecnología', 'cpu', 7, true),
    ('Salud', 'salud', 'Salud y bienestar', 'heart', 8, true),
    ('Cultura', 'cultura', 'Arte, cultura y entretenimiento', 'palette', 9, true),
    ('Medio Ambiente', 'medio-ambiente', 'Ecología y medio ambiente', 'leaf', 10, true);

-- Map categories to sections (you can customize this mapping)
INSERT INTO category_section_mapping (section_id, category_name)
SELECT s.id, c.category_name
FROM sections s
CROSS JOIN (VALUES
    -- Política
    ('Política', 'política'),
    ('Política', 'gobierno'),
    ('Política', 'elecciones'),
    ('Política', 'congreso'),

    -- Economía
    ('Economía', 'economía'),
    ('Economía', 'finanzas'),
    ('Economía', 'mercados'),
    ('Economía', 'empresas'),
    ('Economía', 'negocios'),

    -- Sociedad
    ('Sociedad', 'sociedad'),
    ('Sociedad', 'educación'),
    ('Sociedad', 'seguridad'),
    ('Sociedad', 'justicia'),

    -- Mundo
    ('Mundo', 'internacional'),
    ('Mundo', 'mundo'),

    -- Deportes
    ('Deportes', 'deportes'),
    ('Deportes', 'fútbol'),
    ('Deportes', 'rugby'),
    ('Deportes', 'tenis'),

    -- Tecnología
    ('Tecnología', 'tecnología'),
    ('Tecnología', 'innovación'),
    ('Tecnología', 'ciencia'),

    -- Salud
    ('Salud', 'salud'),
    ('Salud', 'medicina'),

    -- Cultura
    ('Cultura', 'cultura'),
    ('Cultura', 'espectáculos'),
    ('Cultura', 'cine'),
    ('Cultura', 'música'),
    ('Cultura', 'arte'),

    -- Medio Ambiente
    ('Medio Ambiente', 'medio ambiente'),
    ('Medio Ambiente', 'ecología'),
    ('Medio Ambiente', 'clima')
) AS c(section_name, category_name)
WHERE s.name = c.section_name;

-- Add comments
COMMENT ON TABLE sections IS 'Navigation sections that group multiple categories';
COMMENT ON TABLE category_section_mapping IS 'Maps publication categories to navigation sections';
COMMENT ON COLUMN sections.display_order IS 'Order in which sections appear in navigation menu (lower = first)';
COMMENT ON COLUMN sections.is_active IS 'Whether this section is visible in the menu';
