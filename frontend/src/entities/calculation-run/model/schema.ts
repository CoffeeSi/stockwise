import { z } from "zod";
import { apiDateTimeSchema, apiDecimalSchema, apiUuidSchema } from "@/shared/api";

export const calculationRunStatusSchema = z.enum(["pending", "running", "completed", "failed"]);
export const demandTrendPointSchema = z.object({
  category_id: apiUuidSchema.nullable(),
  period_start: z.iso.date(),
  period_end: z.iso.date(),
  raw_demand: apiDecimalSchema,
  cleaned_demand: apiDecimalSchema,
  stockout_adjustment: apiDecimalSchema,
});
export const demandSourceSchema = z.enum(["transactions", "monthly_sales"]);
export const createCalculationRunInputSchema = z.strictObject({
  demand_source: demandSourceSchema,
  horizon_days: z.number().int().positive(),
  warehouse_id: apiUuidSchema.nullable().optional(),
  category_id: apiUuidSchema.nullable().optional(),
});
export const calculationRunSchema = z.object({
  id: apiUuidSchema,
  status: calculationRunStatusSchema,
  parameters: z.object({
    horizon_days: z.number().int().nullable().optional(),
    demand_source: demandSourceSchema.nullable().optional(),
    warehouse_id: apiUuidSchema.nullable().optional(),
    category_id: apiUuidSchema.nullable().optional(),
  }),
  started_at: apiDateTimeSchema,
  finished_at: apiDateTimeSchema.nullable(),
  algorithm_version: z.string(),
  import_batch_ids: z.array(apiUuidSchema),
  recommendation_count: z.number().int().nonnegative().nullable(),
  error_details: z.record(z.string(), z.string()).nullable(),
});

export const runRecommendationFiltersSchema = z.strictObject({
  supplier_id: apiUuidSchema.nullable().optional(),
  warehouse_id: apiUuidSchema.nullable().optional(),
  category_id: apiUuidSchema.nullable().optional(),
  urgency: z.enum(["low", "medium", "high", "critical"]).nullable().optional(),
  status: z.enum(["suggested", "adjusted", "accepted", "rejected", "converted_to_order"]).nullable().optional(),
  sort_by: z.enum(["risk_score", "recommended_quantity", "created_at", "urgency", "product_id"]).optional(),
  descending: z.boolean().optional(),
  limit: z.number().int().min(1).max(500).optional(),
  offset: z.number().int().nonnegative().optional(),
});

// The calculation-run slice owns this DTO copy because sibling entity imports are disallowed by FSD.
const runCalculationComponentsSchema = z.object({
  baseline: apiDecimalSchema.nullable().optional(),
  raw_demand: apiDecimalSchema.nullable().optional(),
  return_adjustment: apiDecimalSchema.nullable().optional(),
  anomaly_adjustment: apiDecimalSchema.nullable().optional(),
  stockout_compensation: apiDecimalSchema.nullable().optional(),
  growth_rate: apiDecimalSchema.nullable().optional(),
  growth_multiplier: apiDecimalSchema.nullable().optional(),
  seasonality_index: apiDecimalSchema.nullable().optional(),
  forecast: apiDecimalSchema.nullable().optional(),
  demand_during_horizon: apiDecimalSchema.nullable().optional(),
  coverage_days: z.number().int().nullable().optional(),
  lead_time_days: z.number().int().nullable().optional(),
  safety_stock: apiDecimalSchema.nullable().optional(),
  current_stock: apiDecimalSchema.nullable().optional(),
  in_transit: apiDecimalSchema.nullable().optional(),
  material_requirements: apiDecimalSchema.nullable().optional(),
  available_supply: apiDecimalSchema.nullable().optional(),
  shortage_quantity: apiDecimalSchema.nullable().optional(),
  quantity_before_rounding: apiDecimalSchema.nullable().optional(),
  moq: apiDecimalSchema.nullable().optional(),
  package_size: apiDecimalSchema.nullable().optional(),
  quantity_after_rounding: apiDecimalSchema.nullable().optional(),
  risk_score: apiDecimalSchema.nullable().optional(),
  urgency: z.enum(["low", "medium", "high", "critical"]).nullable().optional(),
  shortage_ratio: apiDecimalSchema.nullable().optional(),
  lead_time_gap_ratio: apiDecimalSchema.nullable().optional(),
  expected_stockout_at: apiDateTimeSchema.nullable().optional(),
});

const runRecommendationSchema = z.object({
  id: apiUuidSchema,
  calculation_run_id: apiUuidSchema,
  product_id: apiUuidSchema,
  warehouse_id: apiUuidSchema,
  supplier_id: apiUuidSchema,
  forecast_quantity: apiDecimalSchema,
  current_stock: apiDecimalSchema,
  in_transit_quantity: apiDecimalSchema,
  material_requirement_quantity: apiDecimalSchema,
  safety_stock: apiDecimalSchema,
  shortage_quantity: apiDecimalSchema,
  quantity_before_rounding: apiDecimalSchema,
  moq: apiDecimalSchema,
  package_size: apiDecimalSchema,
  recommended_quantity: apiDecimalSchema,
  effective_quantity: apiDecimalSchema,
  risk_score: apiDecimalSchema,
  urgency: z.enum(["low", "medium", "high", "critical"]),
  status: z.enum(["suggested", "adjusted", "accepted", "rejected", "converted_to_order"]),
  version: z.number().int().positive(),
  explanation: z.string(),
  calculation_details: runCalculationComponentsSchema,
  created_at: apiDateTimeSchema,
  updated_at: apiDateTimeSchema,
});

export const runRecommendationsPageSchema = z.object({
  items: z.array(runRecommendationSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});

export type CalculationRun = z.infer<typeof calculationRunSchema>;
export type DemandTrendPoint = z.infer<typeof demandTrendPointSchema>;
export type CreateCalculationRunInput = z.infer<typeof createCalculationRunInputSchema>;
export type RunRecommendationFilters = z.infer<typeof runRecommendationFiltersSchema>;
export type RunRecommendation = z.infer<typeof runRecommendationSchema>;
export type RunRecommendationsPage = z.infer<typeof runRecommendationsPageSchema>;
