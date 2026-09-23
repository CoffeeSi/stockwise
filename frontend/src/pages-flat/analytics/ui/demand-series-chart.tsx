import type { DemandSeries } from "@/entities/analytics";
import { formatNumber } from "@/shared/lib";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui";
import { formatAnalyticsMonth } from "../lib/presentation";

export function DemandSeriesChart({ data }: { data: DemandSeries }) {
  const { points } = data;
  if (points.length === 0) return <p className="py-10 text-center text-sm text-muted-foreground">Для выбранных фильтров нет сохранённого ряда спроса.</p>;
  const width = 760;
  const height = 250;
  const left = 66;
  const top = 18;
  const bottom = 36;
  const right = 18;
  const minimum = Math.min(0, ...points.map((point) => point.raw_sales));
  const maximum = Math.max(0, ...points.flatMap((point) => [point.raw_sales, point.cleaned_demand]));
  const range = maximum - minimum || 1;
  const x = (index: number) => points.length === 1 ? (width + left - right) / 2 : left + index * (width - left - right) / (points.length - 1);
  const y = (value: number) => top + (maximum - value) * (height - top - bottom) / range;
  const rawLine = points.map((point, index) => `${x(index)},${y(point.raw_sales)}`).join(" ");
  const cleanLine = points.map((point, index) => `${x(index)},${y(point.cleaned_demand)}`).join(" ");

  return <>
    <div className="mb-4 flex flex-wrap gap-4 text-xs text-muted-foreground"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-muted-foreground" />Исходные продажи</span><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-primary" />Очищенный спрос</span></div>
    <div className="overflow-x-auto"><svg viewBox={`0 0 ${width} ${height}`} className="min-w-[580px] w-full" role="img" aria-label="Исходные продажи и очищенный спрос по месяцам">
      <title>Сохранённый спрос по месяцам</title>
      {[0, 1, 2, 3, 4].map((step) => {
        const value = minimum + range * step / 4;
        return <g key={step}><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} className="stroke-border" strokeDasharray="3 5" /><text x={left - 8} y={y(value) + 4} textAnchor="end" className="fill-muted-foreground text-[10px]">{formatNumber(Math.round(value * 10) / 10)}</text></g>;
      })}
      <polyline points={rawLine} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 4" className="text-muted-foreground" />
      <polyline points={cleanLine} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" className="text-primary" />
      {points.map((point, index) => <g key={point.month}>
        <circle cx={x(index)} cy={y(point.cleaned_demand)} r="3.5" fill="currentColor" className="text-primary"><title>{formatAnalyticsMonth(point.month)}: спрос {formatNumber(point.cleaned_demand)}, продажи {formatNumber(point.raw_sales)}</title></circle>
        <text x={x(index)} y={height - 12} textAnchor="middle" className="fill-muted-foreground text-[9px]">{formatAnalyticsMonth(point.month)}</text>
      </g>)}
    </svg></div>
    <p className="mt-2 text-xs text-muted-foreground">Сохранено месяцев: {data.available_months}. На графике: {points.length}. Версия расчёта: {data.algorithm_version}.</p>
    <details className="mt-5"><summary className="cursor-pointer text-sm font-medium text-foreground">Показать значения и остатки</summary><div className="mt-3 overflow-x-auto"><Table className="min-w-[480px]"><TableHeader><TableRow><TableHead>Месяц</TableHead><TableHead>Продажи</TableHead><TableHead>Спрос</TableHead><TableHead>Остаток</TableHead></TableRow></TableHeader><TableBody>{points.map((point) => <TableRow key={point.month}><TableCell className="text-sm">{formatAnalyticsMonth(point.month)}</TableCell><TableCell className="text-sm tabular-nums">{formatNumber(point.raw_sales)}</TableCell><TableCell className="text-sm tabular-nums">{formatNumber(point.cleaned_demand)}</TableCell><TableCell className="text-sm tabular-nums">{point.stock === null ? "Нет наблюдения" : formatNumber(point.stock)}</TableCell></TableRow>)}</TableBody></Table></div></details>
  </>;
}
