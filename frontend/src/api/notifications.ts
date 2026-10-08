/** 组 A。铃铛用 unread_count。 */

import { request } from "./client";
import type { NotificationList } from "./types";

export function loadNotifications(): Promise<NotificationList> {
  return request<NotificationList>("/notifications");
}
