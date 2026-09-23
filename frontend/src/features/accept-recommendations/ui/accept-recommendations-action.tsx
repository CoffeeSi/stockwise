"use client";

import { Check } from "lucide-react";
import type { Recommendation } from "@/entities/recommendation";
import { useSessionUser } from "@/entities/user";
import { ApiError } from "@/shared/api";
import { Button } from "@/shared/ui";
import { useAcceptRecommendations } from "../api/use-accept-recommendations";

type AcceptableRecommendation = Pick<Recommendation, "id" | "version" | "status" | "effective_quantity">;

export function AcceptRecommendationsAction({ runId, items, compact = false }: { runId: string; items: AcceptableRecommendation[]; compact?: boolean }) {
  const user = useSessionUser();
  const mutation = useAcceptRecommendations();
  const eligible = items.filter((item) => (item.status === "suggested" || item.status === "adjusted") && item.effective_quantity > 0);
  if (user?.role !== "buyer" && user?.role !== "admin") return null;
  if (compact && eligible.length === 0) return null;

  return <div className="space-y-2">
    <Button type="button" size={compact ? "sm" : "md"} variant="secondary" disabled={eligible.length === 0 || mutation.isPending}
      onClick={() => mutation.mutate({ calculation_run_id: runId, items: eligible.map((item) => ({ recommendation_id: item.id, version: item.version })) })}>
      <Check className="h-4 w-4" />{mutation.isPending ? "Принятие…" : compact ? "Принять" : `Принять выбранные (${eligible.length})`}
    </Button>
    {mutation.isError && <p role="alert" className="max-w-md text-xs text-destructive">{mutation.error instanceof ApiError && mutation.error.status === 409 ? "Часть рекомендаций изменилась. Список обновлён; проверьте строки перед повторным принятием." : mutation.error.message}</p>}
    {mutation.isSuccess && !compact && <p role="status" className="text-xs text-muted-foreground">Принято рекомендаций: {mutation.data.accepted_count}. Теперь можно сформировать черновики.</p>}
  </div>;
}
