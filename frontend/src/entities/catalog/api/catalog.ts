import { queryOptions } from "@tanstack/react-query";
import { apiRequest } from "@/shared/api";
import { catalogFiltersSchema, categoryListSchema, supplierFiltersSchema, supplierPageSchema, warehouseListSchema, type CatalogFilters, type CatalogItem, type SupplierFilters } from "../model/schema";

export const catalogKeys = {
  all: ["catalog"] as const,
  suppliers: (filters: SupplierFilters) => [...catalogKeys.all, "suppliers", filters] as const,
  supplierOptions: (filters: CatalogFilters) => [...catalogKeys.all, "supplier-options", filters] as const,
  warehouses: (filters: CatalogFilters) => [...catalogKeys.all, "warehouses", filters] as const,
  categories: (filters: CatalogFilters) => [...catalogKeys.all, "categories", filters] as const,
};

function queryString(filters: CatalogFilters | SupplierFilters): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value !== undefined) search.set(key, String(value));
  return search.size ? `?${search}` : "";
}

export function suppliersQueryOptions(input: SupplierFilters = {}, init?: RequestInit) {
  const filters = supplierFiltersSchema.parse(input);
  return queryOptions({
    queryKey: catalogKeys.suppliers(filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/suppliers${queryString(filters)}`, supplierPageSchema, { ...init, signal }),
    retry: false,
  });
}

export function supplierOptionsQueryOptions(input: CatalogFilters = {}, init?: RequestInit) {
  const filters = catalogFiltersSchema.parse(input);
  return queryOptions({
    queryKey: catalogKeys.supplierOptions(filters),
    queryFn: async ({ signal }) => {
      const items: CatalogItem[] = [];
      let offset = 0;
      while (true) {
        const page = await apiRequest(`/api/v1/suppliers${queryString({ ...filters, limit: 100, offset })}`, supplierPageSchema, { ...init, signal });
        items.push(...page.items);
        offset += page.items.length;
        if (offset >= page.total) return items;
        if (page.items.length === 0) throw new Error("Справочник поставщиков вернул неполную страницу. Обновите список.");
      }
    },
    retry: false,
  });
}

export function warehousesQueryOptions(input: CatalogFilters = {}, init?: RequestInit) {
  const filters = catalogFiltersSchema.parse(input);
  return queryOptions({
    queryKey: catalogKeys.warehouses(filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/warehouses${queryString(filters)}`, warehouseListSchema, { ...init, signal }),
    retry: false,
  });
}

export function categoriesQueryOptions(input: CatalogFilters = {}, init?: RequestInit) {
  const filters = catalogFiltersSchema.parse(input);
  return queryOptions({
    queryKey: catalogKeys.categories(filters),
    queryFn: ({ signal }) => apiRequest(`/api/v1/categories${queryString(filters)}`, categoryListSchema, { ...init, signal }),
    retry: false,
  });
}
