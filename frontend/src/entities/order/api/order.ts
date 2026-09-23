import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiDownloadWithFilename, apiRequest } from "@/shared/api";
import {
  createOrdersInputSchema,
  createSelectedOrdersInputSchema,
  createSelectedOrdersResponseSchema,
  orderExportSchema,
  orderFiltersSchema,
  orderPageSchema,
  orderSchema,
  type CreateOrdersInput,
  type CreateSelectedOrdersInput,
  type OrderFilters,
} from "../model/schema";

export const orderKeys = {
  all: ["order"] as const,
  lists: () => [...orderKeys.all, "list"] as const,
  list: (filters: OrderFilters) => [...orderKeys.lists(), filters] as const,
  detail: (id: string) => [...orderKeys.all, "detail", id] as const,
};

export function ordersQueryOptions(input: OrderFilters = {}, init?: RequestInit) {
  const filters = orderFiltersSchema.parse(input);
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const suffix = search.size ? `?${search.toString()}` : "";
  return queryOptions({
    queryKey: orderKeys.list(filters),
    queryFn: ({ signal }) => apiRequest(`/api/orders${suffix}`, orderPageSchema, { ...init, signal }),
    retry: false,
  });
}

export function orderQueryOptions(id: string, init?: RequestInit) {
  return queryOptions({
    queryKey: orderKeys.detail(id),
    queryFn: ({ signal }) => apiRequest(`/api/orders/${encodeURIComponent(id)}`, orderSchema, { ...init, signal }),
    retry: false,
  });
}

export function createOrders(input: CreateOrdersInput) {
  const payload = createOrdersInputSchema.parse(input);
  return apiRequest("/api/orders", z.array(orderSchema), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createSelectedOrders(input: CreateSelectedOrdersInput) {
  const payload = createSelectedOrdersInputSchema.parse(input);
  return apiRequest("/api/orders/bulk", createSelectedOrdersResponseSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveOrder(id: string) {
  return apiRequest(`/api/orders/${encodeURIComponent(id)}/approve`, orderSchema, { method: "POST" });
}

export function createOrderExport(id: string) {
  return apiRequest(`/api/orders/${encodeURIComponent(id)}/export`, orderExportSchema, { method: "POST" });
}

export function downloadOrderExport(id: string): Promise<{ blob: Blob; filename: string | null }> {
  return apiDownloadWithFilename(`/api/orders/${encodeURIComponent(id)}/export`);
}
