"use client";

import { CheckCheck, PackagePlus } from "lucide-react";
import Link from "next/link";
import { useSessionUser } from "@/entities/user";
import { Button, ErrorMessage } from "@/shared/ui";
import { useApproveOrder, useCreateOrders, useCreateSelectedOrders } from "../api/mutations";

export interface ApproveActionProps {
  runId: string | null;
  selectedRecommendationIds?: string[];
  onSelectionConsumed?: (ids: string[]) => void;
}

export function ApproveAction({ runId, selectedRecommendationIds = [], onSelectionConsumed }: ApproveActionProps) {
  const user = useSessionUser();
  const canWrite = user?.role === "buyer" || user?.role === "admin";
  const create = useCreateOrders();
  const selected = useCreateSelectedOrders();
  const pending = create.isPending || selected.isPending;

  if (!canWrite) return null;

  const createAll = () => {
    if (!runId) return;
    selected.reset();
    create.mutate({ calculation_run_id: runId }, {
      onSuccess: (orders) => onSelectionConsumed?.(orders.flatMap((order) => order.items.map((item) => item.recommendation_id))),
    });
  };
  const createSelection = () => {
    if (!runId || selectedRecommendationIds.length === 0) return;
    create.reset();
    selected.mutate({ calculation_run_id: runId, recommendation_ids: selectedRecommendationIds }, {
      onSuccess: (result) => onSelectionConsumed?.(result.consumed_recommendation_ids),
    });
  };

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-card p-4">
      <h3 className="font-semibold">Сформировать черновики заказов</h3>
      <p className="text-xs text-muted-foreground">Сначала примите рекомендации. Сервер объединит выбранные позиции по поставщику и складу. Утверждение выполняется отдельно на странице заказов.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!runId || selectedRecommendationIds.length === 0 || pending} onClick={createSelection}>
          <PackagePlus className="h-4 w-4" />
          {selected.isPending ? "Формирование…" : `Из выбранных принятых (${selectedRecommendationIds.length})`}
        </Button>
        <Button type="button" variant="secondary" disabled={!runId || pending} onClick={createAll}>
          {create.isPending ? "Формирование…" : "Из всех принятых строк расчёта"}
        </Button>
      </div>
      {selected.isError && <ErrorMessage title="Не удалось сформировать выбранные заказы" error={selected.error} onRetry={createSelection} />}
      {create.isError && <ErrorMessage title="Не удалось сформировать заказы" error={create.error} onRetry={createAll} />}
      {selected.isSuccess && <p role="status" className="text-sm text-muted-foreground">Создано заказов: {selected.data.orders.length}. Использовано рекомендаций: {selected.data.consumed_recommendation_ids.length}.</p>}
      {create.isSuccess && <p role="status" className="text-sm text-muted-foreground">{create.data.length > 0 ? `Создано заказов: ${create.data.length}.` : "Нет принятых рекомендаций, которые ещё не включены в заказ."}</p>}
      <Link href={runId ? `/orders?run=${encodeURIComponent(runId)}` : "/orders"} className="inline-block text-sm font-medium text-primary underline underline-offset-4">Открыть сохранённые заказы</Link>
    </div>
  );
}

export function ApproveOrderButton({ orderId }: { orderId: string }) {
  const user = useSessionUser();
  const mutation = useApproveOrder();
  if (user?.role !== "buyer" && user?.role !== "admin") return null;
  return (
    <div className="space-y-2">
      <Button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(orderId)}>
        <CheckCheck className="h-4 w-4" />{mutation.isPending ? "Утверждение…" : "Утвердить заказ"}
      </Button>
      {mutation.isError && <ErrorMessage title="Не удалось утвердить заказ" error={mutation.error} onRetry={() => mutation.mutate(orderId)} />}
    </div>
  );
}
