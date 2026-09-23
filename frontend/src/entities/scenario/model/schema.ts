import { z } from "zod";
import { apiDecimalSchema, apiUuidSchema } from "@/shared/api";

export const scenarioInputSchema = z.strictObject({
  base_run_id: apiUuidSchema,
  growth_multiplier: z.number().finite().positive().max(100),
  service_level: z.number().finite().positive().max(1),
  supplier_delay_days: z.number().int().min(0).max(3650),
  include_anomalies: z.boolean(),
  budget_limit: z.number().finite().positive().nullable(),
});
export const scenarioPreviewSchema = z.object({
  base_run_id: apiUuidSchema, is_preview: z.literal(true), method: z.string(), limitations: z.array(z.string()),
  assumptions: z.object({ base_run_id: apiUuidSchema, growth_multiplier: apiDecimalSchema, service_level: apiDecimalSchema, supplier_delay_days: z.number().int(), include_anomalies: z.boolean(), budget_limit: apiDecimalSchema.nullable() }),
  totals: z.object({ amount: apiDecimalSchema.nullable(), currency: z.string().nullable(), quantity: apiDecimalSchema, critical_count: z.number().int(), budget_gap: apiDecimalSchema.nullable() }),
  items: z.array(z.object({ recommendation_id: apiUuidSchema, baseline_quantity: apiDecimalSchema, simulated_quantity: apiDecimalSchema, reason: z.string() })),
});
export type ScenarioInput = z.infer<typeof scenarioInputSchema>;
