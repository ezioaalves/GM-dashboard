export type ApiErrorPayload = {
  code?: string;
  message: string;
  details?: unknown;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: JsonValue | BodyInit;
};

function isBodyInit(value: JsonValue | BodyInit): value is BodyInit {
  return typeof value === "string" || value instanceof Blob || value instanceof FormData || value instanceof URLSearchParams || value instanceof ArrayBuffer || ArrayBuffer.isView(value) || value instanceof ReadableStream;
}

function errorPayload(status: number, payload: unknown, fallback: string): ApiErrorPayload {
  const value = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  const detail = value.detail;
  const detailObject = detail && typeof detail === "object" && !Array.isArray(detail)
    ? detail as Record<string, unknown>
    : undefined;
  const message = typeof detailObject?.message === "string"
    ? detailObject.message
    : typeof value.message === "string"
      ? value.message
      : typeof detail === "string"
        ? detail
        : fallback;
  return {
    code: typeof detailObject?.code === "string" ? detailObject.code : typeof value.code === "string" ? value.code : undefined,
    message,
    details: detailObject ?? (Array.isArray(detail) ? detail : payload),
  };
}

export async function apiRequest<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  let requestBody: BodyInit | undefined;
  if (body !== undefined) {
    if (isBodyInit(body)) {
      requestBody = body;
    } else {
      requestBody = JSON.stringify(body);
      if (!requestHeaders.has("Content-Type")) requestHeaders.set("Content-Type", "application/json");
    }
  }

  const response = await fetch(url, { ...init, headers: requestHeaders, body: requestBody });
  const text = await response.text();
  let payload: unknown = text;
  if (text) {
    try { payload = JSON.parse(text); } catch { /* non-JSON error bodies remain text */ }
  }
  if (!response.ok) throw new ApiError(response.status, errorPayload(response.status, payload, `HTTP ${response.status}`));
  return (text ? payload : undefined) as T;
}

export const api = {
  get: <T>(url: string, options?: Omit<ApiRequestOptions, "method" | "body">) => apiRequest<T>(url, options),
  post: <T>(url: string, body?: JsonValue | BodyInit, options?: Omit<ApiRequestOptions, "method" | "body">) => apiRequest<T>(url, { ...options, method: "POST", body }),
  put: <T>(url: string, body?: JsonValue | BodyInit, options?: Omit<ApiRequestOptions, "method" | "body">) => apiRequest<T>(url, { ...options, method: "PUT", body }),
  patch: <T>(url: string, body?: JsonValue | BodyInit, options?: Omit<ApiRequestOptions, "method" | "body">) => apiRequest<T>(url, { ...options, method: "PATCH", body }),
  delete: <T>(url: string, options?: Omit<ApiRequestOptions, "method" | "body">) => apiRequest<T>(url, { ...options, method: "DELETE" }),
};
