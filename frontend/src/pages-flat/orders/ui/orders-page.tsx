"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Package, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { calculationRunQueryOptions, calculationRunsQueryOptions } from "@/entities/calculation-run";
import { supplierOptionsQueryOptions } from "@/entities/catalog";
import { orderQueryOptions, ordersQueryOptions, type OrderFilters } from "@/entities/order";
import { ApproveOrderButton } from "@/features/approve-order";
import { ExportMenu } from "@/features/export-order";
import { Badge, Button, Card, ErrorMessage, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";
import { formatOrderAmount, formatOrderDate, orderStatusPresentation } from "../lib/presentation";
import { orderListFormSchema, type OrderListForm } from "../model/schema";

const PAGE_SIZE = 20;
const runStatusLabels = { pending: "Ожидает", running: "Выполняется", completed: "Завершён", failed: "Ошибка" } as const;

export function OrdersPage({ initialRunId = null }: { initialRunId?: string | null }) {
  const [filters, setFilters] = useState<OrderFilters>({ ...(initialRunId ? { calculation_run_id: initialRunId } : {}), limit: PAGE_SIZE, offset: 0 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const form = useForm<OrderListForm>({
    resolver: zodResolver(orderListFormSchema),
    defaultValues: { runId: initialRunId ?? "", supplierId: "", status: "" },
  });
  const history = useQuery(calculationRunsQueryOptions({ limit: PAGE_SIZE, offset: historyOffset }));
  const suppliers = useQuery(supplierOptionsQueryOptions({ active_only: false }));
  const selectedRunId = useWatch({ control: form.control, name: "runId" });
  const runMissingFromPage = !!selectedRunId && !history.data?.items.some((run) => run.id === selectedRunId);
  const selectedRun = useQuery({ ...calculationRunQueryOptions(selectedRunId || ""), enabled: runMissingFromPage });
  const list = useQuery(ordersQueryOptions(filters));
  const detail = useQuery({ ...orderQueryOptions(selectedId ?? ""), enabled: selectedId !== null });
  const page = list.data;
  const order = detail.data;
  const summary = page?.items.find((item) => item.id === selectedId);
  const errors = form.formState.errors;
  const applyFilters = (values: OrderListForm) => {
    setSelectedId(null);
    setFilters({
      ...(values.runId ? { calculation_run_id: values.runId } : {}),
      ...(values.supplierId ? { supplier_id: values.supplierId } : {}),
      ...(values.status ? { status: values.status } : {}),
      limit: PAGE_SIZE,
      offset: 0,
    });
  };

  return (
    <AppShell>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div><h1 className="text-3xl font-bold">Заказы поставщикам</h1><p className="mt-2 text-sm text-muted-foreground">Сохранённые черновики, утверждённые заказы и готовые выгрузки.</p></div>
        <Button type="button" variant="secondary" disabled={list.isFetching} onClick={() => void list.refetch()}><RefreshCw className={`h-4 w-4 ${list.isFetching ? "animate-spin" : ""}`} />Обновить</Button>
      </header>
      <Card className="mb-5 p-5">
        <form className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" onSubmit={form.handleSubmit(applyFilters)}>
          <div>
            <label className="text-sm">Расчёт
              <select className="mt-2 h-10 w-full rounded-xl border border-border bg-input px-3 text-foreground disabled:opacity-50" aria-invalid={!!errors.runId} disabled={history.isPending || history.isError} {...form.register("runId")}>
                <option value="">{history.isPending ? "Загрузка истории…" : "Все расчёты"}</option>
                {runMissingFromPage && <option value={selectedRunId}>{selectedRun.data ? `${formatOrderDate(selectedRun.data.started_at)} · ${runStatusLabels[selectedRun.data.status]}` : "Выбранный расчёт"} · {selectedRunId.slice(0, 8)}</option>}
                {history.data?.items.map((run) => <option key={run.id} value={run.id}>{formatOrderDate(run.started_at)} · {runStatusLabels[run.status]} · {run.id.slice(0, 8)}</option>)}
              </select>
              {errors.runId && <span role="alert" className="mt-1 block text-xs text-red-500">Выберите расчёт из истории или все расчёты.</span>}
            </label>
            {history.data && <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-muted-foreground"><span>Расчётов: {history.data.total}</span><Button type="button" size="sm" variant="ghost" disabled={historyOffset === 0 || history.isFetching} onClick={() => setHistoryOffset((value) => Math.max(0, value - PAGE_SIZE))}>Новые</Button><Button type="button" size="sm" variant="ghost" disabled={historyOffset + PAGE_SIZE >= history.data.total || history.isFetching} onClick={() => setHistoryOffset((value) => value + PAGE_SIZE)}>Старые</Button></div>}
          </div>
          <label className="text-sm">Поставщик
            <select className="mt-2 h-10 w-full rounded-xl border border-border bg-input px-3 text-foreground disabled:opacity-50" aria-invalid={!!errors.supplierId} disabled={suppliers.isPending || suppliers.isError} {...form.register("supplierId")}>
              <option value="">{suppliers.isPending ? "Загрузка поставщиков…" : "Все поставщики"}</option>
              {suppliers.data?.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}{supplier.is_active ? "" : " (неактивен)"}</option>)}
            </select>
            {errors.supplierId && <span role="alert" className="mt-1 block text-xs text-red-500">Выберите поставщика из справочника или всех поставщиков.</span>}
          </label>
          <label className="text-sm">Статус
            <select className="mt-2 h-10 w-full rounded-xl border border-border bg-input px-3 text-foreground" {...form.register("status")}>
              <option value="">Все статусы</option>
              {Object.entries(orderStatusPresentation).map(([status, item]) => <option key={status} value={status}>{item.label}</option>)}
            </select>
            {errors.status && <span role="alert" className="mt-1 block text-xs text-red-500">Выберите статус из списка.</span>}
          </label>
          <div className="flex items-end gap-2">
            <Button type="submit">Применить</Button>
            <Button type="button" variant="secondary" onClick={() => { form.reset({ runId: "", supplierId: "", status: "" }); applyFilters({ runId: "", supplierId: "", status: "" }); }}>Сбросить</Button>
          </div>
        </form>
        {history.isError && <div className="mt-3"><ErrorMessage title="Не удалось загрузить историю расчётов" error={history.error} onRetry={() => void history.refetch()} /></div>}
        {suppliers.isError && <div className="mt-3"><ErrorMessage title="Не удалось загрузить поставщиков" error={suppliers.error} onRetry={() => void suppliers.refetch()} /></div>}
        {runMissingFromPage && selectedRun.isError && <div className="mt-3"><ErrorMessage title="Выбранный расчёт недоступен" error={selectedRun.error} onRetry={() => void selectedRun.refetch()} /></div>}
      </Card>
      {list.isPending ? <Skeleton className="h-72 rounded-2xl" /> : list.isError ? (
        <ErrorMessage title="Не удалось загрузить заказы" error={list.error} onRetry={() => void list.refetch()} />
      ) : page && (
        <Card className="overflow-hidden">
          {page.items.length === 0 ? (
            <div className="flex flex-col items-center gap-3 p-10 text-center"><Package className="h-8 w-8 text-muted-foreground" /><p className="font-semibold">Заказы не найдены</p><p className="max-w-md text-sm text-muted-foreground">Измените фильтры или сформируйте черновики из принятых рекомендаций на странице расчёта.</p></div>
          ) : (
            <div className="overflow-x-auto"><Table className="min-w-[850px]">
              <TableHeader><TableRow><TableHead className="pl-5">Заказ</TableHead><TableHead>Поставщик / склад</TableHead><TableHead>Статус</TableHead><TableHead>Позиций</TableHead><TableHead>Сумма</TableHead><TableHead className="pr-5 text-right">Просмотр</TableHead></TableRow></TableHeader>
              <TableBody>{page.items.map((item) => {
                const status = orderStatusPresentation[item.status];
                return <TableRow key={item.id} className={selectedId === item.id ? "bg-primary/5" : ""}>
                  <TableCell className="pl-5"><p className="text-sm font-semibold">{item.order_number}</p><p className="mt-1 text-xs text-muted-foreground">{formatOrderDate(item.created_at)}</p></TableCell>
                  <TableCell><p className="text-sm">{item.supplier_name}</p><p className="mt-1 text-xs text-muted-foreground">{item.warehouse_name}</p></TableCell>
                  <TableCell><Badge tone={status.tone}>{status.label}</Badge></TableCell>
                  <TableCell className="text-sm tabular-nums">{item.item_count}</TableCell>
                  <TableCell className="text-sm tabular-nums">{formatOrderAmount(item.total_amount, item.currency)}</TableCell>
                  <TableCell className="pr-5 text-right"><Button type="button" variant="secondary" size="sm" onClick={() => setSelectedId(item.id)} aria-pressed={selectedId === item.id}>Открыть</Button></TableCell>
                </TableRow>;
              })}</TableBody>
            </Table></div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4">
            <p className="text-xs text-muted-foreground">{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length} из ${page.total}` : `Найдено: ${page.total}`}</p>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="secondary" disabled={page.offset === 0 || list.isFetching} onClick={() => { setSelectedId(null); setFilters((current) => ({ ...current, offset: Math.max(0, page.offset - page.limit) })); }}><ChevronLeft className="h-4 w-4" />Назад</Button>
              <Button type="button" size="sm" variant="secondary" disabled={page.offset + page.limit >= page.total || list.isFetching} onClick={() => { setSelectedId(null); setFilters((current) => ({ ...current, offset: page.offset + page.limit })); }}>Далее<ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </Card>
      )}
      {selectedId && <section className="mt-5" aria-label="Детали заказа">
        {detail.isPending ? <Skeleton className="h-56 rounded-2xl" /> : detail.isError ? <ErrorMessage title="Не удалось загрузить заказ" error={detail.error} onRetry={() => void detail.refetch()} /> : order && <Card className="space-y-5 p-5">
          <div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold">{order.order_number}</h2><div className="mt-2"><Badge tone={orderStatusPresentation[order.status].tone}>{orderStatusPresentation[order.status].label}</Badge></div><p className="mt-2 text-xs text-muted-foreground">Поставщик: {summary?.supplier_name ?? order.supplier_id} · Склад: {summary?.warehouse_name ?? order.warehouse_id}</p><p className="mt-1 text-xs text-muted-foreground">Создан: {formatOrderDate(order.created_at)}{order.approved_at ? ` · Утверждён: ${formatOrderDate(order.approved_at)}` : ""}</p></div><Button type="button" variant="ghost" size="sm" aria-label="Закрыть детали заказа" onClick={() => setSelectedId(null)}><X className="h-4 w-4" /></Button></div>
          <div className="overflow-x-auto"><Table className="min-w-[620px]"><TableHeader><TableRow><TableHead className="pl-3">ID товара</TableHead><TableHead>Рекомендовано</TableHead><TableHead>Заказано</TableHead><TableHead>Сумма</TableHead></TableRow></TableHeader><TableBody>{order.items.map((item) => <TableRow key={item.id}><TableCell className="pl-3 font-mono text-xs">{item.product_id}</TableCell><TableCell className="text-sm tabular-nums">{item.recommended_quantity}</TableCell><TableCell className="text-sm tabular-nums">{item.approved_quantity}</TableCell><TableCell className="text-sm tabular-nums">{formatOrderAmount(item.total_amount, summary?.currency ?? null)}</TableCell></TableRow>)}</TableBody></Table></div>
          {order.items.length === 0 && <p className="text-sm text-muted-foreground">В заказе нет позиций.</p>}
          {order.status === "draft" && <div className="space-y-3"><p className="text-sm text-muted-foreground">Проверьте позиции и количества перед утверждением. После утверждения станет доступен экспорт XLSX.</p><ApproveOrderButton key={order.id} orderId={order.id} /></div>}
          {(order.status === "approved" || order.status === "exported") && <ExportMenu key={order.id} order={order} />}
          {order.status === "cancelled" && <p className="text-sm text-muted-foreground">Заказ отменён. Утверждение и экспорт недоступны.</p>}
        </Card>}
      </section>}
    </AppShell>
  );
}
