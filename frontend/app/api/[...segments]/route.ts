import { NextRequest, NextResponse } from "next/server";

function apiOrigin(): string {
  const configured = process.env.INTERNAL_API_URL ?? process.env.SERVER_API_URL ?? "http://localhost:8000";
  const url = new URL(configured);
  url.pathname = url.pathname.replace(/\/(?:api\/v1|api)\/?$/, "").replace(/\/$/, "");
  return url.toString().replace(/\/$/, "");
}

async function proxy(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const { segments } = await context.params;
  const path = segments.map(encodeURIComponent).join("/");
  const backendUrl = new URL(`/api/${path}${request.nextUrl.search}`, apiOrigin());
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cookie");
  headers.delete("authorization");

  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl, { method: request.method, headers, body, cache: "no-store", redirect: "manual" });
  } catch {
    return NextResponse.json({ detail: { code: "backend_unavailable", message: "Сервис API временно недоступен." } }, { status: 502 });
  }

  const outgoingHeaders = new Headers();
  for (const name of ["content-type", "content-disposition", "x-request-id", "cache-control", "etag"]) {
    const value = upstream.headers.get(name);
    if (value) outgoingHeaders.set(name, value);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: outgoingHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
