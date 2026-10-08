/** 组 A。所有请求走这里，带 Cookie。path 是 `/auth/me` 这种，前面自动加 `/api/v1`。 */

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  form?: FormData;
};

export function newRequestId(): string {
  return crypto.randomUUID();
}

export type ApiFieldError = {
  name: string;
  code: "required" | "unknown_enum" | "too_long" | "invalid_file";
};

/** 接口错误；网络错误保留 fetch 原始异常，不伪装成服务端错误。 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly current_version?: number;
  readonly fields?: ApiFieldError[];

  constructor(
    status: number,
    code: string,
    message: string,
    details: { current_version?: number; fields?: ApiFieldError[] } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.current_version = details.current_version;
    this.fields = details.fields;
  }
}

/** 统一使用英文提示，不直接展示后端可能返回的中文 message。 */
const errorMessages: Readonly<Record<string, string>> = {
  unauthenticated: "Authentication failed. Please sign in or check your credentials.",
  forbidden: "You do not have permission to perform this action.",
  not_found: "The requested resource was not found.",
  version_conflict: "This item has been updated. Please refresh and try again.",
  found_already_returned: "This found item has already been returned.",
  invalid_state: "This action is not allowed in the current state.",
  validation_error: "Some fields are invalid. Please check your input.",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFieldError(value: unknown): value is ApiFieldError {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    (value.code === "required" ||
      value.code === "unknown_enum" ||
      value.code === "too_long" ||
      value.code === "invalid_file")
  );
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `/api/v1${path}`;
  const method = options.method ?? "GET";
  const hasBody = options.body !== undefined;
  const hasForm = options.form !== undefined;

  if (hasBody && hasForm) {
    throw new TypeError("Cannot provide both body and form.");
  }
  if (method === "GET" && (hasBody || hasForm)) {
    throw new TypeError("GET requests cannot include body or form.");
  }

  const init: RequestInit = { method, credentials: "include" };
  if (hasForm) {
    // 不设置 Content-Type，让浏览器生成 multipart boundary。
    init.body = options.form;
  } else if (hasBody) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    // 代理或服务器故障可能返回 HTML、空响应或不符合约定的 JSON。
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }
    const error = isRecord(payload) && isRecord(payload.error) ? payload.error : undefined;
    const code = typeof error?.code === "string" ? error.code : "http_error";
    const message = Object.hasOwn(errorMessages, code)
      ? errorMessages[code]
      : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(response.status, code, message, {
      current_version:
        typeof error?.current_version === "number" ? error.current_version : undefined,
      fields: Array.isArray(error?.fields) ? error.fields.filter(isFieldError) : undefined,
    });
  }

  // 204 没有响应体，不能调用 json()；这类请求的调用方应使用 request<void>。
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
