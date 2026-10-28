import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { Api, TOKEN_KEY } from "../services/api";
import type { Role, User } from "../types";

interface Ctx { user: User | null; loading: boolean; login: (u: string, p: string) => Promise<void>; logout: () => void; has: (...roles: Role[]) => boolean }
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!localStorage.getItem(TOKEN_KEY));
  const logout = useCallback(() => { localStorage.removeItem(TOKEN_KEY); setUser(null); }, []);

  useEffect(() => {
    if (localStorage.getItem(TOKEN_KEY)) Api.me().then(setUser).catch(logout).finally(() => setLoading(false));
    window.addEventListener("avis:logout", logout);
    return () => window.removeEventListener("avis:logout", logout);
  }, [logout]);

  const login = async (u: string, p: string) => {
    const r = await Api.login(u, p);
    localStorage.setItem(TOKEN_KEY, r.access_token);
    setUser(r.user);
  };
  const has = (...roles: Role[]) => !!user && (user.role === "admin" || roles.includes(user.role));
  return <AuthCtx.Provider value={{ user, loading, login, logout, has }}>{children}</AuthCtx.Provider>;
}
