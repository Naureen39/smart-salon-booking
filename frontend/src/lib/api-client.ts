// 8001, not the conventional 8000: that port is the single most likely one
// to already be taken by some other local FastAPI/Django project (see the
// matching backend port choice in docker-compose.yml).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

// Carries the backend's own error message (FastAPI's `{"detail": ...}`
// shape) instead of a generic "request failed" string, so callers that want
// to show the user something specific ("Email already registered", not just
// "Signup failed") can, while ones that don't still get a reasonable
// `.message` for free.
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail) && detail.length > 0 && typeof detail[0]?.msg === "string") {
        return detail[0].msg as string;
      }
    }
  } catch {
    // Response body wasn't JSON (or was empty); fall through to the generic message below.
  }
  return `Request failed (${response.status})`;
}

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
    throw new ApiError(await extractErrorMessage(response), response.status);
  }

  return response.json() as Promise<T>;
}
