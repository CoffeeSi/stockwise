"use client";

import { useQuery } from "@tanstack/react-query";
import { Info, X } from "lucide-react";
import { useId, useRef, useState } from "react";
import { recommendationHistoryQueryOptions } from "@/entities/analytics";
import { recommendationExplanationQueryOptions } from "@/entities/recommendation";
import { formatNumber } from "@/shared/lib";
import { Button, ErrorMessage, Skeleton } from "@/shared/ui";
import { RecommendationHistoryChart } from "./history-chart";

export function ExplainRecommendationAction({ recommendationId, productName }: { recommendationId: string; productName: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const explanation = useQuery({ ...recommendationExplanationQueryOptions(recommendationId), enabled: open });
  const history = useQuery({ ...recommendationHistoryQueryOptions(recommendationId), enabled: open });
  const data = explanation.data;
  return <>
    <Button type="button" size="sm" variant="ghost" onClick={() => { setOpen(true); dialog.current?.showModal(); }}><Info className="h-4 w-4" />Обоснование</Button>
    <dialog ref={dialog} onClose={() => setOpen(false)} aria-labelledby={titleId} className="m-auto max-h-[92vh] w-[calc(100%_-_2rem)] max-w-4xl overflow-y-auto rounded-3xl border border-border bg-card p-6 text-foreground shadow-2xl backdrop:bg-background/80">
      <header className="mb-5 flex items-start justify-between gap-4"><div><h2 id={titleId} className="text-xl font-bold">Обоснование рекомендации</h2><p className="mt-1 text-sm text-muted-foreground">{productName}</p></div><Button type="button" variant="ghost" size="icon" aria-label="Закрыть обоснование" onClick={() => dialog.current?.close()}><X className="h-4 w-4" /></Button></header>
      {explanation.isPending ? <Skeleton className="h-48" /> : explanation.isError ? <ErrorMessage title="Не удалось получить обоснование" error={explanation.error} onRetry={() => void explanation.refetch()} /> : data && <div className="space-y-5">
        <p className="whitespace-pre-wrap text-sm">{data.text}</p>
        <p className="overflow-x-auto rounded-xl border border-border bg-card-muted p-4 font-mono text-xs">{data.formula}</p>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[
          ["Базовый спрос", data.components.baseline], ["Коррекция аномалий", data.components.anomaly_adjustment], ["Компенсация stockout", data.components.stockout_compensation],
          ["Множитель роста", data.components.growth_multiplier], ["Сезонность", data.components.seasonality_index], ["Прогноз", data.forecast.forecast_quantity],
          ["Страховой запас", data.components.safety_stock], ["Текущий остаток", data.components.current_stock], ["В пути", data.components.in_transit],
          ["Материальная потребность", data.components.material_requirements], ["До округления", data.components.quantity_before_rounding], ["MOQ", data.components.moq],
          ["Кратность", data.components.package_size], [data.components.budget_allocation ? "После MOQ, до бюджета" : "После округления", data.components.quantity_after_rounding], ["Риск", data.components.risk_score],
        ].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-card-muted p-3"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-sm font-semibold">{typeof value === "number" ? formatNumber(value) : "Нет данных"}</dd></div>)}</dl>
        {data.components.budget_allocation && <section className="rounded-xl border border-border bg-card-muted p-4 text-sm"><h3 className="font-semibold">Ограничение бюджета</h3><p className="mt-2">До бюджета: {formatNumber(data.components.budget_allocation.unconstrained_quantity)}. Итог по бюджету: {formatNumber(data.components.budget_allocation.allocated_quantity)}.</p><p className="mt-1 text-xs text-muted-foreground">Метод: {data.components.budget_allocation.method}</p></section>}
        <section><h3 className="mb-3 font-semibold">Исключённые аномалии</h3>{data.anomalies.length === 0 ? <p className="text-sm text-muted-foreground">Для этой рекомендации сохранённых транзакционных аномалий нет.</p> : <ul className="space-y-2">{data.anomalies.map((anomaly) => <li key={anomaly.id} className="rounded-xl border border-border p-3 text-sm"><p>{formatNumber(anomaly.original_quantity)} → {formatNumber(anomaly.replacement_quantity)} · {anomaly.method}{anomaly.threshold !== null ? ` · порог ${formatNumber(anomaly.threshold)}` : ""}</p><p className="mt-1 text-xs text-muted-foreground">{anomaly.reason}</p></li>)}</ul>}</section>
      </div>}
      <section className="mt-6"><h3 className="mb-3 font-semibold">Продажи и остатки за 24 месяца</h3>{history.isPending ? <Skeleton className="h-40" /> : history.isError ? <ErrorMessage title="История недоступна" error={history.error} onRetry={() => void history.refetch()} /> : history.data && <RecommendationHistoryChart points={history.data.points} />}</section>
    </dialog>
  </>;
}
