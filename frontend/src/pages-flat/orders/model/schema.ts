import { z } from "zod";
import { orderStatusSchema } from "@/entities/order";
import { apiUuidSchema } from "@/shared/api";

const optionalIdSchema = z.union([z.literal(""), apiUuidSchema]);

export const orderListFormSchema = z.strictObject({
  runId: optionalIdSchema,
  supplierId: optionalIdSchema,
  status: z.union([z.literal(""), orderStatusSchema]),
});

export type OrderListForm = z.infer<typeof orderListFormSchema>;
