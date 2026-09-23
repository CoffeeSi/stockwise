import { SandboxPage } from "@/pages-flat/sandbox";
import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import { cookies } from "next/headers";
import { calculationRunsQueryOptions } from "@/entities/calculation-run";

export const dynamic = "force-dynamic";

export default async function Page() {
  const client = new QueryClient();
  const token = (await cookies()).get("stockwise_access_token")?.value;
  if (token) await client.prefetchQuery(calculationRunsQueryOptions({ status: "completed", limit: 100, offset: 0 }, { headers: { Authorization: `Bearer ${token}` } }));
  return <HydrationBoundary state={dehydrate(client)}><SandboxPage /></HydrationBoundary>;
}
