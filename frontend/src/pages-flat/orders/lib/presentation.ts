import type { OrderStatus } from "@/entities/order";

export const orderStatusPresentation: Record<OrderStatus, { label: string; tone: "amber" | "green" | "blue" | "gray" }> = {
  draft: { label: "Черновик", tone: "amber" },
  approved: { label: "Утверждён", tone: "green" },
  exported: { label: "Экспортирован", tone: "blue" },
  cancelled: { label: "Отменён", tone: "gray" },
};

export function formatOrderDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

export function formatOrderAmount(amount: number | null, currency: string | null): string {
  if (amount === null) return "Стоимость неизвестна";
  const formatted = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 4 }).format(amount);
  return currency ? `${formatted} ${currency}` : `${formatted} · валюта не указана`;
}
