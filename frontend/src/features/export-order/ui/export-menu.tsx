"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { createOrderExport, downloadOrderExport, orderKeys, type Order } from "@/entities/order";
import { Button, ErrorMessage } from "@/shared/ui";

export function ExportMenu({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: async () => {
      const metadata = await createOrderExport(order.id);
      const blob = await downloadOrderExport(order.id);
      if (blob.blob.size === 0) throw new Error("Сервер вернул пустой файл экспорта.");
      const filename = blob.filename ?? metadata.file_name;
      const url = URL.createObjectURL(blob.blob);
      try {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
      }
      return { ...metadata, file_name: filename };
    },
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: orderKeys.detail(order.id) }); },
  });

  return <div className="space-y-2"><Button type="button" variant="secondary" disabled={mutation.isPending || (order.status !== "approved" && order.status !== "exported")} onClick={() => mutation.mutate()}><Download className="h-4 w-4" />{mutation.isPending ? "Готовим файл…" : "Скачать XLSX для 1С"}</Button>
    {mutation.isError && <ErrorMessage title="Не удалось скачать экспорт" error={mutation.error} onRetry={() => mutation.mutate()} />}
    {mutation.isSuccess && <p role="status" className="text-xs text-emerald-500">Файл {mutation.data.file_name} получен от сервера.</p>}
  </div>;
}
