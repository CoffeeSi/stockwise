import { z } from "zod";

const optionalId = z.union([z.literal(""), z.uuid()]);
export const recommendationFilterFormSchema = z.strictObject({
  search: z.string().trim().max(120, "Не более 120 символов."),
  supplier_id: optionalId,
  warehouse_id: optionalId,
  category_id: optionalId,
  urgency: z.enum(["", "low", "medium", "high", "critical"]),
  status: z.enum(["", "suggested", "adjusted", "accepted", "rejected", "converted_to_order"]),
  sort_by: z.enum(["risk_score", "recommended_quantity", "created_at", "urgency", "product_id"]),
  direction: z.enum(["descending", "ascending"]),
});
export type RecommendationFilterForm = z.infer<typeof recommendationFilterFormSchema>;
