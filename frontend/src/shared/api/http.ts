import { z } from "zod";

const DEFAULT_TIMEOUT_MS = 60_000;

const errorResponseSchema = z.object({
  detail: z.union([
    z.string(),
    z.object({
      code: z.string().optional(),
      message: z.string().optional(),
      validation_errors: z.array(z.unknown()).optional(),
      issues: z.array(z.unknown()).optional(),
    }).passthrough(),
  ]).optional(),
  request_id: z.string().optional(),
});

export class ApiError extends Error {
  readonly code: string | undefined;
  readonly requestId: string | undefined;
  readonly validationErrors: readonly unknown[];

  constructor(
    public readonly status: number,
    message: string,
    options: { code?: string; requestId?: string; validationErrors?: readonly unknown[] } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code;
    this.requestId = options.requestId;
    this.validationErrors = options.validationErrors ?? [];
  }
}

function getApiUrl(path: string): string {
  const isBrowser = typeof window !== "undefined";
  // Browser requests must stay same-origin so the Next.js BFF can attach its HttpOnly session.
  const configured = isBrowser
    ? undefined
    : process.env.INTERNAL_API_URL ?? process.env.SERVER_API_URL ?? process.env.NEXT_PUBLIC_API_URL;
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) {
    throw new ApiError(0, `Путь API должен начинаться с /: ${path}`);
  }
  if (!configured) return path;
  try {
    const base = new URL(configured);
    const basePath = base.pathname.replace(/\/(?:api\/v1|api)\/?$/, "").replace(/\/$/, "");
    base.pathname = basePath || "/";
    const url = new URL(path.replace(/^\/+/, ""), `${base.toString().replace(/\/$/, "")}/`);
    if (url.origin !== base.origin) throw new Error("cross-origin API path");
    return url.toString();
  } catch {
    throw new ApiError(0, "Адрес FastAPI имеет неверный формат.");
  }
}

function errorFromBody(status: number, raw: unknown): ApiError {
  const parsed = errorResponseSchema.safeParse(raw);
  const detail = parsed.success ? parsed.data.detail : undefined;
  const requestId = parsed.success ? parsed.data.request_id : undefined;
  const code = typeof detail === "object" && detail !== null ? detail.code : undefined;
  const serverMessage = typeof detail === "string" ? detail : detail?.message;
  const message = status === 401
    ? "Войдите в систему. Логин или пароль неверны, либо сессия истекла."
    : status === 403
    ? typeof detail === "object" && detail !== null && detail.code === "invalid_origin"
      ? "Запрос пришёл с неизвестного адреса. Добавьте адрес StockWise в CORS_ORIGINS в .env и перезапустите Compose."
      : "Недостаточно прав для этой операции."
    : status === 404
      ? "Ресурс не найден (404)."
      : status === 501
        ? "Операция ещё не реализована на сервере (501)."
        : serverMessage || `Ошибка сервера (${status}).`;
  const validationErrors = typeof detail === "object" && detail !== null
    ? detail.validation_errors ?? detail.issues ?? []
    : [];
  const validationSummary = validationErrors.flatMap((issue) => {
    if (typeof issue !== "object" || issue === null) return [];
    if ("missing_columns" in issue && Array.isArray(issue.missing_columns)) {
      const names = issue.missing_columns.filter((name): name is string => typeof name === "string");
      return names.length ? [`Отсутствуют столбцы: ${names.join(", ")}.`] : [];
    }
    if ("row" in issue && typeof issue.row === "number") return [`Ошибка в строке ${issue.row}.`];
    if ("message" in issue && typeof issue.message === "string") return [issue.message];
    return [];
  });
  const fullMessage = validationSummary.length ? `${message} ${validationSummary.join(" ")}` : message;
  return new ApiError(status, fullMessage, { code, requestId, validationErrors });
}

function parseJson(value: string, status: number): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    throw new ApiError(status, "Сервер вернул некорректный JSON.");
  }
}

function parseResponse<T>(raw: unknown, status: number, schema: z.ZodType<T>): T {
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    const field = parsed.error.issues[0]?.path.join(".");
    const message = field
      ? `Ответ сервера не соответствует контракту данных: поле ${field}.`
      : "Ответ сервера не соответствует контракту данных.";
    throw new ApiError(status, message, {
      code: "invalid_response",
      validationErrors: parsed.error.issues,
    });
  }
  return parsed.data;
}

function requestHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function withResponse<T>(
  path: string,
  init: RequestInit | undefined,
  timeoutMs: number,
  read: (response: Response) => Promise<T>,
): Promise<T> {
  const url = getApiUrl(path);
  if (init?.signal?.aborted) throw new ApiError(0, "Запрос отменён.", { code: "request_aborted" });
  const controller = new AbortController();
  const abort = () => controller.abort();
  init?.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, Math.max(30_000, timeoutMs));
  try {
    const response = await fetch(url, {
      ...init,
      headers: requestHeaders(init),
      signal: controller.signal,
      cache: "no-store",
    });
    return await read(response);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (init?.signal?.aborted) throw new ApiError(0, "Запрос отменён.", { code: "request_aborted" });
    if (controller.signal.aborted) throw new ApiError(0, "Превышено время ожидания ответа сервера.", { code: "request_timeout" });
    throw new ApiError(0, "Не удалось подключиться к серверу. Проверьте адрес API и сеть.", { code: "network_error" });
  } finally {
    clearTimeout(timer);
    init?.signal?.removeEventListener("abort", abort);
  }
}

async function assertOk(response: Response): Promise<void> {
  if (response.ok) return;
  if (response.status === 401 && typeof window !== "undefined" && !response.url.includes("/api/auth/")) {
    window.dispatchEvent(new Event("stockwise:unauthorized"));
  }
  const bodyText = await response.text();
  let body: unknown;
  try {
    body = JSON.parse(bodyText) as unknown;
  } catch {
    body = { detail: bodyText || undefined };
  }
  const error = errorFromBody(response.status, body);
  if (!error.requestId) {
    const requestId = response.headers.get("X-Request-ID");
    if (requestId) Object.defineProperty(error, "requestId", { value: requestId, enumerable: true });
  }
  throw error;
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  return withResponse(path, init, timeoutMs, async (response) => {
    await assertOk(response);
    return parseResponse(parseJson(await response.text(), response.status), response.status, schema);
  });
}

export async function apiDownload(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Blob> {
  return withResponse(path, init, timeoutMs, async (response) => {
    await assertOk(response);
    return response.blob();
  });
}

export async function apiDownloadWithFilename(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<{ blob: Blob; filename: string | null }> {
  return withResponse(path, init, timeoutMs, async (response) => {
    await assertOk(response);
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    let filename = encoded ? decodeURIComponent(encoded) : plain ?? null;
    if (filename) filename = filename.replace(/[\\/\0]/g, "").trim() || null;
    return { blob: await response.blob(), filename };
  });
}

export function apiUpload<T>(
  path: string,
  schema: z.ZodType<T>,
  formData: FormData,
  onProgress?: (loaded: number, total: number) => void,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  if (typeof XMLHttpRequest === "undefined") {
    return apiRequest(path, schema, { method: "POST", body: formData }, timeoutMs);
  }

  const url = getApiUrl(path);
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.withCredentials = true;
    request.timeout = Math.max(30_000, timeoutMs);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) onProgress?.(event.loaded, event.total);
    });
    request.addEventListener("error", () => reject(new ApiError(0, "Не удалось загрузить файл на сервер.", { code: "network_error" })));
    request.addEventListener("timeout", () => reject(new ApiError(0, "Превышено время ожидания загрузки файла.", { code: "request_timeout" })));
    request.addEventListener("abort", () => reject(new ApiError(0, "Загрузка файла отменена.", { code: "request_aborted" })));
    request.addEventListener("load", () => {
      try {
        if (request.status < 200 || request.status >= 300) {
          let body: unknown;
          try {
            body = JSON.parse(request.responseText) as unknown;
          } catch {
            body = { detail: request.responseText || undefined };
          }
          reject(errorFromBody(request.status, body));
          return;
        }
        const body = parseJson(request.responseText, request.status);
        resolve(parseResponse(body, request.status, schema));
      } catch (error) {
        reject(error);
      }
    });
    request.send(formData);
  });
}
