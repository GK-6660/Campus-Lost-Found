/** 组 A。铃铛用 unread_count。 */

import { request } from "./client";
import type { NotificationList } from "./types";

/**通知类型。 */
export type NotificationType = "new_match" | "found_returned" | "item_taken_down";

/**通知。字段同 schemas.py；types.ts 的 items 是 unknown[]，形状写在这里。 */
export type Notification = {
  id: string;
  type: NotificationType;
  read: boolean;
  lost_item_id: string | null;
  found_item_id: string | null;
  title: string;
  body: string;
  created_at: string;
};

/** 未读数和列表。列表最多 100 条，新的在前。 */
export type NotificationFeed = {
  unread_count: number;
  items: Notification[];
};

export function loadNotifications(): Promise<NotificationFeed> {
  return request<NotificationList>("/notifications").then((list) => ({
    unread_count: list.unread_count,
    items: list.items as Notification[],
  }));
}
