"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { calculationRunKeys } from "@/entities/calculation-run";
import { acceptRecommendations, recommendationKeys } from "@/entities/recommendation";

export function useAcceptRecommendations() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: acceptRecommendations,
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: calculationRunKeys.all }),
        client.invalidateQueries({ queryKey: recommendationKeys.all }),
      ]);
    },
  });
}
