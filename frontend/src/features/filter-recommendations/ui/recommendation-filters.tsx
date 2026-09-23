"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { categoriesQueryOptions, supplierOptionsQueryOptions, warehousesQueryOptions } from "@/entities/catalog";
import type { RunRecommendationFilters } from "@/entities/calculation-run";
import { Button, ErrorMessage, Input } from "@/shared/ui";
import { recommendationFilterFormSchema, type RecommendationFilterForm } from "../model/schema";

const selectClass = "mt-1.5 h-10 w-full rounded-xl border border-border bg-input px-3 text-xs text-foreground disabled:opacity-50";
const empty: RecommendationFilterForm = { search: "", supplier_id: "", warehouse_id: "", category_id: "", urgency: "", status: "", sort_by: "risk_score", direction: "descending" };

export function RecommendationFilters({ initialSearch = "", onApply }: { initialSearch?: string; onApply: (filters: RunRecommendationFilters) => void }) {
  const suppliers = useQuery(supplierOptionsQueryOptions({ active_only: false }));
  const warehouses = useQuery(warehousesQueryOptions({ active_only: false }));
  const categories = useQuery(categoriesQueryOptions({ active_only: false }));
  const { register, handleSubmit, reset, formState: { errors } } = useForm<RecommendationFilterForm>({ resolver: zodResolver(recommendationFilterFormSchema), defaultValues: { ...empty, search: initialSearch } });
  const apply = (values: RecommendationFilterForm) => onApply({
    ...(values.search ? { search: values.search } : {}),
    ...(values.supplier_id ? { supplier_id: values.supplier_id } : {}),
    ...(values.warehouse_id ? { warehouse_id: values.warehouse_id } : {}),
    ...(values.category_id ? { category_id: values.category_id } : {}),
    ...(values.urgency ? { urgency: values.urgency } : {}),
    ...(values.status ? { status: values.status } : {}),
    sort_by: values.sort_by,
    descending: values.direction === "descending",
  });
  const catalogError = suppliers.error ?? warehouses.error ?? categories.error;
  return <div className="space-y-3 rounded-2xl border border-border bg-card p-4">
    <form className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" onSubmit={handleSubmit(apply)}>
      <label className="text-xs text-muted-foreground">Артикул или наименование<Input className="mt-1.5" placeholder="Поиск по всему расчёту" maxLength={120} {...register("search")} />{errors.search && <span role="alert" className="text-destructive">{errors.search.message}</span>}</label>
      <label className="text-xs text-muted-foreground">Поставщик<select className={selectClass} disabled={suppliers.isPending} {...register("supplier_id")}><option value="">Все поставщики</option>{suppliers.data?.map((item) => <option key={item.id} value={item.id}>{item.name}{!item.is_active ? " (неактивен)" : ""}</option>)}</select></label>
      <label className="text-xs text-muted-foreground">Склад<select className={selectClass} disabled={warehouses.isPending} {...register("warehouse_id")}><option value="">Все склады</option>{warehouses.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}{!item.is_active ? " (неактивен)" : ""}</option>)}</select></label>
      <label className="text-xs text-muted-foreground">Категория<select className={selectClass} disabled={categories.isPending} {...register("category_id")}><option value="">Все категории</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="text-xs text-muted-foreground">Срочность<select className={selectClass} {...register("urgency")}><option value="">Любая срочность</option><option value="critical">Критическая</option><option value="high">Высокая</option><option value="medium">Средняя</option><option value="low">Низкая</option></select></label>
      <label className="text-xs text-muted-foreground">Статус<select className={selectClass} {...register("status")}><option value="">Все статусы</option><option value="suggested">Предложено</option><option value="adjusted">Скорректировано</option><option value="accepted">Принято</option><option value="rejected">Отклонено</option><option value="converted_to_order">В заказе</option></select></label>
      <label className="text-xs text-muted-foreground">Сортировка<select className={selectClass} {...register("sort_by")}><option value="risk_score">Риск дефицита</option><option value="recommended_quantity">Рекомендуемое количество</option><option value="created_at">Дата создания</option><option value="urgency">Срочность</option><option value="product_id">Товар</option></select></label>
      <label className="text-xs text-muted-foreground">Порядок<select className={selectClass} {...register("direction")}><option value="descending">По убыванию</option><option value="ascending">По возрастанию</option></select></label>
      <div className="flex flex-wrap gap-2 sm:col-span-2 xl:col-span-4"><Button type="submit" size="sm">Применить фильтры</Button><Button type="button" size="sm" variant="secondary" onClick={() => { reset(empty); apply(empty); }}>Сбросить</Button></div>
      {(errors.supplier_id || errors.warehouse_id || errors.category_id || errors.urgency || errors.status || errors.sort_by || errors.direction) && <p role="alert" className="text-xs text-destructive sm:col-span-2 xl:col-span-4">Выберите значения из доступных списков.</p>}
    </form>
    {catalogError && <ErrorMessage title="Справочники недоступны" error={catalogError} onRetry={() => { void suppliers.refetch(); void warehouses.refetch(); void categories.refetch(); }} />}
  </div>;
}
