"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { calculationRunQueryOptions, calculationRunsQueryOptions, runRecommendationsQueryOptions, type RunRecommendationFilters } from "@/entities/calculation-run";
import { useSessionUser } from "@/entities/user";
import { AcceptRecommendationsAction } from "@/features/accept-recommendations";
import { ApproveAction } from "@/features/approve-order";
import { RecommendationFilters } from "@/features/filter-recommendations";
import { RunCalculationAction, useCalculationSessionStore } from "@/features/run-calculation";
import { useSelectionStore } from "@/features/select-items";
import { formatNumber } from "@/shared/lib";
import { Badge, Button, Card, ErrorMessage, Skeleton } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";
import { RunRecommendationsTable } from "@/widgets/run-recommendations";
import { runSelectionSchema, type RunSelection } from "../model/schema";

const runStatusLabels = { pending: "Ожидает", running: "Выполняется", completed: "Завершён", failed: "Ошибка" } as const;
const PAGE_SIZE = 50;

export function InventoryPage({ initialRunId = null, initialSearch = "" }: { initialRunId?: string | null; initialSearch?: string }) {
  const user = useSessionUser();
  const canWrite = user?.role === "buyer" || user?.role === "admin";
  const sessionRunId = useCalculationSessionStore((state) => state.activeRunId);
  const setActiveRunId = useCalculationSessionStore((state) => state.setActiveRunId);
  const [historyOffset, setHistoryOffset] = useState(0);
  const latest = useQuery(calculationRunsQueryOptions({ status: "completed", limit: 1, offset: 0 }));
  const history = useQuery(calculationRunsQueryOptions({ limit: 20, offset: historyOffset }));
  const activeRunId = sessionRunId ?? initialRunId ?? latest.data?.items[0]?.id ?? history.data?.items[0]?.id ?? null;
  const form = useForm<RunSelection>({ resolver: zodResolver(runSelectionSchema), values: { runId: activeRunId ?? "" } });

  useEffect(() => { if (initialRunId) setActiveRunId(initialRunId); }, [initialRunId, setActiveRunId]);

  return <AppShell>
    <header className="mb-6"><h1 className="text-3xl font-bold tracking-tight">Управление пополнением</h1><p className="mt-2 text-sm text-muted-foreground">Сохранённые результаты расчётов, принятие рекомендаций и формирование заказов.</p></header>
    <Card className="mb-5 space-y-3 p-4">
      <form onSubmit={form.handleSubmit(({ runId }) => setActiveRunId(runId))} className="flex flex-wrap items-end gap-3">
        <label className="min-w-64 flex-1 text-sm">История расчётов<select className="mt-2 h-11 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground" {...form.register("runId")}>
          <option value="">Выберите расчёт</option>
          {activeRunId && !history.data?.items.some((run) => run.id === activeRunId) && <option value={activeRunId}>Открытый расчёт · {activeRunId}</option>}
          {history.data?.items.map((run) => <option key={run.id} value={run.id}>{new Date(run.started_at).toLocaleString("ru-RU")} · {runStatusLabels[run.status]} · {run.id.slice(0, 8)}</option>)}
        </select>{form.formState.errors.runId && <span role="alert" className="mt-1 block text-xs text-destructive">{form.formState.errors.runId.message}</span>}</label>
        <Button type="submit" disabled={history.isPending}>Открыть</Button>
        <Button type="button" variant="secondary" disabled={!latest.data?.items[0]} onClick={() => { const id = latest.data?.items[0]?.id; if (id) setActiveRunId(id); }}>Последний завершённый</Button>
      </form>
      {history.isError ? <ErrorMessage title="История расчётов недоступна" error={history.error} onRetry={() => void history.refetch()} /> : history.data && <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"><span>Расчётов: {history.data.total}. Сортировка: сначала новые.</span><div className="flex gap-2"><Button type="button" size="sm" variant="ghost" disabled={historyOffset === 0 || history.isFetching} onClick={() => setHistoryOffset((value) => Math.max(0, value - 20))}>Новые</Button><Button type="button" size="sm" variant="ghost" disabled={historyOffset + 20 >= history.data.total || history.isFetching} onClick={() => setHistoryOffset((value) => value + 20)}>Старые</Button></div></div>}
    </Card>
    {activeRunId ? <RecommendationWorkspace key={`${activeRunId}:${initialSearch}`} runId={activeRunId} initialSearch={initialSearch} /> : latest.isPending || history.isPending ? <Skeleton className="h-48" /> : latest.isError ? <ErrorMessage title="Не удалось найти завершённый расчёт" error={latest.error} onRetry={() => void latest.refetch()} /> : <Card className="space-y-4 p-6 text-sm text-muted-foreground"><p>{canWrite ? "Расчётов пока нет. После загрузки источников запустите новый расчёт — импорт сам по себе его не создаёт." : "Расчётов пока нет. Для запуска расчёта обратитесь к закупщику или администратору."}</p>{canWrite && <RunCalculationAction horizonDays={30} />}</Card>}
  </AppShell>;
}

function RecommendationWorkspace({ runId, initialSearch }: { runId: string; initialSearch: string }) {
  const user = useSessionUser();
  const canWrite = user?.role === "buyer" || user?.role === "admin";
  const [filters, setFilters] = useState<RunRecommendationFilters>({ ...(initialSearch ? { search: initialSearch } : {}), limit: PAGE_SIZE, offset: 0 });
  const selectionScope = `${runId}:${JSON.stringify(filters)}`;
  const storedScope = useSelectionStore((state) => state.scope);
  const storedIds = useSelectionStore((state) => state.selectedIds);
  const setScope = useSelectionStore((state) => state.setScope);
  const toggle = useSelectionStore((state) => state.toggle);
  const selectMany = useSelectionStore((state) => state.selectMany);
  const clearMany = useSelectionStore((state) => state.clearMany);
  const clear = useSelectionStore((state) => state.clear);
  const selectedIds = storedScope === selectionScope ? storedIds : [];
  const run = useQuery({ ...calculationRunQueryOptions(runId), refetchInterval: (query) => query.state.data?.status === "pending" || query.state.data?.status === "running" ? 2000 : false });
  const recommendations = useQuery({ ...runRecommendationsQueryOptions(runId, filters), enabled: run.data?.status === "completed" });
  const rows = recommendations.data?.items ?? [];
  const selectedRows = rows.filter((row) => selectedIds.includes(row.id) && ["suggested", "adjusted", "accepted"].includes(row.status) && row.effective_quantity > 0);
  const acceptedIds = selectedRows.filter((row) => row.status === "accepted").map((row) => row.id);
  const runData = run.data;
  const budget = runData?.budget_limit ?? runData?.parameters.budget_limit;
  const allocated = runData?.allocated_amount ?? runData?.parameters.allocated_amount;
  const unmet = runData?.unmet_need_amount ?? runData?.parameters.unmet_need_amount;
  const currency = runData?.currency ?? runData?.parameters.currency ?? "";

  useEffect(() => { setScope(selectionScope); }, [selectionScope, setScope]);

  return <section className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Рекомендации расчёта</h2><p className="mt-1 break-all font-mono text-xs text-muted-foreground">{runId}</p></div>{runData && <Badge tone={runData.status === "completed" ? "green" : runData.status === "failed" ? "red" : "blue"}>{runStatusLabels[runData.status]}</Badge>}</div>
    {run.isPending ? <Skeleton className="h-32" /> : run.isError ? <ErrorMessage title="Не удалось загрузить расчёт" error={run.error} onRetry={() => void run.refetch()} /> : runData && <>
      {(runData.status === "pending" || runData.status === "running") && <Card className="p-5 text-sm" role="status">{runData.status === "pending" ? "Расчёт поставлен в очередь." : "Сервер выполняет расчёт."}{runData.progress && <p className="mt-2 text-muted-foreground">Этап: {runData.progress.phase}. Обработано: {runData.progress.completed} из {runData.progress.total}.</p>}</Card>}
      {runData.status === "failed" && <Card className="p-5 text-sm text-destructive" role="alert">{runData.error_details?.code === "supplier_terms_missing" ? "Для части товаров нет условий поставщика. Загрузите MOQ и запустите новый расчёт." : runData.error_details?.code === "missing_imports" ? "Нет завершённых загрузок. Дождитесь обработки файлов и запустите новый расчёт." : "Расчёт завершился ошибкой. Проверьте загруженные данные, условия поставщиков и параметры бюджета, затем создайте новый запуск."}</Card>}
      {runData.status === "completed" && <>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground"><span>Алгоритм: {runData.algorithm_version}</span><span>Всего рекомендаций: {runData.recommendation_count ?? "не указано"}</span><span>Импортов в снимке: {runData.import_batch_ids.length}</span></div>
        {budget !== undefined && budget !== null && <Card className="grid gap-3 p-4 text-sm sm:grid-cols-3"><p>Лимит: <strong>{formatNumber(budget)} {currency}</strong></p><p>Распределено: <strong>{allocated === undefined || allocated === null ? "Нет данных" : `${formatNumber(allocated)} ${currency}`}</strong></p><p>Непокрытая потребность: <strong>{unmet === undefined || unmet === null ? "Нет данных" : `${formatNumber(unmet)} ${currency}`}</strong></p></Card>}
        <RecommendationFilters initialSearch={initialSearch} onApply={(values) => { clear(); setFilters({ ...values, limit: PAGE_SIZE, offset: 0 }); }} />
        {recommendations.isPending ? <Skeleton className="h-64" /> : recommendations.isError ? <ErrorMessage title="Не удалось загрузить рекомендации" error={recommendations.error} onRetry={() => void recommendations.refetch()} /> : recommendations.data && <Card className="overflow-hidden">
          <RunRecommendationsTable items={rows} selectedIds={selectedIds} onToggle={toggle} onSelectMany={selectMany} onClearMany={clearMany} />
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border p-4 text-xs text-muted-foreground"><p>Показано {rows.length === 0 ? 0 : recommendations.data.offset + 1}–{recommendations.data.offset + rows.length} из {recommendations.data.total}. Поиск и фильтры применены на сервере.</p><div className="flex gap-2"><Button type="button" size="sm" variant="secondary" disabled={recommendations.data.offset === 0 || recommendations.isFetching} onClick={() => { clear(); setFilters((current) => ({ ...current, offset: Math.max(0, (current.offset ?? 0) - PAGE_SIZE) })); }}>Назад</Button><Button type="button" size="sm" variant="secondary" disabled={recommendations.data.offset + recommendations.data.limit >= recommendations.data.total || recommendations.isFetching} onClick={() => { clear(); setFilters((current) => ({ ...current, offset: (current.offset ?? 0) + PAGE_SIZE })); }}>Далее</Button></div></div>
        </Card>}
        {canWrite && <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4"><div><p className="text-sm">Выбрано на странице: {selectedRows.length}. Принятых: {acceptedIds.length}.</p><p className="mt-1 text-xs text-muted-foreground">При смене страницы, расчёта или фильтров выбор очищается.</p></div><AcceptRecommendationsAction runId={runId} items={selectedRows} /></div>
          <ApproveAction runId={runId} selectedRecommendationIds={acceptedIds} onSelectionConsumed={clearMany} />
        </>}
      </>}
    </>}
  </section>;
}
