import type { RecommendationHistory } from "@/entities/analytics";
import { formatNumber } from "@/shared/lib";

export function RecommendationHistoryChart({ points }: { points: RecommendationHistory["points"] }) {
  if (points.length === 0) return <p className="text-sm text-muted-foreground">В снимке расчёта нет помесячной истории.</p>;
  const values = points.flatMap((point) => point.stock === null ? [point.sales] : [point.sales, point.stock]);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(1, ...values);
  const y = (value: number) => 180 - (value - minimum) / (maximum - minimum) * 160;
  const baseline = y(0);
  const step = 680 / points.length;
  return <div className="space-y-3">
    <p className="text-xs text-muted-foreground"><span className="font-medium text-primary">Столбцы — продажи.</span> <span className="font-medium text-emerald-500">Точки — остаток.</span> Отсутствующее наблюдение остатка не заменяется нулём.</p>
    <svg viewBox="0 0 720 220" className="w-full" role="img" aria-label="Помесячные продажи и наблюдения остатков из сохранённого расчёта">
      <line x1="20" x2="700" y1={baseline} y2={baseline} className="stroke-border" />
      {points.map((point, index) => {
        const x = 20 + index * step;
        return <g key={point.month}>
          <rect x={x + 2} width={Math.max(1, step - 4)} y={Math.min(y(point.sales), baseline)} height={Math.abs(baseline - y(point.sales))} className="fill-primary/70"><title>{point.month}: продажи {formatNumber(point.sales)}</title></rect>
          {point.stock !== null && <circle cx={x + step / 2} cy={y(point.stock)} r="3" className="fill-emerald-500"><title>{point.month}: остаток {formatNumber(point.stock)}</title></circle>}
          {(index === 0 || index === points.length - 1 || index % 4 === 0) && <text x={x + step / 2} y="208" textAnchor="middle" className="fill-muted-foreground text-[9px]">{point.month}</text>}
        </g>;
      })}
    </svg>
    <details className="rounded-xl border border-border p-3 text-xs"><summary className="cursor-pointer font-medium">Точные значения по месяцам</summary><div className="mt-3 max-h-56 space-y-2 overflow-y-auto">{points.map((point) => <div key={point.month} className="grid grid-cols-3 gap-3"><span>{point.month}</span><span>Продажи: {formatNumber(point.sales)}</span><span>Остаток: {point.stock === null ? "нет наблюдения" : formatNumber(point.stock)}</span></div>)}</div></details>
  </div>;
}
