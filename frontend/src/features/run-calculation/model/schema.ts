import { z } from "zod";

export const runCalculationSchema = z.strictObject({
  demand_source: z.enum(["transactions", "monthly_sales"]),
  horizon_days: z.number().int("Укажите целое число дней.").min(1, "Минимум 1 день.").max(365, "Максимум 365 дней."),
  warehouse_id: z.uuid("Некорректный ID склада.").nullable().optional(),
  category_id: z.uuid("Некорректный ID категории.").nullable().optional(),
  budget_limit: z.string().regex(/^\d+(?:\.\d{1,4})?$/, "Укажите положительную сумму с точностью до 4 знаков.")
    .refine((value) => Number.isFinite(Number(value)) && Number(value) > 0, "Бюджет должен быть больше нуля.").nullable().optional(),
  currency: z.string().regex(/^[A-Z]{3}$/, "Три заглавные латинские буквы, например KZT.").nullable().optional(),
}).superRefine((value, context) => {
  if (value.budget_limit && !value.currency) context.addIssue({ code: "custom", path: ["currency"], message: "Укажите единую валюту бюджета." });
});

export type RunCalculationInput = z.infer<typeof runCalculationSchema>;
