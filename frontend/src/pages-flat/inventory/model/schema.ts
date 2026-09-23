import { z } from "zod";

export const runSelectionSchema = z.strictObject({ runId: z.uuid("Выберите расчёт из истории.") });
export type RunSelection = z.infer<typeof runSelectionSchema>;
