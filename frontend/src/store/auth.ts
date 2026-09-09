import { create } from "zustand";

import * as authApi from "@/lib/auth-api";

interface AuthState {
  accessToken: string | null;
  user: authApi.UserRead | null;
  isHydrating: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: { email: string; password: string; full_name: string; phone?: string }) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
}

// The access token lives only in memory (not localStorage): it's short-lived
// (15 min) by design, and the httpOnly refresh cookie the backend already
// sets on login is what actually persists the session across a page reload.
// `hydrate()` calls /auth/refresh once on app start to silently restore a
// session from that cookie, matching how the backend's rotation model was
// designed to be used rather than bolting on a second, less secure
// persistence mechanism.
//
// De-duplicated via a module-level in-flight promise: refresh tokens are
// single-use (rotated on every call), so React StrictMode's deliberate
// double-invocation of effects in development would otherwise fire two
// concurrent /auth/refresh calls, one succeeds and rotates the cookie, the
// other then fails on the now-stale token, whichever resolves last wins,
// so an already-restored session could get silently wiped back to logged
// out. Sharing one in-flight request makes a second concurrent call just
// await the first's result instead of firing a real duplicate request.
let hydratePromise: Promise<void> | null = null;

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  isHydrating: true,

  login: async (email, password) => {
    const { access_token } = await authApi.login(email, password);
    const user = await authApi.me(access_token);
    set({ accessToken: access_token, user });
  },

  signup: async (payload) => {
    await authApi.signup(payload);
    const { access_token } = await authApi.login(payload.email, payload.password);
    const user = await authApi.me(access_token);
    set({ accessToken: access_token, user });
  },

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      set({ accessToken: null, user: null });
    }
  },

  hydrate: () => {
    if (!hydratePromise) {
      hydratePromise = (async () => {
        try {
          const { access_token } = await authApi.refresh();
          const user = await authApi.me(access_token);
          set({ accessToken: access_token, user, isHydrating: false });
        } catch {
          set({ accessToken: null, user: null, isHydrating: false });
        }
      })();
    }
    return hydratePromise;
  },
}));
