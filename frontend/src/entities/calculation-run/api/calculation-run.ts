import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "@/shared/api";
import {
  calculationRunSchema,
  calculationRunFiltersSchema,
  calculationRunPageSchema,
  demandTrendPointSchema,
  createCalculationRunInputSchema,
  runRecommendationFiltersSchema,
  runRecommendationsPageSchema,
  type CreateCalculationRunInput,
  type CalculationRunFilters,
  type RunRecommendationFilters,
} from "../model/schema";

export const calculationRunKeys = {
  all: ["calculation-run"] as const,
  lists: () => [...calculationRunKeys.all, "list"] as const,
  list: (filters: CalculationRunFilters) => [...calculationRunKeys.lists(), filters] as const,
  detail: (id: string) => [...calculationRunKeys.all, id] as const,
  recommendations: (id: string, filters: RunRecommendationFilters = {}) =>
    [...calculationRunKeys.detail(id), "recommendations", filters] as const,
  trends: (id: string) => [...calculationRunKeys.detail(id), "demand-trends"] as const,
};

export function demandTrendsQueryOptions(id: string, init?: RequestInit) {
  return queryOptions({
    queryKey: calculationRunKeys.trends(id),
    queryFn: ({ signal }) => apiRequest(`/api/calculation-runs/${encodeURIComponent(id)}/demand-trends`, z.array(demandTrendPointSchema), { ...init, signal }),
    retry: false,
  });
}

export function calculationRunsQueryOptions(input: CalculationRunFilters = {}, init?: RequestInit) {
  const filters = calculationRunFiltersSchema.parse(input);
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) search.set(key, String(value));
  }
  return queryOptions({
    queryKey: calculationRunKeys.list(filters),
    queryFn: ({ signal }) => apiRequest(`/api/calculation-runs?${search}`, calculationRunPageSchema, { ...init, signal }),
    retry: false,
  });
}

export function calculationRunQueryOptions(id: string, init?: RequestInit) {
  return queryOptions({
    queryKey: calculationRunKeys.detail(id),
    queryFn: ({ signal }) => apiRequest(`/api/calculation-runs/${encodeURIComponent(id)}`, calculationRunSchema, { ...init, signal }),
    retry: false,
  });
}

export function runRecommendationsQueryOptions(id: string, input: RunRecommendationFilters = {}, init?: RequestInit) {
  const filters = runRecommendationFiltersSchema.parse(input);
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null) search.set(key, String(value));
  }
  const suffix = search.size ? `?${search.toString()}` : "";
  return queryOptions({
    queryKey: calculationRunKeys.recommendations(id, filters),
    queryFn: ({ signal }) => apiRequest(`/api/calculation-runs/${encodeURIComponent(id)}/recommendations${suffix}`, runRecommendationsPageSchema, { ...init, signal }),
    retry: false,
  });
}

export function createCalculationRun(input: CreateCalculationRunInput, idempotencyKey: string) {
  const payload = createCalculationRunInputSchema.parse(input);
  return apiRequest("/api/calculation-runs", calculationRunSchema, {
    method: "POST",
    headers: { "Idempotency-Key": z.uuid().parse(idempotencyKey) },
    body: JSON.stringify(payload),
  });
}
