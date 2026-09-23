"use client";

import type { RunRecommendation } from "@/entities/calculation-run";
import { useSessionUser } from "@/entities/user";
import { AcceptRecommendationsAction } from "@/features/accept-recommendations";
import { AdjustRecommendationAction } from "@/features/adjust-recommendation";
import { ExplainRecommendationAction } from "@/features/explain-recommendation";
import { formatNumber } from "@/shared/lib";
import { Badge, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";

type Props = { items: RunRecommendation[]; selectedIds: string[]; onToggle: (id: string) => void; onSelectMany: (ids: string[]) => void; onClearMany: (ids: string[]) => void };
const statuses = { suggested: "Предложено", adjusted: "Скорректировано", accepted: "Принято", rejected: "Отклонено", converted_to_order: "В заказе" } as const;
const urgencies = { critical: "Критический", high: "Высокий", medium: "Средний", low: "Низкий" } as const;

export function RunRecommendationsTable({ items, selectedIds, onToggle, onSelectMany, onClearMany }: Props) {
  const user = useSessionUser();
  const canWrite = user?.role === "buyer" || user?.role === "admin";
  const selectable = items.filter((item) => ["suggested", "adjusted", "accepted"].includes(item.status) && item.effective_quantity > 0).map((item) => item.id);
  const allChecked = selectable.length > 0 && selectable.every((id) => selectedIds.includes(id));
  const suppliers = new Map<string, RunRecommendation[]>();
  for (const item of items) {
    const group = suppliers.get(item.supplier_id);
    if (group) group.push(item);
    else suppliers.set(item.supplier_id, [item]);
  }

  return <div className="overflow-x-auto"><Table className="min-w-[1350px]">
    <TableHeader><TableRow>
      <TableHead className="pl-4">{canWrite && <input type="checkbox" aria-label="Выбрать доступные строки страницы" checked={allChecked} disabled={selectable.length === 0} onChange={(event) => event.target.checked ? onSelectMany(selectable) : onClearMany(selectable)} className="accent-primary" />}</TableHead>
      <TableHead>Номенклатура</TableHead><TableHead>Склад</TableHead><TableHead>Остаток</TableHead><TableHead>В пути</TableHead><TableHead>Дефицит</TableHead><TableHead>Рекомендовано</TableHead><TableHead>К заказу</TableHead><TableHead>Стоимость</TableHead><TableHead>Риск / статус</TableHead><TableHead className="pr-4">Действия</TableHead>
    </TableRow></TableHeader>
    {Array.from(suppliers).map(([supplierId, rows]) => <TableBody key={supplierId}>
      <tr className="bg-card-muted"><TableCell colSpan={11} className="px-4 py-3 text-sm font-semibold">{rows[0].supplier_name} <span className="ml-2 text-xs font-normal text-muted-foreground">{rows.length} позиций на странице</span></TableCell></tr>
      {rows.map((item) => <TableRow key={item.id} className={selectedIds.includes(item.id) ? "bg-primary/5" : ""}>
        <TableCell className="pl-4">{canWrite && <input type="checkbox" aria-label={`Выбрать ${item.sku}`} checked={selectedIds.includes(item.id) && selectable.includes(item.id)} disabled={!selectable.includes(item.id)} onChange={() => onToggle(item.id)} className="accent-primary" />}</TableCell>
        <TableCell className="max-w-64"><p className="text-xs font-semibold">{item.sku}</p><p className="mt-1 text-sm">{item.product_name}</p><p className="mt-1 text-xs text-muted-foreground">{item.category_name ?? "Категория не указана"} · {item.unit}</p></TableCell>
        <TableCell className="text-xs">{item.warehouse_name}</TableCell>
        <TableCell className="text-sm tabular-nums">{formatNumber(item.current_stock)}</TableCell>
        <TableCell className="text-sm tabular-nums">{formatNumber(item.in_transit_quantity)}</TableCell>
        <TableCell className="text-sm tabular-nums">{formatNumber(item.shortage_quantity)}</TableCell>
        <TableCell className="text-sm tabular-nums">{formatNumber(item.recommended_quantity)}</TableCell>
        <TableCell className="text-sm font-semibold tabular-nums">{formatNumber(item.effective_quantity)}<p className="mt-1 text-[10px] font-normal text-muted-foreground">MOQ {formatNumber(item.moq)} · кратность {formatNumber(item.package_size)}</p></TableCell>
        <TableCell className="text-xs tabular-nums">{item.estimated_total === null ? "Нет цены" : `${formatNumber(item.estimated_total)} ${item.currency ?? "(валюта неизвестна)"}`}<p className="mt-1 text-muted-foreground">{item.unit_price === null ? "" : `${formatNumber(item.unit_price)} за ${item.unit}`}</p></TableCell>
        <TableCell><div className="space-y-1"><Badge tone={item.urgency === "critical" ? "red" : item.urgency === "high" ? "amber" : item.urgency === "medium" ? "blue" : "green"}>{urgencies[item.urgency]} · {formatNumber(item.risk_score)}</Badge><p className="text-xs text-muted-foreground">{statuses[item.status]}</p></div></TableCell>
        <TableCell className="pr-4"><div className="flex max-w-80 flex-wrap gap-2"><ExplainRecommendationAction recommendationId={item.id} productName={`${item.sku} · ${item.product_name}`} />{canWrite && <><AcceptRecommendationsAction runId={item.calculation_run_id} items={[item]} compact /><AdjustRecommendationAction recommendation={item} /></>}</div></TableCell>
      </TableRow>)}
    </TableBody>)}
  </Table>{items.length === 0 && <p className="p-6 text-sm text-muted-foreground">Рекомендаций по выбранным фильтрам нет.</p>}</div>;
}
