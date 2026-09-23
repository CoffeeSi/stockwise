import { z } from "zod";
import { apiDateTimeSchema, apiDecimalSchema, apiUuidSchema } from "@/shared/api";

const monthSchema = z.string().regex(/^\d{4}-(?:0[1-9]|1[0-2])$/);
const nonnegativeDecimalSchema = apiDecimalSchema.pipe(z.number().nonnegative());

export const analyticsFiltersSchema = z.strictObject({
  supplier_id: apiUuidSchema.optional(),
  warehouse_id: apiUuidSchema.optional(),
  category_id: apiUuidSchema.optional(),
});
export const demandSeriesFiltersSchema = analyticsFiltersSchema.extend({
  product_id: apiUuidSchema.optional(),
  months: z.number().int().min(1).max(24).optional(),
});
export const outlierFiltersSchema = analyticsFiltersSchema.extend({
  product_id: apiUuidSchema.optional(),
  limit: z.number().int().min(1).max(100).optional(),
  offset: z.number().int().nonnegative().optional(),
});

export const recommendationHistorySchema = z.object({
  recommendation_id: apiUuidSchema,
  run_id: apiUuidSchema,
  points: z.array(z.object({ month: monthSchema, sales: apiDecimalSchema, stock: apiDecimalSchema.nullable() })),
});
export const demandSeriesSchema = z.object({
  run_id: apiUuidSchema,
  points: z.array(z.object({
    month: monthSchema,
    raw_sales: apiDecimalSchema,
    cleaned_demand: nonnegativeDecimalSchema,
    stock: apiDecimalSchema.nullable(),
  })),
  algorithm_version: z.string().min(1),
  available_months: z.number().int().nonnegative(),
});
export const abcXyzSchema = z.object({
  run_id: apiUuidSchema,
  cells: z.array(z.object({
    abc: z.enum(["A", "B", "C"]),
    xyz: z.enum(["X", "Y", "Z"]),
    sku_count: z.number().int().nonnegative(),
    demand_share: nonnegativeDecimalSchema.pipe(z.number().max(1)),
  })),
  algorithm_version: z.string().min(1),
  metadata: z.object({
    version: z.string().min(1),
    abc_method: z.string(),
    abc_a_share: nonnegativeDecimalSchema.pipe(z.number().max(1)),
    abc_b_share: nonnegativeDecimalSchema.pipe(z.number().max(1)),
    xyz_method: z.string(),
    xyz_x_cv: nonnegativeDecimalSchema,
    xyz_y_cv: nonnegativeDecimalSchema,
  }),
});
export const outlierSchema = z.object({
  id: apiUuidSchema,
  sales_transaction_id: apiUuidSchema,
  product_id: apiUuidSchema,
  sku: z.string(),
  warehouse_id: apiUuidSchema,
  occurred_at: apiDateTimeSchema,
  method: z.string(),
  original_quantity: apiDecimalSchema,
  replacement_quantity: apiDecimalSchema,
  threshold: apiDecimalSchema.nullable(),
  reason: z.string(),
});
export const outlierPageSchema = z.object({
  items: z.array(outlierSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});

export type AnalyticsFilters = z.infer<typeof analyticsFiltersSchema>;
export type DemandSeriesFilters = z.infer<typeof demandSeriesFiltersSchema>;
export type OutlierFilters = z.infer<typeof outlierFiltersSchema>;
export type RecommendationHistory = z.infer<typeof recommendationHistorySchema>;
export type DemandSeries = z.infer<typeof demandSeriesSchema>;
export type AbcXyz = z.infer<typeof abcXyzSchema>;
export type Outlier = z.infer<typeof outlierSchema>;
export type OutlierPage = z.infer<typeof outlierPageSchema>;
