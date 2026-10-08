/** 组 A。所有请求走这里，带 Cookie。path 是 `/auth/me` 这种，前面自动加 `/api/v1`。 */

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  form?: FormData;
};

export function newRequestId(): string {
  return crypto.randomUUID();
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `/api/v1${path}`;
  // 实现时：fetch(url, { credentials: "include", method, body 或 form })，并解析 error.code。
  throw new Error(`Not implemented: api.request ${options.method ?? "GET"} ${url}`);
}
