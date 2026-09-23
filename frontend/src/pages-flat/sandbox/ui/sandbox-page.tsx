"use client";

import { RunCalculationAction } from "@/features/run-calculation";
import { PreviewScenario } from "@/features/preview-scenario";
import { useSessionUser } from "@/entities/user";
import { useHorizonStore } from "@/features/set-horizon";
import { Card } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";

export function SandboxPage() {
  const user = useSessionUser();
  const horizonDays = useHorizonStore((state) => state.days);
  return <AppShell><header className="mb-6"><h1 className="text-3xl font-bold">Финансовая песочница</h1><p className="mt-2 text-sm text-muted-foreground">Сравните предположения с сохранённым расчётом и запустите новый расчёт с бюджетом.</p></header><div className="space-y-6"><PreviewScenario />{(user?.role === "buyer" || user?.role === "admin") && <Card className="p-6"><h2 className="mb-4 text-xl font-bold">Новый сохранённый расчёт</h2><RunCalculationAction horizonDays={horizonDays} /></Card>}</div></AppShell>;
}
