import { useQuery } from "@tanstack/react-query";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { Api } from "../services/api";
import type { Mode } from "../types";
import { useAuth } from "./AuthContext";

interface Ctx { mode: Mode; setMode: (m: Mode) => void; realAvailable: boolean; realMessage: string }
const ModeCtx = createContext<Ctx>(null as unknown as Ctx);
export const useMode = () => useContext(ModeCtx);

export function ModeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [mode] = useState<Mode>("real");
  const st = useQuery({ queryKey: ["models-status"], queryFn: Api.modelsStatus, enabled: !!user, refetchInterval: 30000 });
  const realAvailable = !!st.data?.real_mode_available;
  const setMode = (_m: Mode) => {
    // Demo mode is removed; inference is exclusively real AI
  };
  return <ModeCtx.Provider value={{ mode, setMode, realAvailable, realMessage: st.data?.message ?? "" }}>{children}</ModeCtx.Provider>;
}
