import { z } from "zod";

export const userRoleSchema = z.enum(["viewer", "buyer", "admin"]);
export const userSchema = z.object({ id: z.uuid(), username: z.string(), display_name: z.string(), role: userRoleSchema });
export const loginInputSchema = z.strictObject({ username: z.string().trim().min(3).max(255), password: z.string().min(1).max(256) });
export const registrationInputSchema = loginInputSchema.extend({
  username: z.string().trim().min(3).max(255).regex(/^[A-Za-z0-9][A-Za-z0-9._@+-]*$/, "Используйте латиницу, цифры и . _ @ + -"),
  display_name: z.string().trim().min(1).max(255),
  password: z.string().min(12, "Минимум 12 символов").max(256),
});
export type User = z.infer<typeof userSchema>;
export type LoginInput = z.infer<typeof loginInputSchema>;
export type RegistrationInput = z.infer<typeof registrationInputSchema>;
