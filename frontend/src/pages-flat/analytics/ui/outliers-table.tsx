import { ChevronLeft, ChevronRight } from "lucide-react";
import type { OutlierPage } from "@/entities/analytics";
import { formatNumber } from "@/shared/lib";
import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";
import { formatAnalyticsDate } from "../lib/presentation";

export function OutliersTable({ data, isFetching, onPage, warehouses }: {
  data: OutlierPage;
  isFetching: boolean;
  onPage: (offset: number) => void;
  warehouses: ReadonlyMap<string, string>;
}) {
  return <>
    {data.items.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">Транзакционных аномалий для выбранных фильтров нет.</p> : <div className="overflow-x-auto"><Table className="min-w-[900px]"><TableHeader><TableRow><TableHead className="pl-5">SKU / склад</TableHead><TableHead>Дата продажи</TableHead><TableHead>Исходное</TableHead><TableHead>После очистки</TableHead><TableHead>Порог</TableHead><TableHead className="pr-5">Причина</TableHead></TableRow></TableHeader><TableBody>{data.items.map((item) => <TableRow key={item.id}>
      <TableCell className="pl-5"><p className="font-mono text-xs font-semibold">{item.sku}</p><p className="mt-1 max-w-48 truncate text-xs text-muted-foreground" title={warehouses.get(item.warehouse_id) ?? item.warehouse_id}>{warehouses.get(item.warehouse_id) ?? item.warehouse_id}</p></TableCell>
      <TableCell className="whitespace-nowrap text-xs">{formatAnalyticsDate(item.occurred_at)}</TableCell>
      <TableCell className="text-sm tabular-nums">{formatNumber(item.original_quantity)}</TableCell>
      <TableCell className="text-sm tabular-nums">{formatNumber(item.replacement_quantity)}</TableCell>
      <TableCell className="text-sm tabular-nums">{item.threshold === null ? "Не задан" : formatNumber(item.threshold)}</TableCell>
      <TableCell className="max-w-sm pr-5 text-xs"><p>{item.reason}</p><p className="mt-1 text-muted-foreground">{item.method}</p></TableCell>
    </TableRow>)}</TableBody></Table></div>}
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4"><p className="text-xs text-muted-foreground">{data.items.length ? `${data.offset + 1}–${data.offset + data.items.length} из ${data.total}` : `Найдено: ${data.total}`}</p><div className="flex gap-2">
      <Button type="button" size="sm" variant="secondary" disabled={data.offset === 0 || isFetching} onClick={() => onPage(Math.max(0, data.offset - data.limit))}><ChevronLeft className="h-4 w-4" />Назад</Button>
      <Button type="button" size="sm" variant="secondary" disabled={data.offset + data.limit >= data.total || isFetching} onClick={() => onPage(data.offset + data.limit)}>Далее<ChevronRight className="h-4 w-4" /></Button>
    </div></div>
  </>;
}
