"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { calculationRunKeys } from "@/entities/calculation-run";
import { createOrderExport, downloadOrderExport, orderKeys, type Order } from "@/entities/order";

export function useExportOrder(order: Order) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const metadata = order.status === "approved" ? await createOrderExport(order.id) : null;
      const file = await downloadOrderExport(order.id);
      if (file.blob.size === 0) throw new Error("Сервер вернул пустой файл экспорта.");
      const filename = file.filename ?? metadata?.file_name ?? `${order.order_number}.xlsx`;
      const url = URL.createObjectURL(file.blob);
      const anchor = document.createElement("a");
      try {
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
      } finally {
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
      }
      return { filename };
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: orderKeys.all }),
        queryClient.invalidateQueries({ queryKey: calculationRunKeys.all }),
      ]);
    },
  });
}
