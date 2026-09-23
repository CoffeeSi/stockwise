import { z } from "zod";
export const shellSearchSchema = z.strictObject({ search: z.string().trim().max(200) });
export type ShellSearch = z.infer<typeof shellSearchSchema>;
