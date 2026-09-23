"use client";

import { useQuery } from "@tanstack/react-query";
import { demandTrendsQueryOptions } from "@/entities/calculation-run";
import { useCalculationSessionStore } from "@/features/run-calculation";
import { formatNumber } from "@/shared/lib";
import { Card, ErrorMessage, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";

export function AnalyticsPage() {
  const runId = useCalculationSessionStore((state) => state.activeRunId);
  const trends = useQuery({ ...demandTrendsQueryOptions(runId ?? ""), enabled: runId !== null });

  return <AppShell>
    <header className="mb-6"><h1 className="text-3xl font-bold">Аналитика спроса</h1><p className="mt-2 text-sm text-muted-foreground">Тренды загружаются из сохранённого запуска расчёта.</p></header>
    {!runId ? <Card className="p-6 text-sm text-muted-foreground">Данных для графика пока нет. Сначала загрузите источники и выполните расчёт.</Card> : trends.isPending ? <Skeleton className="h-72" /> : trends.isError ? <ErrorMessage title="Не удалось загрузить тренды спроса" error={trends.error} onRetry={() => void trends.refetch()} /> : <Card className="overflow-hidden">
      {trends.data.length === 0 ? <p className="p-6 text-sm text-muted-foreground">Для этого запуска сервер не вернул точек тренда.</p> : <Table>
        <TableHeader><tr><TableHead>Категория</TableHead><TableHead>Период</TableHead><TableHead>Спрос</TableHead><TableHead>Очищенный спрос</TableHead><TableHead>Компенсация дефицита</TableHead></tr></TableHeader>
        <TableBody>{trends.data.map((point) => <TableRow key={`${point.category_id ?? "all"}-${point.period_start}-${point.period_end}`}>
          <TableCell className="font-mono text-xs">{point.category_id ?? "Все категории"}</TableCell>
          <TableCell>{point.period_start} — {point.period_end}</TableCell>
          <TableCell>{formatNumber(point.raw_demand)}</TableCell>
          <TableCell>{formatNumber(point.cleaned_demand)}</TableCell>
          <TableCell>{formatNumber(point.stockout_adjustment)}</TableCell>
        </TableRow>)}</TableBody>
      </Table>}
    </Card>}
  </AppShell>;
}
