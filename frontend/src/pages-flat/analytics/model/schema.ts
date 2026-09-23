import { z } from "zod";

const optionalId = z.union([z.literal(""), z.uuid()]);

export const analyticsFormSchema = z.strictObject({
  runId: optionalId,
  supplierId: optionalId,
  warehouseId: optionalId,
  categoryId: optionalId,
  months: z.number().int().min(1).max(24),
});

export type AnalyticsForm = z.infer<typeof analyticsFormSchema>;
