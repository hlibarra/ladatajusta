// Use internal URL for SSR, external URL for browser
export const API_BASE = import.meta.env.SSR
  ? (import.meta.env.PUBLIC_API_BASE_URL || "http://backend:8000")
  : (import.meta.env.PUBLIC_CLIENT_API_BASE_URL || import.meta.env.PUBLIC_API_BASE_URL || "");

// Types
export interface Publication {
  id: string;
  state: string;
  title: string;
  summary: string;
  body: string;
  category?: string | null;
  tags: string[];
  created_at: string;
  published_at?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface VoteTotals {
  publication_id: string;
  hot: number;
  cold: number;
}

export interface SearchParams {
  q?: string;
  category?: string;
  tags?: string[];
  from_date?: string;
  to_date?: string;
  state?: string;
  limit?: number;
  offset?: number;
}

// Base API functions
export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`GET ${path} failed: ${r.status}`);
  return (await r.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`POST ${path} failed: ${r.status}`);
  return (await r.json()) as T;
}

// Publication functions
export async function fetchPublications(
  params: SearchParams = {}
): Promise<PaginatedResponse<Publication>> {
  const query = new URLSearchParams();

  if (params.q) query.set("q", params.q);
  if (params.category) query.set("category", params.category);
  if (params.tags) params.tags.forEach((t) => query.append("tags", t));
  if (params.from_date) query.set("from_date", params.from_date);
  if (params.to_date) query.set("to_date", params.to_date);
  if (params.state) query.set("state", params.state);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));

  const queryStr = query.toString();
  const path = queryStr ? `/api/publications/search?${queryStr}` : "/api/publications/search";

  return apiGet<PaginatedResponse<Publication>>(path);
}

export async function getPublication(id: string): Promise<Publication> {
  return apiGet<Publication>(`/api/publications/${id}`);
}

export async function vote(
  publicationId: string,
  voteType: "hot" | "cold"
): Promise<VoteTotals> {
  return apiPost<VoteTotals>(`/api/publications/${publicationId}/vote`, {
    vote_type: voteType,
  });
}

// Get unique categories from publications
export async function getCategories(): Promise<string[]> {
  const res = await fetchPublications({ limit: 100 });
  const categories = new Set<string>();
  res.items.forEach((p) => {
    if (p.category) categories.add(p.category);
  });
  return Array.from(categories).sort();
}
