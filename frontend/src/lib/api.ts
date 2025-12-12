function computeApiBase(): string {
  const publicBase =
    import.meta.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  // SSR needs to reach the backend from the server runtime (Docker network, etc.)
  if (import.meta.env.SSR) {
    return (
      import.meta.env.PUBLIC_API_INTERNAL_BASE_URL ??
      import.meta.env.PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    );
  }
  // Browser runtime
  return publicBase;
}

export const API_BASE = computeApiBase();

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
