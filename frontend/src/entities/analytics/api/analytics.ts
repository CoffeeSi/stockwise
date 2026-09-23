import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "@/shared/api";
import {
  abcXyzSchema, analyticsFiltersSchema, demandSeriesFiltersSchema, demandSeriesSchema,
  outlierFiltersSchema, outlierPageSchema, recommendationHistorySchema,
  type AnalyticsFilters, type DemandSeriesFilters, type OutlierFilters,
} from "../model/schema";

export const analyticsKeys = {
  all: ["analytics"] as const,
  history: (id: string, months: number) => [...analyticsKeys.all, "history", id, months] as const,
  demandSeries: (id: string, filters: DemandSeriesFilters) => [...analyticsKeys.all, "demand-series", id, filters] as const,
  abcXyz: (id: string, filters: AnalyticsFilters) => [...analyticsKeys.all, "abc-xyz", id, filters] as const,
  outliers: (id: string, filters: OutlierFilters) => [...analyticsKeys.all, "outliers", id, filters] as const,
};

function queryString(runId: string, filters: DemandSeriesFilters | OutlierFilters): string {
  const params = new URLSearchParams({ calculation_run_id: runId });
  for (const [key, value] of Object.entries(filters)) if (value !== undefined) params.set(key, String(value));
  return params.toString();
}

export function recommendationHistoryQueryOptions(id: string, months = 24, init?: RequestInit) {
  const parsedMonths = z.number().int().min(1).max(24).parse(months);
  return queryOptions({
    queryKey: analyticsKeys.history(id, parsedMonths),
    queryFn: ({ signal }) => apiRequest(`/api/recommendations/${encodeURIComponent(id)}/history?months=${parsedMonths}`, recommendationHistorySchema, { ...init, signal }),
    retry: false,
  });
}

export function demandSeriesQueryOptions(runId: string, input: DemandSeriesFilters = {}, init?: RequestInit) {
  const filters = demandSeriesFiltersSchema.parse(input);
  return queryOptions({
    queryKey: analyticsKeys.demandSeries(runId, filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/analytics/demand-series?${queryString(runId, filters)}`, demandSeriesSchema, { ...init, signal }),
    retry: false,
  });
}

export function abcXyzQueryOptions(runId: string, input: AnalyticsFilters = {}, init?: RequestInit) {
  const filters = analyticsFiltersSchema.parse(input);
  return queryOptions({
    queryKey: analyticsKeys.abcXyz(runId, filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/analytics/abc-xyz?${queryString(runId, filters)}`, abcXyzSchema, { ...init, signal }),
    retry: false,
  });
}

export function outliersQueryOptions(runId: string, input: OutlierFilters = {}, init?: RequestInit) {
  const filters = outlierFiltersSchema.parse(input);
  return queryOptions({
    queryKey: analyticsKeys.outliers(runId, filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/analytics/outliers?${queryString(runId, filters)}`, outlierPageSchema, { ...init, signal }),
    retry: false,
  });
}
