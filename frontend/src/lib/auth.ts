import { API_BASE } from './api';

const ACCESS_TOKEN_KEY = 'ldj_access_token';
const REFRESH_TOKEN_KEY = 'ldj_refresh_token';

export function saveTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function getAccessToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

export async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const r = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!r.ok) {
      clearTokens();
      return false;
    }

    const data = await r.json();
    localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export async function login(email: string, password: string): Promise<{ success: boolean; error?: string }> {
  try {
    console.log('=== LOGIN DEBUG ===');
    console.log('API_BASE:', API_BASE);
    console.log('Login URL:', `${API_BASE}/api/auth/login`);
    console.log('Email:', email);

    const r = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    console.log('Response status:', r.status);
    console.log('Response ok:', r.ok);

    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      console.log('Error data:', data);
      return { success: false, error: data.detail || 'Error de autenticacion' };
    }

    const data = await r.json();
    console.log('Success! Got tokens');
    saveTokens(data.access_token, data.refresh_token);
    return { success: true };
  } catch (err) {
    console.error('Login exception:', err);
    return { success: false, error: 'Error de conexion' };
  }
}

export function logout(): void {
  clearTokens();
  window.location.href = '/admin/login';
}

export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  let token = getAccessToken();

  const makeRequest = async (accessToken: string | null) => {
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    return fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });
  };

  let response = await makeRequest(token);

  // If unauthorized, try to refresh
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      token = getAccessToken();
      response = await makeRequest(token);
    } else {
      logout();
    }
  }

  return response;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const r = await authFetch('/api/auth/me');
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}
