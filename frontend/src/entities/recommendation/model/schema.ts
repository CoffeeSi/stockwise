import { z } from "zod";
import { apiDateSchema, apiDateTimeSchema, apiDecimalSchema, apiUuidSchema } from "@/shared/api";

export const urgencySchema = z.enum(["low", "medium", "high", "critical"]);
export const recommendationStatusSchema = z.enum([
  "suggested", "adjusted", "accepted", "rejected", "converted_to_order",
]);

export const calculationComponentsSchema = z.object({
  budget_allocation: z.object({ method: z.string(), unconstrained_quantity: apiDecimalSchema, allocated_quantity: apiDecimalSchema }).nullable().optional(),
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
  urgency: urgencySchema.nullable().optional(),
  shortage_ratio: apiDecimalSchema.nullable().optional(),
  lead_time_gap_ratio: apiDecimalSchema.nullable().optional(),
  expected_stockout_at: apiDateTimeSchema.nullable().optional(),
});

export const recommendationSchema = z.object({
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
  urgency: urgencySchema,
  status: recommendationStatusSchema,
  version: z.number().int().positive(),
  explanation: z.string(),
  calculation_details: calculationComponentsSchema,
  created_at: apiDateTimeSchema,
  updated_at: apiDateTimeSchema,
});

export const recommendationPageSchema = z.object({
  items: z.array(recommendationSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});

export const anomalySchema = z.object({
  id: apiUuidSchema,
  sales_transaction_id: apiUuidSchema,
  method: z.string(),
  original_quantity: apiDecimalSchema,
  replacement_quantity: apiDecimalSchema,
  threshold: apiDecimalSchema.nullable(),
  reason: z.string(),
});

export const forecastSchema = z.object({
  id: apiUuidSchema,
  product_id: apiUuidSchema,
  warehouse_id: apiUuidSchema,
  period_start: apiDateSchema,
  period_end: apiDateSchema,
  raw_demand: apiDecimalSchema,
  return_adjustment: apiDecimalSchema,
  anomaly_adjustment: apiDecimalSchema,
  stockout_adjustment: apiDecimalSchema,
  cleaned_baseline: apiDecimalSchema,
  growth_rate: apiDecimalSchema,
  seasonality_index: apiDecimalSchema,
  forecast_quantity: apiDecimalSchema,
});

export const recommendationExplanationSchema = z.object({
  recommendation_id: apiUuidSchema,
  formula: z.string(),
  components: calculationComponentsSchema,
  anomalies: z.array(anomalySchema),
  forecast: forecastSchema,
  text: z.string(),
});

export const adjustRecommendationInputSchema = z.strictObject({
  new_quantity: z.number().finite().nonnegative(),
  reason: z.string().trim().min(1).max(2000),
  version: z.number().int().positive(),
});

export const acceptRecommendationInputSchema = z.strictObject({ version: z.number().int().positive() });
export const acceptRecommendationsInputSchema = z.strictObject({
  calculation_run_id: apiUuidSchema,
  items: z.array(z.strictObject({ recommendation_id: apiUuidSchema, version: z.number().int().positive() })).min(1).max(500)
    .refine((items) => new Set(items.map((item) => item.recommendation_id)).size === items.length, "Рекомендации не должны повторяться."),
});
export const acceptRecommendationsResponseSchema = z.object({ items: z.array(recommendationSchema), accepted_count: z.number().int().nonnegative() });

export type Recommendation = z.infer<typeof recommendationSchema>;
export type RecommendationPage = z.infer<typeof recommendationPageSchema>;
export type RecommendationExplanation = z.infer<typeof recommendationExplanationSchema>;
export type AdjustRecommendationInput = z.infer<typeof adjustRecommendationInputSchema>;
export type AcceptRecommendationsInput = z.infer<typeof acceptRecommendationsInputSchema>;
