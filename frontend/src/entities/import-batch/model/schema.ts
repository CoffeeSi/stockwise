import { z } from "zod";
import { apiUuidSchema } from "@/shared/api";

export const importSourceTypeSchema = z.enum([
  "sales", "monthly_sales", "inventory", "stockout", "in_transit",
  "seasonality", "supplier_terms", "growth", "material_requirements",
]);
export const importStatusSchema = z.enum(["pending", "processing", "completed", "failed"]);
export const importValidationIssueSchema = z.union([
  z.object({ missing_columns: z.array(z.string()) }),
  z.object({ row: z.number().int().nonnegative(), message: z.string() }),
  z.object({ message: z.string() }),
]);
export const importBatchSchema = z.object({
  batch_id: apiUuidSchema,
  source_type: importSourceTypeSchema,
  status: importStatusSchema,
  row_count: z.number().int().nonnegative(),
  file_checksum: z.string(),
  validation_errors: z.array(importValidationIssueSchema),
  warnings: z.array(z.object({ code: z.string(), count: z.number().int().nonnegative() })).default([]),
  progress: z.object({
    stage: z.enum(["uploaded", "validating", "persisting", "completed"]),
    processed_rows: z.number().int().nonnegative(),
    total_rows: z.number().int().nonnegative().nullable().optional(),
  }).nullable().optional(),
});
export const importBatchDetailSchema = importBatchSchema.extend({
  file_name: z.string(),
  error_details: z.object({ code: z.string() }).nullable(),
});

export type ImportSourceType = z.infer<typeof importSourceTypeSchema>;
export type ImportBatch = z.infer<typeof importBatchSchema>;
export type ImportBatchDetail = z.infer<typeof importBatchDetailSchema>;
export type ImportValidationIssue = z.infer<typeof importValidationIssueSchema>;
