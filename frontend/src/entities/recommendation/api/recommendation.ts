import { queryOptions } from "@tanstack/react-query";
import { apiRequest } from "@/shared/api";
import {
  adjustRecommendationInputSchema,
  acceptRecommendationInputSchema,
  acceptRecommendationsInputSchema,
  acceptRecommendationsResponseSchema,
  recommendationExplanationSchema,
  recommendationSchema,
  type AdjustRecommendationInput,
  type AcceptRecommendationsInput,
} from "../model/schema";

export const recommendationKeys = {
  all: ["recommendation"] as const,
  explanation: (id: string) => [...recommendationKeys.all, id, "explanation"] as const,
};

export function recommendationExplanationQueryOptions(id: string) {
  return queryOptions({
    queryKey: recommendationKeys.explanation(id),
    queryFn: () => apiRequest(`/api/recommendations/${encodeURIComponent(id)}/explain`, recommendationExplanationSchema),
    retry: false,
  });
}

export function adjustRecommendation(id: string, input: AdjustRecommendationInput) {
  const payload = adjustRecommendationInputSchema.parse(input);
  return apiRequest(`/api/recommendations/${encodeURIComponent(id)}`, recommendationSchema, {
    method: "PATCH",
    body: JSON.stringify({ ...payload, new_quantity: String(payload.new_quantity) }),
  });
}

export function acceptRecommendation(id: string, version: number) {
  const payload = acceptRecommendationInputSchema.parse({ version });
  return apiRequest(`/api/recommendations/${encodeURIComponent(id)}/accept`, recommendationSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function acceptRecommendations(input: AcceptRecommendationsInput) {
  const payload = acceptRecommendationsInputSchema.parse(input);
  return apiRequest("/api/recommendations/bulk/accept", acceptRecommendationsResponseSchema, { method: "POST", body: JSON.stringify(payload) });
}
