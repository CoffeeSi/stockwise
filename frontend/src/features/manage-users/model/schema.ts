import { z } from "zod";
import { userRoleSchema } from "@/entities/user";
export const roleFormSchema = z.strictObject({ role: userRoleSchema });
export type RoleForm = z.infer<typeof roleFormSchema>;
