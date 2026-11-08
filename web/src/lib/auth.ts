const TOKEN_KEY = 'medbalance.auth.token';
const USER_KEY = 'medbalance.auth.user';

export interface AuthUser {
  user_id: string;
  role: string;
  name: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  name: string;
  expires_in: number;
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setAuth(resp: LoginResponse): void {
  sessionStorage.setItem(TOKEN_KEY, resp.access_token);
  sessionStorage.setItem(USER_KEY, JSON.stringify({
    user_id: resp.role,
    role: resp.role,
    name: resp.name,
  }));
}

export function clearAuth(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch('/api/core/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(body.detail ?? body.error ?? 'Login failed');
  }
  const data = await res.json() as LoginResponse;
  setAuth(data);
  return data;
}

export async function fetchUsers(): Promise<{ username: string; role: string; name: string }[]> {
  const res = await fetch('/api/core/auth/users');
  if (!res.ok) return [];
  return res.json();
}

export function logout(): void {
  clearAuth();
  window.location.reload();
}
