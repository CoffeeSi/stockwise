"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { abcXyzQueryOptions, demandSeriesQueryOptions, outliersQueryOptions, type AnalyticsFilters } from "@/entities/analytics";
import { calculationRunsQueryOptions } from "@/entities/calculation-run";
import { categoriesQueryOptions, supplierOptionsQueryOptions, warehousesQueryOptions } from "@/entities/catalog";
import { ApiError } from "@/shared/api";
import { Button, Card, ErrorMessage, Skeleton } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";
import { formatAnalyticsDate } from "../lib/presentation";
import { analyticsFormSchema, type AnalyticsForm } from "../model/schema";
import { AbcXyzMatrix } from "./abc-xyz-matrix";
import { DemandSeriesChart } from "./demand-series-chart";
import { OutliersTable } from "./outliers-table";

const PAGE_SIZE = 20;
const control = "mt-2 h-11 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground disabled:opacity-50";

function AnalyticsError({ error, retry }: { error: Error; retry: () => void }) {
  if (error instanceof ApiError && error.code === "analytics_unavailable") {
    return <p className="py-8 text-sm text-muted-foreground">Данные недоступны: в этом историческом расчёте не сохранены нужные данные или правила аналитики. Запустите новый расчёт, чтобы получить этот отчёт.</p>;
  }
  return <ErrorMessage error={error} onRetry={retry} />;
}

export function AnalyticsPage({ initialRunId = null }: { initialRunId?: string | null }) {
  const defaults: AnalyticsForm = { runId: initialRunId ?? "", supplierId: "", warehouseId: "", categoryId: "", months: 24 };
  const [filters, setFilters] = useState<AnalyticsForm>(defaults);
  const [runOffset, setRunOffset] = useState(0);
  const [outlierPage, setOutlierPage] = useState<{ runId: string | null; offset: number }>({ runId: null, offset: 0 });
  const form = useForm<AnalyticsForm>({ resolver: zodResolver(analyticsFormSchema), defaultValues: defaults });
  const latestRuns = useQuery(calculationRunsQueryOptions({ status: "completed", limit: PAGE_SIZE, offset: 0 }));
  const runs = useQuery(calculationRunsQueryOptions({ status: "completed", limit: PAGE_SIZE, offset: runOffset }));
  const suppliers = useQuery(supplierOptionsQueryOptions({ active_only: false }));
  const warehouses = useQuery(warehousesQueryOptions({ active_only: false }));
  const categories = useQuery(categoriesQueryOptions({ active_only: false }));
  const runId = filters.runId || latestRuns.data?.items[0]?.id || null;
  const activeFilters: AnalyticsFilters = {
    ...(filters.supplierId ? { supplier_id: filters.supplierId } : {}),
    ...(filters.warehouseId ? { warehouse_id: filters.warehouseId } : {}),
    ...(filters.categoryId ? { category_id: filters.categoryId } : {}),
  };
  const series = useQuery({ ...demandSeriesQueryOptions(runId ?? "", { ...activeFilters, months: filters.months }), enabled: runId !== null });
  const matrix = useQuery({ ...abcXyzQueryOptions(runId ?? "", activeFilters), enabled: runId !== null });
  const offset = outlierPage.runId === runId ? outlierPage.offset : 0;
  const outliers = useQuery({ ...outliersQueryOptions(runId ?? "", { ...activeFilters, limit: PAGE_SIZE, offset }), enabled: runId !== null });
  const errors = form.formState.errors;
  const draftRunId = form.watch("runId");
  const knownRuns = runs.data?.items ?? [];
  const warehouseNames = new Map<string, string>(warehouses.data?.items.map((warehouse) => [warehouse.id, warehouse.name] as const));
  const catalogError = suppliers.error ?? warehouses.error ?? categories.error;
  const refresh = () => {
    void latestRuns.refetch();
    if (runOffset !== 0) void runs.refetch();
    if (runId) { void series.refetch(); void matrix.refetch(); void outliers.refetch(); }
  };
  const applyFilters = (values: AnalyticsForm) => {
    setFilters(values);
    setOutlierPage({ runId: null, offset: 0 });
  };

  return <AppShell>
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold">Аналитика спроса</h1><p className="mt-2 text-sm text-muted-foreground">Сохранённый спрос, структура закупки и исключённые крупные продажи.</p></div><Button type="button" variant="secondary" onClick={refresh} disabled={series.isFetching || matrix.isFetching || outliers.isFetching || latestRuns.isFetching}><RefreshCw className="h-4 w-4" />Обновить</Button></header>
    <Card className="mb-6 p-5">
      <form className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" onSubmit={form.handleSubmit(applyFilters)}>
        <label className="text-sm">Завершённый расчёт<select className={control} {...form.register("runId")} aria-invalid={!!errors.runId}>
          <option value="">Последний завершённый</option>
          {draftRunId && !knownRuns.some((run) => run.id === draftRunId) && <option value={draftRunId}>Выбранный расчёт · {draftRunId.slice(0, 8)}</option>}
          {knownRuns.map((run) => <option key={run.id} value={run.id}>{formatAnalyticsDate(run.started_at)} · {run.id.slice(0, 8)}</option>)}
        </select>{errors.runId && <span className="mt-1 block text-xs text-red-500" role="alert">Выберите расчёт из списка.</span>}</label>
        <label className="text-sm">Поставщик<select className={control} {...form.register("supplierId")} disabled={suppliers.isPending || suppliers.isError} aria-invalid={!!errors.supplierId}><option value="">Все поставщики</option>{suppliers.data?.map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_active ? "" : " · архив"}</option>)}</select>{errors.supplierId && <span className="mt-1 block text-xs text-red-500" role="alert">Выберите поставщика из справочника.</span>}</label>
        <label className="text-sm">Склад<select className={control} {...form.register("warehouseId")} disabled={warehouses.isPending || warehouses.isError} aria-invalid={!!errors.warehouseId}><option value="">Все склады</option>{warehouses.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_active ? "" : " · архив"}</option>)}</select>{errors.warehouseId && <span className="mt-1 block text-xs text-red-500" role="alert">Выберите склад из справочника.</span>}</label>
        <label className="text-sm">Категория<select className={control} {...form.register("categoryId")} disabled={categories.isPending || categories.isError} aria-invalid={!!errors.categoryId}><option value="">Все категории</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_active ? "" : " · архив"}</option>)}</select>{errors.categoryId && <span className="mt-1 block text-xs text-red-500" role="alert">Выберите категорию из справочника.</span>}</label>
        <label className="text-sm">Окно графика<select className={control} {...form.register("months", { valueAsNumber: true })} aria-invalid={!!errors.months}><option value={6}>До 6 месяцев</option><option value={12}>До 12 месяцев</option><option value={24}>До 24 месяцев</option></select>{errors.months && <span className="mt-1 block text-xs text-red-500" role="alert">Выберите период от 1 до 24 месяцев.</span>}</label>
        <div className="flex items-end gap-2"><Button type="submit">Применить</Button><Button type="button" variant="secondary" onClick={() => { const reset: AnalyticsForm = { runId: "", supplierId: "", warehouseId: "", categoryId: "", months: 24 }; form.reset(reset); applyFilters(reset); setRunOffset(0); }}>Сбросить</Button></div>
      </form>
      {runs.isError && <div className="mt-4"><ErrorMessage title="Не удалось загрузить список расчётов" error={runs.error} onRetry={() => void runs.refetch()} /></div>}
      {runs.data && runs.data.total > PAGE_SIZE && <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-border pt-4"><p className="text-xs text-muted-foreground">В списке расчёты {runOffset + 1}–{runOffset + runs.data.items.length} из {runs.data.total}</p><Button type="button" size="sm" variant="ghost" disabled={runOffset === 0 || runs.isFetching} onClick={() => setRunOffset(Math.max(0, runOffset - PAGE_SIZE))}><ChevronLeft className="h-4 w-4" />Новее</Button><Button type="button" size="sm" variant="ghost" disabled={runOffset + PAGE_SIZE >= runs.data.total || runs.isFetching} onClick={() => setRunOffset(runOffset + PAGE_SIZE)}>Ранее<ChevronRight className="h-4 w-4" /></Button></div>}
      {catalogError && <div className="mt-4"><ErrorMessage title="Часть справочников недоступна" error={catalogError} onRetry={() => { void suppliers.refetch(); void warehouses.refetch(); void categories.refetch(); }} /></div>}
    </Card>
    {!runId ? latestRuns.isPending ? <Skeleton className="h-72 rounded-2xl" /> : latestRuns.isError ? <ErrorMessage title="Не удалось найти завершённый расчёт" error={latestRuns.error} onRetry={() => void latestRuns.refetch()} /> : <Card className="p-8 text-sm text-muted-foreground">Завершённых расчётов пока нет. Загрузите источники и выполните расчёт, чтобы увидеть аналитику.</Card> : <>
      <p className="mb-4 text-xs text-muted-foreground">Расчёт <span className="font-mono">{runId}</span>. Фильтры применяются к данным этого запуска.</p>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <Card className="min-w-0 p-5"><h2 className="text-lg font-semibold">Спрос по месяцам</h2><p className="mb-5 mt-1 text-xs text-muted-foreground">Фактические продажи и спрос после очистки и компенсации дефицита.</p>{series.isPending ? <Skeleton className="h-72 rounded-xl" /> : series.isError ? <AnalyticsError error={series.error} retry={() => void series.refetch()} /> : <DemandSeriesChart data={series.data} />}</Card>
        <Card className="min-w-0 p-5"><h2 className="text-lg font-semibold">Матрица ABC / XYZ</h2><p className="mb-5 mt-1 text-xs text-muted-foreground">Количество SKU и доля очищенного спроса. Используется вся сохранённая история.</p>{matrix.isPending ? <Skeleton className="h-72 rounded-xl" /> : matrix.isError ? <AnalyticsError error={matrix.error} retry={() => void matrix.refetch()} /> : <AbcXyzMatrix data={matrix.data} />}</Card>
      </div>
      <Card className="mt-5 overflow-hidden"><div className="p-5"><h2 className="text-lg font-semibold">Исключённые крупные продажи</h2><p className="mt-1 text-xs text-muted-foreground">Транзакционные аномалии этого расчёта. Исходные продажи сохранены без изменений.</p></div>{outliers.isPending ? <div className="p-5"><Skeleton className="h-48 rounded-xl" /></div> : outliers.isError ? <div className="p-5"><AnalyticsError error={outliers.error} retry={() => void outliers.refetch()} /></div> : <OutliersTable data={outliers.data} isFetching={outliers.isFetching} onPage={(nextOffset) => setOutlierPage({ runId, offset: nextOffset })} warehouses={warehouseNames} />}</Card>
    </>}
  </AppShell>;
}
