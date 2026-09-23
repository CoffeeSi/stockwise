import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import { cookies } from "next/headers";
import { abcXyzQueryOptions, demandSeriesQueryOptions, outliersQueryOptions } from "@/entities/analytics";
import { calculationRunsQueryOptions } from "@/entities/calculation-run";
import { categoriesQueryOptions, supplierOptionsQueryOptions, warehousesQueryOptions } from "@/entities/catalog";
import { AnalyticsPage } from "@/pages-flat/analytics";
import { apiUuidSchema } from "@/shared/api";

export const dynamic = "force-dynamic";

export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) {
  const { run } = await searchParams;
  const parsedRun = apiUuidSchema.safeParse(run);
  const initialRunId = parsedRun.success ? parsedRun.data : null;
  const queryClient = new QueryClient();
  const token = (await cookies()).get("stockwise_access_token")?.value;
  if (token) {
    const init = { headers: { Authorization: `Bearer ${token}` } };
    const latestOptions = calculationRunsQueryOptions({ status: "completed", limit: 20, offset: 0 }, init);
    await Promise.all([
      queryClient.prefetchQuery(latestOptions),
      queryClient.prefetchQuery(supplierOptionsQueryOptions({ active_only: false }, init)),
      queryClient.prefetchQuery(warehousesQueryOptions({ active_only: false }, init)),
      queryClient.prefetchQuery(categoriesQueryOptions({ active_only: false }, init)),
    ]);
    const runId = initialRunId ?? queryClient.getQueryData(latestOptions.queryKey)?.items[0]?.id;
    if (runId) {
      await Promise.all([
        queryClient.prefetchQuery(demandSeriesQueryOptions(runId, { months: 24 }, init)),
        queryClient.prefetchQuery(abcXyzQueryOptions(runId, {}, init)),
        queryClient.prefetchQuery(outliersQueryOptions(runId, { limit: 20, offset: 0 }, init)),
      ]);
    }
  }
  return <HydrationBoundary state={dehydrate(queryClient)}><AnalyticsPage key={initialRunId ?? "latest"} initialRunId={initialRunId} /></HydrationBoundary>;
}
