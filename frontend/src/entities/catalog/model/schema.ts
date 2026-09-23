import { z } from "zod";
import { apiUuidSchema } from "@/shared/api";

export const catalogItemSchema = z.object({ id: apiUuidSchema, code: z.string(), name: z.string(), is_active: z.boolean() });
export const categorySchema = catalogItemSchema.extend({ parent_id: apiUuidSchema.nullable() });
export const supplierPageSchema = z.object({
  items: z.array(catalogItemSchema), total: z.number().int().nonnegative(),
  limit: z.number().int().positive(), offset: z.number().int().nonnegative(),
});
export const warehouseListSchema = z.object({ items: z.array(catalogItemSchema) });
export const categoryListSchema = z.object({ items: z.array(categorySchema) });
export const catalogFiltersSchema = z.strictObject({ active_only: z.boolean().optional(), search: z.string().trim().max(120).optional() });
export const supplierFiltersSchema = catalogFiltersSchema.extend({ limit: z.number().int().min(1).max(100).optional(), offset: z.number().int().nonnegative().optional() });
export type CatalogItem = z.infer<typeof catalogItemSchema>;
export type CatalogFilters = z.infer<typeof catalogFiltersSchema>;
export type SupplierFilters = z.infer<typeof supplierFiltersSchema>;
