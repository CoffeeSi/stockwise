"use client";
import { createContext, useContext, type ReactNode } from "react";
import type { User } from "./schema";
const SessionContext = createContext<User | null>(null);
export function SessionUserProvider({ user, children }: { user: User; children: ReactNode }) { return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>; }
export function useSessionUser() { return useContext(SessionContext); }
