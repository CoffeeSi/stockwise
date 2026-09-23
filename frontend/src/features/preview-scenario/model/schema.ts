import { z } from "zod";
export const previewFormSchema = z.strictObject({
  base_run_id: z.uuid("Выберите завершённый расчёт"),
  growth_multiplier: z.number().finite().positive().max(100),
  service_level: z.number().finite().positive().max(1),
  supplier_delay_days: z.number().int().min(0).max(3650),
  include_anomalies: z.boolean(),
  budget_enabled: z.boolean(),
  budget_limit: z.number().finite().nonnegative(),
}).refine((data) => !data.budget_enabled || data.budget_limit > 0, { path: ["budget_limit"], message: "Укажите положительный бюджет" });
export type PreviewForm = z.infer<typeof previewFormSchema>;
