import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import { cookies } from "next/headers";
import { ordersQueryOptions } from "@/entities/order";
import { OrdersPage } from "@/pages-flat/orders";
import { apiUuidSchema } from "@/shared/api";

export const dynamic = "force-dynamic";

export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) {
  const { run } = await searchParams;
  const parsedRun = apiUuidSchema.safeParse(run);
  const initialRunId = parsedRun.success ? parsedRun.data : null;
  const queryClient = new QueryClient();
  const token = (await cookies()).get("stockwise_access_token")?.value;
  if (token) {
    await queryClient.prefetchQuery(ordersQueryOptions({
      ...(initialRunId ? { calculation_run_id: initialRunId } : {}),
      limit: 20,
      offset: 0,
    }, { headers: { Authorization: `Bearer ${token}` } }));
  }
  return <HydrationBoundary state={dehydrate(queryClient)}><OrdersPage key={initialRunId ?? "all"} initialRunId={initialRunId} /></HydrationBoundary>;
}
