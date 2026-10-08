/** 组 A。 */

import { newRequestId, request } from "./client";
import type { User } from "./types";

export function loadMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function login(studentNo: string, password: string): Promise<User> {
  return request<User>("/auth/login", {
    method: "POST",
    body: { student_no: studentNo, password, request_id: newRequestId() },
  });
}
