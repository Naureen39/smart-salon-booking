import { apiFetch } from "@/lib/api-client";

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export function signup(payload: {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}): Promise<UserRead> {
  return apiFetch<UserRead>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify(payload) });
}

export function login(email: string, password: string): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    credentials: "include",
  });
}

export function refresh(): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
}

export function logout(): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>("/api/v1/auth/logout", { method: "POST", credentials: "include" });
}

export function me(accessToken: string): Promise<UserRead> {
  return apiFetch<UserRead>("/api/v1/auth/me", undefined, accessToken);
}
