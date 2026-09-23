"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { runRecommendationsQueryOptions } from "@/entities/calculation-run";
import type { Order } from "@/entities/order";
import { ApproveAction } from "@/features/approve-order";
import { ExportMenu } from "@/features/export-order";
import { useCalculationSessionStore } from "@/features/run-calculation";
import { Button, Card, ErrorMessage, Skeleton } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";
import { RunRecommendationsTable } from "@/widgets/run-recommendations";

export function InventoryPage({ initialRunId = null }: { initialRunId?: string | null }) {
  const sessionRunId = useCalculationSessionStore((state) => state.activeRunId);
  const setActiveRunId = useCalculationSessionStore((state) => state.setActiveRunId);
  const activeRunId = initialRunId ?? sessionRunId;
  const [runOffset, setRunOffset] = useState(0);
  const [orders, setOrders] = useState<Order[]>([]);
  const recommendations = useQuery({
    ...runRecommendationsQueryOptions(activeRunId ?? "", { limit: 50, offset: runOffset }),
    enabled: activeRunId !== null,
  });

  useEffect(() => {
    if (initialRunId) setActiveRunId(initialRunId);
    setRunOffset(0);
  }, [initialRunId, setActiveRunId]);

  return <AppShell>
    <header className="mb-6">
      <h1 className="text-3xl font-bold tracking-tight">Управление пополнением</h1>
      <p className="mt-2 text-sm text-muted-foreground">Рекомендации отображаются из сохранённых запусков расчёта.</p>
    </header>

    {!activeRunId ? <Card className="p-6 text-sm text-muted-foreground">Пока нет выбранного расчёта. Загрузите исходные данные и запустите расчёт.</Card> : <section className="space-y-4">
      <div><h2 className="text-xl font-bold">Рекомендации расчёта</h2><p className="mt-1 font-mono text-xs text-muted-foreground">Run ID: {activeRunId}</p></div>
      {recommendations.isPending ? <Skeleton className="h-64" /> : recommendations.isError ? <ErrorMessage title="Не удалось загрузить рекомендации расчёта" error={recommendations.error} onRetry={() => void recommendations.refetch()} /> : <Card className="overflow-hidden">
        <RunRecommendationsTable items={recommendations.data.items} />
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border p-4 text-xs text-muted-foreground">
          <p>Показано {recommendations.data.items.length === 0 ? 0 : runOffset + 1}–{runOffset + recommendations.data.items.length} из {recommendations.data.total}.</p>
          <div className="flex gap-2"><Button type="button" size="sm" variant="secondary" disabled={runOffset === 0} onClick={() => setRunOffset((value) => Math.max(0, value - 50))}>Назад</Button><Button type="button" size="sm" variant="secondary" disabled={runOffset + 50 >= recommendations.data.total} onClick={() => setRunOffset((value) => value + 50)}>Далее</Button></div>
        </div>
      </Card>}
      <ApproveAction runId={activeRunId} onOrdersCreated={setOrders} onOrderApproved={(updated) => setOrders((current) => current.map((order) => order.id === updated.id ? updated : order))} />
      {orders.filter((order) => order.status === "approved" || order.status === "exported").map((order) => <Card key={order.id} className="p-4"><p className="mb-3 text-sm font-semibold">{order.order_number}</p><ExportMenu order={order} /></Card>)}
    </section>}
  </AppShell>;
}
