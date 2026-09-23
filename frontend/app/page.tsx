import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import { calculationRunQueryOptions, runRecommendationsQueryOptions } from "@/entities/calculation-run";
import { InventoryPage } from "@/pages-flat/inventory";
import { apiUuidSchema } from "@/shared/api";

export const dynamic = "force-dynamic";

export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) {
  const queryClient = new QueryClient();
  const { run } = await searchParams;
  const validRun = apiUuidSchema.safeParse(run);
  await Promise.all([
    ...(validRun.success ? [
      queryClient.prefetchQuery(calculationRunQueryOptions(validRun.data)),
      queryClient.prefetchQuery(runRecommendationsQueryOptions(validRun.data, { limit: 50, offset: 0 })),
    ] : []),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <InventoryPage initialRunId={validRun.success ? validRun.data : null} />
    </HydrationBoundary>
  );
}
