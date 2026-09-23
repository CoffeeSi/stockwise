"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { calculationRunKeys, calculationRunQueryOptions } from "@/entities/calculation-run";
import { categoriesQueryOptions, warehousesQueryOptions } from "@/entities/catalog";
import { useSessionUser } from "@/entities/user";
import { Button, ErrorMessage, Input } from "@/shared/ui";
import { useRunCalculation } from "../api/use-run-calculation";
import { runCalculationSchema, type RunCalculationInput } from "../model/schema";
import { useCalculationSessionStore } from "../model/run-session";

type Props = { horizonDays: number; warehouseId?: string | null; categoryId?: string | null; onCompleted?: (runId: string) => void; openRequest?: number };
const selectClass = "mt-1.5 h-11 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground disabled:opacity-50";

export function RunCalculationAction({ horizonDays, warehouseId, categoryId, onCompleted, openRequest = 0 }: Props) {
  const user = useSessionUser();
  const canWrite = user?.role === "buyer" || user?.role === "admin";
  const dialog = useRef<HTMLDialogElement>(null);
  const notified = useRef<string | null>(null);
  const client = useQueryClient();
  const activeRunId = useCalculationSessionStore((state) => state.activeRunId);
  const warehouses = useQuery({ ...warehousesQueryOptions(), enabled: canWrite });
  const categories = useQuery({ ...categoriesQueryOptions(), enabled: canWrite });
  const form = useForm<RunCalculationInput>({
    resolver: zodResolver(runCalculationSchema),
    defaultValues: { demand_source: "transactions", horizon_days: horizonDays, warehouse_id: warehouseId ?? null, category_id: categoryId ?? null, budget_limit: null, currency: null },
  });
  const mutation = useRunCalculation();
  const { setValue } = form;
  const runQuery = useQuery({
    ...calculationRunQueryOptions(activeRunId ?? ""), enabled: activeRunId !== null,
    refetchInterval: (query) => query.state.data?.status === "pending" || query.state.data?.status === "running" ? 2000 : false,
  });
  const run = runQuery.data;
  const running = mutation.isPending || run?.status === "pending" || run?.status === "running";
  const errors = form.formState.errors;
  const catalogError = warehouses.error ?? categories.error;

  useEffect(() => { setValue("horizon_days", horizonDays); }, [horizonDays, setValue]);
  useEffect(() => { if (openRequest > 0 && !dialog.current?.open) dialog.current?.showModal(); }, [openRequest]);
  useEffect(() => {
    if (run?.status === "completed" && notified.current !== run.id) {
      notified.current = run.id;
      void client.invalidateQueries({ queryKey: calculationRunKeys.lists() });
      onCompleted?.(run.id);
    }
  }, [run?.status, run?.id, client, onCompleted]);

  if (!canWrite) return null;
  return <>
    <Button type="button" size="sm" variant="secondary" onClick={() => dialog.current?.showModal()}><Calculator className="h-4 w-4" />{running ? "Статус расчёта" : "Новый расчёт"}</Button>
    <dialog ref={dialog} className="m-auto max-h-[90vh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto rounded-3xl border border-border bg-card p-6 text-foreground shadow-2xl backdrop:bg-background/80">
      <div className="mb-5 flex items-center justify-between gap-4"><h2 className="text-xl font-bold">Расчёт потребности</h2><Button type="button" variant="ghost" size="icon" aria-label="Закрыть расчёт" onClick={() => dialog.current?.close()}><X className="h-4 w-4" /></Button></div>
      <form className="grid gap-4 sm:grid-cols-2" noValidate onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <label className="text-sm">Источник спроса<select className={selectClass} disabled={running} {...form.register("demand_source")}><option value="transactions">Продажи по документам</option><option value="monthly_sales">Продажи по месяцам</option></select>{errors.demand_source && <span role="alert" className="text-xs text-destructive">{errors.demand_source.message}</span>}</label>
        <label className="text-sm">Горизонт, дней<Input className="mt-1.5" type="number" min={1} max={365} step={1} disabled={running} {...form.register("horizon_days", { valueAsNumber: true })} />{errors.horizon_days && <span role="alert" className="text-xs text-destructive">{errors.horizon_days.message}</span>}</label>
        <label className="text-sm">Склад<select className={selectClass} disabled={running || warehouses.isPending} {...form.register("warehouse_id", { setValueAs: (value: string) => value || null })}><option value="">Все склады</option>{warehouses.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{errors.warehouse_id && <span role="alert" className="text-xs text-destructive">{errors.warehouse_id.message}</span>}</label>
        <label className="text-sm">Категория<select className={selectClass} disabled={running || categories.isPending} {...form.register("category_id", { setValueAs: (value: string) => value || null })}><option value="">Все категории</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{errors.category_id && <span role="alert" className="text-xs text-destructive">{errors.category_id.message}</span>}</label>
        <label className="text-sm">Лимит бюджета<Input className="mt-1.5" inputMode="decimal" placeholder="Без ограничения" disabled={running} {...form.register("budget_limit", { setValueAs: (value: unknown) => typeof value === "string" ? value.trim() || null : null })} />{errors.budget_limit && <span role="alert" className="text-xs text-destructive">{errors.budget_limit.message}</span>}</label>
        <label className="text-sm">Валюта бюджета<Input className="mt-1.5 uppercase" maxLength={3} placeholder="KZT" disabled={running} {...form.register("currency", { setValueAs: (value: unknown) => typeof value === "string" ? value.trim().toUpperCase() || null : null })} />{errors.currency && <span role="alert" className="text-xs text-destructive">{errors.currency.message}</span>}</label>
        <p className="text-xs text-muted-foreground sm:col-span-2">Бюджет проверяется по сохранённым закупочным ценам. При неизвестной цене или смешанных валютах сервер отклонит бюджетный расчёт.</p>
        <div className="sm:col-span-2"><Button type="submit" disabled={running || warehouses.isPending || categories.isPending || !!catalogError}><Calculator className="h-4 w-4" />{running ? "Расчёт выполняется…" : "Запустить расчёт"}</Button></div>
      </form>
      {catalogError && <div className="mt-4"><ErrorMessage title="Справочники недоступны" error={catalogError} onRetry={() => { void warehouses.refetch(); void categories.refetch(); }} /></div>}
      {mutation.isError && <div className="mt-4"><ErrorMessage title="Не удалось запустить расчёт" error={mutation.error} /><p className="mt-2 text-xs text-muted-foreground">После потери соединения повторите отправку тех же параметров: ключ запроса сохранён, повторный расчёт не создастся.</p></div>}
      {runQuery.isError && <div className="mt-4"><ErrorMessage title="Не удалось получить статус расчёта" error={runQuery.error} onRetry={() => void runQuery.refetch()} /></div>}
      {mutation.isPending && <p role="status" className="mt-4 text-sm text-muted-foreground">Отправляем параметры на сервер…</p>}
      {run && <div className="mt-4 rounded-2xl border border-border bg-card-muted p-4 text-sm">
        {(run.status === "pending" || run.status === "running") && <p role="status">{run.status === "pending" ? "Расчёт ожидает выполнения." : "Сервер выполняет расчёт."}{run.progress ? ` Этап: ${run.progress.phase}. Обработано: ${run.progress.completed} из ${run.progress.total}.` : ""}</p>}
        {run.status === "completed" && <p role="status" className="text-emerald-500">Расчёт завершён. Рекомендаций: {run.recommendation_count ?? "нет данных"}.</p>}
        {run.status === "failed" && <p role="alert" className="text-destructive">{run.error_details?.code === "supplier_terms_missing" ? "Для части товаров нет условий поставщика. Загрузите MOQ и создайте новый расчёт." : run.error_details?.code === "missing_imports" ? "Нет завершённых загрузок. Дождитесь обработки файлов и создайте новый расчёт." : "Расчёт завершился ошибкой. Проверьте источники, условия поставщиков и параметры бюджета."}</p>}
        <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{run.id}</p>
      </div>}
    </dialog>
  </>;
}
