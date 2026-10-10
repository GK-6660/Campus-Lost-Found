/** A1：登录及读取当前用户；通过公共请求入口通信，不保存密码或会话令牌。 */

import { newRequestId, request } from "./client";
import type { User } from "./types";

/** 读取服务端认可的当前用户；未登录时由 request 抛出 ApiError，交给页面处理。 */
export function loadMe(): Promise<User> {
  return request<User>("/auth/me");
}

/**
 * 登录成功返回用户，Cookie 由浏览器管理；失败异常交给调用方处理。
 * 默认生成新请求编号。若调用方需要重试，须在首次调用前生成编号并在重试时复用。
 * 修改学号或密码后属于新提交，应生成新编号；此函数不自动重试。
 */
export function login(
  studentNo: string,
  password: string,
  requestId: string = newRequestId(),
): Promise<User> {
  return request<User>("/auth/login", {
    method: "POST",
    body: { student_no: studentNo, password, request_id: requestId },
  });
}
