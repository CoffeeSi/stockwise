import { z } from "zod";
import { apiDateTimeSchema, apiDecimalSchema, apiUuidSchema } from "@/shared/api";

export const orderStatusSchema = z.enum(["draft", "approved", "exported", "cancelled"]);
export const createOrdersInputSchema = z.strictObject({ calculation_run_id: apiUuidSchema });
export const createSelectedOrdersInputSchema = z.strictObject({
  calculation_run_id: apiUuidSchema,
  recommendation_ids: z.array(apiUuidSchema).min(1, "Выберите принятые рекомендации.").max(500)
    .refine((ids) => new Set(ids).size === ids.length, "Рекомендации не должны повторяться."),
});
export const orderFiltersSchema = z.strictObject({
  calculation_run_id: apiUuidSchema.optional(),
  supplier_id: apiUuidSchema.optional(),
  status: orderStatusSchema.optional(),
  limit: z.number().int().min(1).max(100).optional(),
  offset: z.number().int().nonnegative().optional(),
});
export const orderItemSchema = z.object({
  id: apiUuidSchema,
  recommendation_id: apiUuidSchema,
  product_id: apiUuidSchema,
  recommended_quantity: apiDecimalSchema,
  approved_quantity: apiDecimalSchema,
  unit_price: apiDecimalSchema.nullable(),
  total_amount: apiDecimalSchema.nullable(),
});
export const orderSchema = z.object({
  id: apiUuidSchema,
  order_number: z.string(),
  supplier_id: apiUuidSchema,
  warehouse_id: apiUuidSchema,
  created_from_run_id: apiUuidSchema,
  status: orderStatusSchema,
  created_by: apiUuidSchema,
  created_at: apiDateTimeSchema,
  approved_by: apiUuidSchema.nullable(),
  approved_at: apiDateTimeSchema.nullable(),
  exported_at: apiDateTimeSchema.nullable(),
  items: z.array(orderItemSchema),
});
export const orderExportSchema = z.object({
  id: apiUuidSchema,
  purchase_order_id: apiUuidSchema,
  format: z.literal("xlsx"),
  file_name: z.string(),
  file_checksum: z.string(),
  created_by: apiUuidSchema,
  created_at: apiDateTimeSchema,
});
export const orderSummarySchema = z.object({
  id: apiUuidSchema,
  order_number: z.string(),
  supplier_id: apiUuidSchema,
  supplier_name: z.string(),
  warehouse_id: apiUuidSchema,
  warehouse_name: z.string(),
  status: orderStatusSchema,
  created_at: apiDateTimeSchema,
  approved_at: apiDateTimeSchema.nullable(),
  item_count: z.number().int().nonnegative(),
  total_amount: apiDecimalSchema.nullable(),
  currency: z.string().nullable(),
});
export const orderPageSchema = z.object({
  items: z.array(orderSummarySchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});
export const createSelectedOrdersResponseSchema = z.object({
  orders: z.array(orderSchema),
  consumed_recommendation_ids: z.array(apiUuidSchema),
});

export type Order = z.infer<typeof orderSchema>;
export type OrderExport = z.infer<typeof orderExportSchema>;
export type CreateOrdersInput = z.infer<typeof createOrdersInputSchema>;
export type CreateSelectedOrdersInput = z.infer<typeof createSelectedOrdersInputSchema>;
export type OrderFilters = z.infer<typeof orderFiltersSchema>;
export type OrderSummary = z.infer<typeof orderSummarySchema>;
export type OrderPage = z.infer<typeof orderPageSchema>;
export type OrderStatus = z.infer<typeof orderStatusSchema>;
