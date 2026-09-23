import type { AbcXyz } from "@/entities/analytics";
import { formatNumber } from "@/shared/lib";
import { formatShare } from "../lib/presentation";

export function AbcXyzMatrix({ data }: { data: AbcXyz }) {
  const totalSkus = data.cells.reduce((total, cell) => total + cell.sku_count, 0);
  if (!totalSkus) return <p className="py-10 text-center text-sm text-muted-foreground">Для выбранных фильтров нет позиций для классификации.</p>;
  const { metadata } = data;
  return <>
    <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs text-muted-foreground"><span>X · стабильный</span><span>Y · переменный</span><span>Z · неравномерный</span></div>
    <div className="grid grid-cols-3 gap-2">{data.cells.map((cell) => <div key={`${cell.abc}${cell.xyz}`} className={`rounded-2xl border p-4 ${cell.sku_count ? "border-primary/25 bg-primary/5" : "border-border bg-card-muted"}`}>
      <p className="text-xs font-semibold text-muted-foreground">{cell.abc}{cell.xyz}</p><p className="mt-2 text-2xl font-semibold tabular-nums">{formatNumber(cell.sku_count)}</p><p className="mt-1 text-xs text-muted-foreground">SKU · {formatShare(cell.demand_share)} спроса</p>
    </div>)}</div>
    <p className="mt-4 text-xs leading-relaxed text-muted-foreground">ABC по количеству очищенного спроса: A до {formatShare(metadata.abc_a_share)}, B до {formatShare(metadata.abc_b_share)} накопленной доли. XYZ по вариации: X ≤ {metadata.xyz_x_cv}, Y ≤ {metadata.xyz_y_cv}.</p>
    <p className="mt-2 text-xs text-muted-foreground">Метод: {metadata.version}. Пороговые значения сохранены вместе с расчётом.</p>
  </>;
}
