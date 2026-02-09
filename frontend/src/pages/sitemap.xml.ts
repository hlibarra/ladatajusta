import type { APIRoute } from 'astro';

const SITE_URL = 'https://ladatajusta.com.ar';
const API_BASE = import.meta.env.PUBLIC_API_BASE_URL || 'http://backend:8000';

export const GET: APIRoute = async () => {
  // Fetch published articles
  let publications: any[] = [];
  try {
    const res = await fetch(`${API_BASE}/api/publications/search?limit=1000&state=published`);
    if (res.ok) {
      const data = await res.json();
      publications = data.items || [];
    }
  } catch (e) {
    console.error('Error fetching publications for sitemap:', e);
  }

  // Fetch sections
  let sections: any[] = [];
  try {
    const res = await fetch(`${API_BASE}/api/sections`);
    if (res.ok) {
      const data = await res.json();
      sections = (data.sections || []).filter((s: any) => s.is_active);
    }
  } catch (e) {
    console.error('Error fetching sections for sitemap:', e);
  }

  const today = new Date().toISOString().split('T')[0];

  const urls = [
    // Homepage
    `<url><loc>${SITE_URL}/</loc><changefreq>hourly</changefreq><priority>1.0</priority><lastmod>${today}</lastmod></url>`,
    // About
    `<url><loc>${SITE_URL}/about</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>`,
    // Tendencias
    `<url><loc>${SITE_URL}/tendencias</loc><changefreq>daily</changefreq><priority>0.7</priority></url>`,
    // Sections
    ...sections.map((s: any) =>
      `<url><loc>${SITE_URL}/seccion/${s.slug}</loc><changefreq>hourly</changefreq><priority>0.8</priority><lastmod>${today}</lastmod></url>`
    ),
    // Publications
    ...publications.map((p: any) => {
      const lastmod = p.published_at ? p.published_at.split('T')[0] : today;
      return `<url><loc>${SITE_URL}/p/${p.slug}</loc><changefreq>weekly</changefreq><priority>0.6</priority><lastmod>${lastmod}</lastmod></url>`;
    }),
  ];

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>`;

  return new Response(sitemap, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
