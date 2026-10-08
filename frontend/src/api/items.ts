/** 组 B。 */

import { newRequestId, request } from "./client";
import type { Category, Color, Item, ItemCreate, ItemPatch } from "./types";

export function createItem(payload: ItemCreate): Promise<Item> {
  return request<Item>("/items", {
    method: "POST",
    body: { ...payload, request_id: payload.request_id ?? newRequestId() },
  });
}

export function updateItem(id: string, version: number, patch: ItemPatch): Promise<Item> {
  return request<Item>(`/items/${id}`, {
    method: "PATCH",
    body: { ...patch, version, request_id: newRequestId() },
  });
}

export function publishItem(id: string, version: number): Promise<Item> {
  return request<Item>(`/items/${id}/publish`, {
    method: "POST",
    body: { version, request_id: newRequestId() },
  });
}

export function confirmTags(
  id: string,
  version: number,
  category: Category,
  color: Color,
): Promise<Item> {
  return updateItem(id, version, { category, color, confirm_tags: true });
}
