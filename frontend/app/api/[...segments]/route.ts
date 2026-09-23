import { NextRequest, NextResponse } from "next/server";

function apiOrigin(): string {
  const configured = process.env.INTERNAL_API_URL ?? process.env.SERVER_API_URL ?? "http://localhost:8000";
  const url = new URL(configured);
  url.pathname = url.pathname.replace(/\/(?:api\/v1|api)\/?$/, "").replace(/\/$/, "");
  return url.toString().replace(/\/$/, "");
}

function allowedFrontendOrigins(request: NextRequest): Set<string> {
  const configured = process.env.FRONTEND_ORIGINS ?? "http://localhost:3000,http://127.0.0.1:3000";
  const origins = new Set([request.nextUrl.origin]);
  for (const item of configured.split(",")) {
    try {
      origins.add(new URL(item.trim()).origin);
    } catch {
      // Ignore invalid optional entries; the canonical request origin remains allowed.
    }
  }
  return origins;
}

async function proxy(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const { segments } = await context.params;
  const path = segments.map(encodeURIComponent).join("/");
  if (!["GET", "HEAD"].includes(request.method)) {
    const origin = request.headers.get("origin");
    if (origin && !allowedFrontendOrigins(request).has(origin)) {
      return NextResponse.json({ detail: { code: "invalid_origin", message: "Недопустимый источник запроса." } }, { status: 403 });
    }
  }
  const backendUrl = new URL(`/api/${path}${request.nextUrl.search}`, apiOrigin());
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cookie");
  headers.delete("authorization");
  const token = request.cookies.get("stockwise_access_token")?.value;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl, { method: request.method, headers, body, cache: "no-store", redirect: "manual" });
  } catch {
    return NextResponse.json({ detail: { code: "backend_unavailable", message: "Сервис API временно недоступен." } }, { status: 502 });
  }

  const cookieOptions = { httpOnly: true, sameSite: "lax" as const, secure: request.nextUrl.protocol === "https:", path: "/" };
  if (path === "auth/logout" && (upstream.ok || upstream.status === 401)) {
    const response = NextResponse.json({ success: true });
    response.cookies.set("stockwise_access_token", "", { ...cookieOptions, maxAge: 0 });
    return response;
  }
  if (path === "auth/login" && upstream.ok) {
    let data: unknown;
    try {
      data = await upstream.json();
    } catch {
      return NextResponse.json({ detail: { code: "invalid_session", message: "Некорректный ответ сервера входа." } }, { status: 502 });
    }
    if (typeof data !== "object" || data === null || !("access_token" in data) || typeof data.access_token !== "string" || !("expires_in" in data) || typeof data.expires_in !== "number") {
      return NextResponse.json({ detail: { code: "invalid_session", message: "Некорректный ответ сервера входа." } }, { status: 502 });
    }
    const response = NextResponse.json({ token_type: "bearer", expires_in: data.expires_in });
    response.cookies.set("stockwise_access_token", data.access_token, { ...cookieOptions, maxAge: data.expires_in });
    return response;
  }

  const outgoingHeaders = new Headers();
  for (const name of ["content-type", "content-disposition", "x-request-id", "cache-control", "etag"]) {
    const value = upstream.headers.get(name);
    if (value) outgoingHeaders.set(name, value);
  }
  const response = new NextResponse(upstream.body, { status: upstream.status, headers: outgoingHeaders });
  if (upstream.status === 401) response.cookies.set("stockwise_access_token", "", { ...cookieOptions, maxAge: 0 });
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
