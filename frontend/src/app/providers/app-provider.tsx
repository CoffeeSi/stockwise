"use client";

import type { ReactNode } from "react";
import { SessionGate } from "@/features/auth-session";
import { QueryProvider } from "./query-provider";
import { ThemeProvider } from "./theme-provider";

export function AppProvider({ children }: { children: ReactNode }) {
  return <ThemeProvider><QueryProvider><SessionGate>{children}</SessionGate></QueryProvider></ThemeProvider>;
}
