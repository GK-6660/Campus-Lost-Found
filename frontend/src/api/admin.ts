/** 组 D。 */

import { newRequestId, request } from "./client";
import type { Item, ReportList } from "./types";

export function loadReports(): Promise<ReportList> {
  return request<ReportList>("/admin/reports");
}

export function takedown(itemId: string, version: number, reason: string): Promise<Item> {
  return request<Item>(`/admin/items/${itemId}/takedown`, {
    method: "POST",
    body: { version, reason, request_id: newRequestId() },
  });
}
