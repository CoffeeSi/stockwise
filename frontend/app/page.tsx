import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import { cookies } from "next/headers";
import { z } from "zod";
import { calculationRunQueryOptions, calculationRunsQueryOptions, runRecommendationsQueryOptions } from "@/entities/calculation-run";
import { InventoryPage } from "@/pages-flat/inventory";
import { apiUuidSchema } from "@/shared/api";

export const dynamic = "force-dynamic";

export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string; q?: string }> }) {
  const { run, q } = await searchParams;
  const parsedRun = apiUuidSchema.safeParse(run);
  const parsedSearch = z.string().trim().max(120).safeParse(q ?? "");
  const search = parsedSearch.success ? parsedSearch.data : "";
  const queryClient = new QueryClient();
  const token = (await cookies()).get("stockwise_access_token")?.value;
  if (token) {
    const init: RequestInit = { headers: { Authorization: `Bearer ${token}` } };
    const latestOptions = calculationRunsQueryOptions({ status: "completed", limit: 1, offset: 0 }, init);
    await Promise.all([
      queryClient.prefetchQuery(latestOptions),
      queryClient.prefetchQuery(calculationRunsQueryOptions({ limit: 20, offset: 0 }, init)),
    ]);
    const runId = parsedRun.success ? parsedRun.data : queryClient.getQueryData(latestOptions.queryKey)?.items[0]?.id;
    if (runId) {
      const runOptions = calculationRunQueryOptions(runId, init);
      await queryClient.prefetchQuery(runOptions);
      if (queryClient.getQueryData(runOptions.queryKey)?.status === "completed") {
        await queryClient.prefetchQuery(runRecommendationsQueryOptions(runId, { ...(search ? { search } : {}), limit: 50, offset: 0 }, init));
      }
    }
  }
  return <HydrationBoundary state={dehydrate(queryClient)}><InventoryPage initialRunId={parsedRun.success ? parsedRun.data : null} initialSearch={search} /></HydrationBoundary>;
}
