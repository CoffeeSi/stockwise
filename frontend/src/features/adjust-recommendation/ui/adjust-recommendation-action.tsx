"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, X } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
  calculationRunKeys,
  type RunRecommendationsPage,
} from "@/entities/calculation-run";
import {
  adjustRecommendation,
  recommendationKeys,
  type Recommendation,
} from "@/entities/recommendation";
import { ApiError } from "@/shared/api";
import { Button, Input } from "@/shared/ui";
import { adjustmentFormSchema, type AdjustmentFormValues } from "../model/schema";

type EditableRecommendation = Pick<
  Recommendation,
  "id" | "calculation_run_id" | "effective_quantity" | "version" | "moq" | "package_size" | "status"
>;

type Props = {
  recommendation: EditableRecommendation;
  onSaved?: (updated: Recommendation) => void;
};

type AdjustmentCommand = AdjustmentFormValues & { version: number };

function mutationErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "Рекомендация уже изменена другим пользователем. Список обновляется; откройте форму снова после обновления.";
  }
  return error instanceof Error ? error.message : "Не удалось сохранить корректировку.";
}

export function AdjustRecommendationAction({ recommendation, onSaved }: Props) {
  const quantityId = useId();
  const reasonId = useId();
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const schema = useMemo(
    () => adjustmentFormSchema(recommendation.moq, recommendation.package_size),
    [recommendation.moq, recommendation.package_size],
  );
  const { register, handleSubmit, reset, formState: { errors } } = useForm<AdjustmentFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { new_quantity: recommendation.effective_quantity, reason: "" },
    mode: "onChange",
  });

  const recommendationListKey = [...calculationRunKeys.detail(recommendation.calculation_run_id), "recommendations"] as const;
  const mutation = useMutation({
    mutationFn: ({ new_quantity, reason, version }: AdjustmentCommand) =>
      adjustRecommendation(recommendation.id, { new_quantity, reason, version }),
    onMutate: async ({ new_quantity, version }) => {
      await queryClient.cancelQueries({ queryKey: recommendationListKey });
      const snapshots = queryClient.getQueriesData<RunRecommendationsPage>({ queryKey: recommendationListKey });
      queryClient.setQueriesData<RunRecommendationsPage>({ queryKey: recommendationListKey }, (page) => {
        if (!page) return page;
        return {
          ...page,
          items: page.items.map((item) => item.id === recommendation.id
            ? {
              ...item,
              effective_quantity: new_quantity,
              status: "adjusted" as const,
              version: version + 1,
              updated_at: new Date().toISOString(),
            }
            : item),
        };
      });
      return { snapshots };
    },
    onError: (_error, _variables, context) => {
      for (const [key, page] of context?.snapshots ?? []) {
        queryClient.setQueryData(key, page);
      }
    },
    onSuccess: (updated) => {
      queryClient.setQueriesData<RunRecommendationsPage>({ queryKey: recommendationListKey }, (page) => {
        if (!page) return page;
        return { ...page, items: page.items.map((item) => item.id === updated.id ? { ...item, ...updated } : item) };
      });
      setOpen(false);
      reset({ new_quantity: updated.effective_quantity, reason: "" });
      onSaved?.(updated);
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: recommendationListKey }),
        queryClient.invalidateQueries({ queryKey: recommendationKeys.explanation(recommendation.id) }),
      ]);
    },
  });

  const closed = recommendation.status === "rejected" || recommendation.status === "converted_to_order";
  const invalidTerms = recommendation.moq <= 0 || recommendation.package_size <= 0;

  function startEditing() {
    reset({ new_quantity: recommendation.effective_quantity, reason: "" });
    mutation.reset();
    setOpen(true);
  }

  if (!open) {
    return <Button type="button" size="sm" variant="secondary" onClick={startEditing} disabled={closed || invalidTerms} title={closed ? "Закрытую рекомендацию изменить нельзя" : invalidTerms ? "Условия поставки некорректны" : undefined}>
      <Pencil className="h-3.5 w-3.5" />Изменить
    </Button>;
  }

  return <form
    className="min-w-56 space-y-3 rounded-xl border border-border bg-card p-3"
    noValidate
    onSubmit={handleSubmit((values) => mutation.mutate({ ...values, version: recommendation.version }))}
  >
    <div>
      <label htmlFor={quantityId} className="text-xs font-medium text-foreground">Количество к заказу</label>
      <Input
        id={quantityId}
        type="number"
        min={0}
        step="any"
        inputMode="decimal"
        disabled={mutation.isPending}
        aria-invalid={Boolean(errors.new_quantity)}
        aria-describedby={errors.new_quantity ? `${quantityId}-error` : undefined}
        {...register("new_quantity", { valueAsNumber: true })}
      />
      {errors.new_quantity && <p id={`${quantityId}-error`} role="alert" className="mt-1 text-xs text-destructive">{errors.new_quantity.message}</p>}
      <p className="mt-1 text-xs text-muted-foreground">MOQ: {recommendation.moq}; кратность: {recommendation.package_size}. Для отмены позиции укажите 0.</p>
    </div>
    <div>
      <label htmlFor={reasonId} className="text-xs font-medium text-foreground">Причина изменения</label>
      <textarea
        id={reasonId}
        rows={2}
        maxLength={2000}
        disabled={mutation.isPending}
        aria-invalid={Boolean(errors.reason)}
        aria-describedby={errors.reason ? `${reasonId}-error` : undefined}
        className="mt-1 w-full resize-y rounded-xl border border-border bg-input px-3 py-2 text-sm text-foreground outline-none focus:border-ring focus:ring-1 focus:ring-ring"
        {...register("reason")}
      />
      {errors.reason && <p id={`${reasonId}-error`} role="alert" className="mt-1 text-xs text-destructive">{errors.reason.message}</p>}
    </div>
    {mutation.isError && <p role="alert" className="text-xs text-destructive">{mutationErrorMessage(mutation.error)}</p>}
    <div className="flex flex-wrap gap-2">
      <Button type="submit" size="sm" disabled={mutation.isPending}><Check className="h-3.5 w-3.5" />{mutation.isPending ? "Сохраняем…" : "Сохранить"}</Button>
      <Button type="button" size="sm" variant="ghost" disabled={mutation.isPending} onClick={() => setOpen(false)}><X className="h-3.5 w-3.5" />Отмена</Button>
    </div>
  </form>;
}
