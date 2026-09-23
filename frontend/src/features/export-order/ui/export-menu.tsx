"use client";

import { Download } from "lucide-react";
import type { Order } from "@/entities/order";
import { useSessionUser } from "@/entities/user";
import { Button, ErrorMessage } from "@/shared/ui";
import { useExportOrder } from "../api/use-export-order";

export function ExportMenu({ order }: { order: Order }) {
  const user = useSessionUser();
  const canCreate = user?.role === "buyer" || user?.role === "admin";
  const mutation = useExportOrder(order);
  if (order.status === "approved" && !canCreate) {
    return <p className="text-sm text-muted-foreground">Сотрудник с ролью закупщика или администратора должен сформировать XLSX. После этого файл будет доступен для скачивания.</p>;
  }
  return (
    <div className="space-y-2">
      <Button type="button" variant="secondary" disabled={mutation.isPending || (order.status !== "approved" && order.status !== "exported")} onClick={() => mutation.mutate()}>
        <Download className="h-4 w-4" />{mutation.isPending ? "Готовим файл…" : order.status === "exported" ? "Скачать готовый XLSX" : "Создать и скачать XLSX"}
      </Button>
      {mutation.isError && <ErrorMessage title="Не удалось скачать экспорт" error={mutation.error} onRetry={() => mutation.mutate()} />}
      {mutation.isSuccess && <p role="status" className="text-xs text-emerald-500">Файл {mutation.data.filename} получен от сервера.</p>}
    </div>
  );
}
