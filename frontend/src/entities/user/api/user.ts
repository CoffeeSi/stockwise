import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "@/shared/api";
import { loginInputSchema, registrationInputSchema, userRoleSchema, userSchema, type LoginInput, type RegistrationInput, type User } from "../model/schema";

export const userKeys = { all: ["auth"] as const, me: ["auth", "me"] as const, list: (offset: number) => ["auth", "users", offset] as const };
export function currentUserQueryOptions() {
  return queryOptions({ queryKey: userKeys.me, queryFn: () => apiRequest("/api/auth/me", userSchema), retry: false, staleTime: 30_000 });
}
export function usersQueryOptions(offset = 0) {
  return queryOptions({ queryKey: userKeys.list(offset), queryFn: () => apiRequest(`/api/auth/users?limit=50&offset=${offset}`, z.array(userSchema)), retry: false });
}
export function login(input: LoginInput) {
  return apiRequest("/api/auth/login", z.object({ token_type: z.literal("bearer"), expires_in: z.number().positive() }), { method: "POST", body: JSON.stringify(loginInputSchema.parse(input)) });
}
export function registerUser(input: RegistrationInput) {
  return apiRequest("/api/auth/register", userSchema, { method: "POST", body: JSON.stringify(registrationInputSchema.parse(input)) });
}
export function logout() {
  return apiRequest("/api/auth/logout", z.object({ success: z.literal(true) }), { method: "POST" });
}
export function updateUserRole(id: string, role: User["role"]) {
  return apiRequest(`/api/auth/users/${z.uuid().parse(id)}/role`, userSchema, { method: "PATCH", body: JSON.stringify({ role: userRoleSchema.parse(role) }) });
}
