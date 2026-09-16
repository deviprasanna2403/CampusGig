/**
 * Auth state: user + JWT pair in context, persisted to localStorage via the
 * token store. Role helpers drive RoleRoute and role-aware redirects.
 *
 * Session-expiry sync: the API client dispatches "cg:session-expired" when a
 * refresh fails; this context listens and resets so ProtectedRoute bounces
 * the user to /login.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { tokenStore } from "../api/client";
import * as authApi from "../api/auth";
import type { Role, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean; // true while the initial session restore runs
  login: (email: string, password: string) => Promise<void>;
  register: (input: authApi.RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem("cg.user");
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser);
  const [loading, setLoading] = useState(true);

  // Restore the session once on mount: if tokens exist, ask /auth/me/ who
  // we are (also catches revoked/invalid tokens early).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!tokenStore.access) {
        setLoading(false);
        return;
      }
      try {
        const u = await authApi.me();
        if (!cancelled) {
          setUser(u);
          localStorage.setItem("cg.user", JSON.stringify(u));
        }
      } catch {
        // 401 path already cleared the store via the interceptor chain.
        if (!cancelled && !tokenStore.access) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Session expired elsewhere (refresh failure in the API client).
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener("cg:session-expired", onExpired);
    return () => window.removeEventListener("cg:session-expired", onExpired);
  }, []);

  const persistUser = useCallback((u: User) => {
    localStorage.setItem("cg.user", JSON.stringify(u));
    setUser(u);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access, refresh, user: u } = await authApi.login({ email, password });
      tokenStore.set(access, refresh);
      persistUser(u);
    },
    [persistUser],
  );

  const register = useCallback(
    async (input: authApi.RegisterInput) => {
      const { access, refresh, user: u } = await authApi.register(input);
      tokenStore.set(access, refresh);
      persistUser(u);
    },
    [persistUser],
  );

  const logout = useCallback(async () => {
    try {
      const refresh = tokenStore.refresh;
      if (refresh) await authApi.logout(refresh); // blacklist server-side
    } catch {
      // Best-effort: even if the blacklist call fails, drop local state.
    } finally {
      tokenStore.clear();
      setUser(null);
    }
  }, []);

  const hasRole = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user]);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, hasRole }),
    [user, loading, login, register, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
