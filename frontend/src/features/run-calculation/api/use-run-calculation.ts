"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { calculationRunKeys, createCalculationRun, type CreateCalculationRunInput } from "@/entities/calculation-run";
import { ApiError } from "@/shared/api";
import { useCalculationSessionStore } from "../model/run-session";

export function useRunCalculation() {
  const client = useQueryClient();
  const setActiveRunId = useCalculationSessionStore((state) => state.setActiveRunId);
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);
  return useMutation({
    mutationFn: (input: CreateCalculationRunInput) => {
      const fingerprint = JSON.stringify(input);
      const current = attempt.current?.fingerprint === fingerprint ? attempt.current : { fingerprint, key: crypto.randomUUID() };
      attempt.current = current;
      return createCalculationRun(input, current.key);
    },
    onSuccess: async (run) => {
      attempt.current = null;
      client.setQueryData(calculationRunKeys.detail(run.id), run);
      setActiveRunId(run.id);
      await client.invalidateQueries({ queryKey: calculationRunKeys.lists() });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 408 && error.status !== 429) attempt.current = null;
    },
    retry: false,
  });
}
