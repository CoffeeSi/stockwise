"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, PackagePlus } from "lucide-react";
import { useState } from "react";
import { approveOrder, createOrders, orderKeys, type Order } from "@/entities/order";
import { Button, ErrorMessage } from "@/shared/ui";

export function ApproveAction({ runId, onOrdersCreated, onOrderApproved }: { runId: string | null; onOrdersCreated: (orders: Order[]) => void; onOrderApproved: (order: Order) => void }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: () => {
      if (!runId) throw new Error("Сначала запустите расчёт.");
      return createOrders({ calculation_run_id: runId });
    },
    onSuccess: (created) => { setOrders(created); onOrdersCreated(created); },
  });
  const approve = useMutation({
    mutationFn: approveOrder,
    onSuccess: async (updated) => {
      setOrders((current) => current.map((order) => order.id === updated.id ? updated : order));
      onOrderApproved(updated);
      await queryClient.invalidateQueries({ queryKey: orderKeys.detail(updated.id) });
    },
  });

  return <div className="space-y-3 rounded-2xl border border-border bg-card p-4"><h3 className="font-semibold">Заказы расчёта</h3><p className="text-xs text-muted-foreground">API создаёт заказы из принятых рекомендаций всего расчёта. Выбор отдельных строк пока не поддерживается.</p>
    <Button type="button" disabled={!runId || create.isPending} onClick={() => create.mutate()}><PackagePlus className="h-4 w-4" />{create.isPending ? "Формирование…" : "Сформировать заказы"}</Button>
    {create.isError && <ErrorMessage title="Не удалось сформировать заказы" error={create.error} onRetry={() => create.mutate()} />}
    {create.isSuccess && orders.length === 0 && <p role="status" className="text-sm text-muted-foreground">Заказы не созданы. Серверу нужны принятые рекомендации; маршрут принятия отсутствует в API 0.1.0.</p>}
    {orders.map((order) => <div key={order.id} className="rounded-xl border border-border bg-card-muted p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{order.order_number} · {order.status}</span>{order.status === "draft" && <Button type="button" size="sm" disabled={approve.isPending} onClick={() => approve.mutate(order.id)}><CheckCheck className="h-3.5 w-3.5" />Утвердить</Button>}</div><p className="mt-1 text-muted-foreground">{order.items.length} позиций · ID {order.id}</p></div>)}
    {approve.isError && <ErrorMessage title="Не удалось утвердить заказ" error={approve.error} onRetry={() => { if (approve.variables) approve.mutate(approve.variables); }} />}
  </div>;
}

export function ApproveOrderButton({ orderId }: { orderId: string }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => approveOrder(orderId),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: orderKeys.detail(orderId) }); },
  });
  return <div className="space-y-2"><Button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate()}><CheckCheck className="h-4 w-4" />{mutation.isPending ? "Утверждение…" : "Утвердить заказ"}</Button>{mutation.isError && <ErrorMessage title="Не удалось утвердить заказ" error={mutation.error} onRetry={() => mutation.mutate()} />}</div>;
}
