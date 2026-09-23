"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, Boxes, ClipboardList, FlaskConical, Search, Truck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { apiHealthQueryOptions, databaseHealthQueryOptions } from "@/entities/system";
import { ImportDataAction } from "@/features/import-data";
import { CalculationRunBadge, RunCalculationAction } from "@/features/run-calculation";
import { inventoryFilterSchema } from "@/features/filter-inventory";
import { useHorizonStore } from "@/features/set-horizon";
import { ThemeToggle } from "@/features/toggle-theme";

const navigation = [
  { href: "/", label: "Рекомендации", icon: ClipboardList },
  { href: "/analytics", label: "Аналитика", icon: BarChart3 },
  { href: "/orders", label: "Заказы", icon: Truck },
  { href: "/sandbox", label: "Песочница", icon: FlaskConical },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const days = useHorizonStore((state) => state.days);
  const setDays = useHorizonStore((state) => state.setDays);
  const api = useQuery(apiHealthQueryOptions());
  const database = useQuery(databaseHealthQueryOptions());
  const apiStatus = api.isPending ? "Проверка API" : api.isSuccess ? "API доступен" : "API недоступен";
  const dbStatus = database.isPending ? "Проверка БД" : database.isSuccess ? "БД доступна" : "БД недоступна";

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = inventoryFilterSchema.safeParse({ search, status: "all", supplier: "all", category: "all" });
    if (result.success) router.push(result.data.search.trim() ? `/?q=${encodeURIComponent(result.data.search.trim())}` : "/");
  }

  return <div className="min-h-screen bg-background lg:flex">
    <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-card p-4 lg:flex">
      <Link href="/" className="flex items-center gap-3 px-2 py-2 font-bold"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Boxes className="h-5 w-5" /></span>StockWise</Link>
      <nav aria-label="Разделы" className="mt-8 space-y-1">{navigation.map((entry) => <Link key={entry.href} href={entry.href} aria-current={pathname === entry.href ? "page" : undefined} className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm ${pathname === entry.href ? "bg-accent font-semibold text-accent-foreground" : "text-muted-foreground hover:bg-card-muted"}`}><entry.icon className="h-4 w-4" />{entry.label}</Link>)}</nav>
      <div className="mt-auto space-y-2 rounded-xl border border-border bg-card-muted p-3 text-xs"><div className="flex items-center gap-2"><Activity className={`h-4 w-4 ${api.isSuccess ? "text-emerald-500" : "text-red-500"}`} />{apiStatus}</div><div className="flex items-center gap-2"><Activity className={`h-4 w-4 ${database.isSuccess ? "text-emerald-500" : "text-red-500"}`} />{dbStatus}</div></div>
    </aside>
    <div className="min-w-0 flex-1">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-3 sm:px-7">
        <Link href="/" className="flex items-center gap-2 font-bold lg:hidden"><Boxes className="h-5 w-5" />StockWise</Link>
        <form onSubmit={submitSearch} className="relative w-full sm:w-60"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input aria-label="Поиск по номенклатуре и артикулу" value={search} onChange={(event) => setSearch(event.target.value)} maxLength={120} placeholder="Поиск SKU" className="h-10 w-full rounded-full border border-border bg-input pl-9 pr-3 text-xs outline-none focus:border-ring" /></form>
        <div className="ml-auto flex flex-wrap items-center gap-2"><CalculationRunBadge /><ImportDataAction /><RunCalculationAction horizonDays={days} /><label htmlFor="horizon" className="sr-only">Горизонт расчёта</label><select id="horizon" value={days} onChange={(event) => setDays(Number(event.target.value))} className="h-10 rounded-full border border-border bg-input px-3 text-xs"><option value={30}>30 дней</option><option value={60}>60 дней</option><option value={90}>90 дней</option></select><ThemeToggle /></div>
        <div className="w-full text-right text-[11px] text-muted-foreground lg:hidden">{apiStatus} · {dbStatus}</div>
      </header>
      <nav aria-label="Разделы на мобильном" className="flex gap-1 overflow-x-auto border-b border-border bg-card px-3 py-2 lg:hidden">{navigation.map((entry) => <Link key={entry.href} href={entry.href} aria-current={pathname === entry.href ? "page" : undefined} className={`shrink-0 rounded-full px-3 py-2 text-xs ${pathname === entry.href ? "bg-accent font-semibold" : "text-muted-foreground"}`}>{entry.label}</Link>)}</nav>
      <main className="mx-auto max-w-[1600px] px-4 py-7 sm:px-7 lg:px-9">{children}</main>
    </div>
  </div>;
}
