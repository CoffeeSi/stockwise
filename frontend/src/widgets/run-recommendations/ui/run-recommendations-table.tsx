"use client";

import type { RunRecommendation } from "@/entities/calculation-run";
import { AdjustRecommendationAction } from "@/features/adjust-recommendation";
import { calculationRunKeys, type RunRecommendationsPage } from "@/entities/calculation-run";
import { acceptRecommendation } from "@/entities/recommendation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/ui";
import { formatNumber } from "@/shared/lib";
import { Badge, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";

export function RunRecommendationsTable({ items }: { items: RunRecommendation[] }) {
  const client = useQueryClient();
  const accept = useMutation({ mutationFn: ({ id, version }: { id: string; version: number }) => acceptRecommendation(id, version), onSuccess: async (updated) => { client.setQueriesData<RunRecommendationsPage>({ queryKey: [...calculationRunKeys.detail(updated.calculation_run_id), "recommendations"] }, (page) => page ? { ...page, items: page.items.map((row) => row.id === updated.id ? { ...row, ...updated } : row) } : page); await client.invalidateQueries({ queryKey: [...calculationRunKeys.detail(updated.calculation_run_id), "recommendations"] }); } });
  return <div className="overflow-x-auto"><Table className="min-w-[1000px]"><TableHeader><tr><TableHead>Товар ID</TableHead><TableHead>Поставщик ID</TableHead><TableHead>Остаток</TableHead><TableHead>Дефицит</TableHead><TableHead>Рекомендовано</TableHead><TableHead>К заказу</TableHead><TableHead>Статус</TableHead><TableHead>Действия</TableHead></tr></TableHeader><TableBody>{items.map((item) => <TableRow key={item.id}>
    <TableCell className="max-w-40 truncate font-mono text-xs" title={item.product_id}>{item.product_id}</TableCell>
    <TableCell className="max-w-40 truncate font-mono text-xs" title={item.supplier_id}>{item.supplier_id}</TableCell>
    <TableCell>{formatNumber(item.current_stock)}</TableCell>
    <TableCell>{formatNumber(item.shortage_quantity)}</TableCell>
    <TableCell>{formatNumber(item.recommended_quantity)}</TableCell>
    <TableCell className="font-semibold">{formatNumber(item.effective_quantity)}</TableCell>
    <TableCell><Badge tone={item.urgency === "critical" ? "red" : item.urgency === "high" ? "amber" : "blue"}>{item.status} · {item.urgency}</Badge></TableCell>
    <TableCell><div className="flex flex-wrap gap-1">{item.status !== "accepted" && item.status !== "converted_to_order" && <Button size="sm" type="button" disabled={accept.isPending} onClick={() => accept.mutate({ id: item.id, version: item.version })}>Принять</Button>}<AdjustRecommendationAction recommendation={item} /></div>{accept.isError && <p className="mt-1 text-xs text-destructive">{accept.error.message}</p>}</TableCell>
  </TableRow>)}</TableBody></Table>{items.length === 0 && <p className="p-6 text-sm text-muted-foreground">Расчёт завершён без рекомендаций.</p>}</div>;
}
