"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { calculationRunKeys } from "@/entities/calculation-run";
import { approveOrder, createOrders, createSelectedOrders, orderKeys } from "@/entities/order";
import { ApiError } from "@/shared/api";

function useOrderInvalidation() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: orderKeys.all }),
      queryClient.invalidateQueries({ queryKey: calculationRunKeys.all }),
    ]);
  };
}

export function useCreateOrders() {
  const invalidate = useOrderInvalidation();
  return useMutation({
    mutationFn: createOrders,
    onSuccess: invalidate,
    onError: async (error) => { if (error instanceof ApiError && error.status === 409) await invalidate(); },
  });
}

export function useCreateSelectedOrders() {
  const invalidate = useOrderInvalidation();
  return useMutation({
    mutationFn: createSelectedOrders,
    onSuccess: invalidate,
    onError: async (error) => { if (error instanceof ApiError && error.status === 409) await invalidate(); },
  });
}

export function useApproveOrder() {
  const invalidate = useOrderInvalidation();
  return useMutation({
    mutationFn: approveOrder,
    onSuccess: invalidate,
    onError: async (error) => { if (error instanceof ApiError && error.status === 409) await invalidate(); },
  });
}
