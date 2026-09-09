// 8001, not the conventional 8000: that port is the single most likely one
// to already be taken by some other local FastAPI/Django project (see the
// matching backend port choice in docker-compose.yml).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

export async function apiFetch<T>(path: string, init?: RequestInit, accessToken?: string | null): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}
