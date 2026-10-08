/** 组 B。只上传涂黑后的图。 */

import { newRequestId, request } from "./client";
import type { StoredFile } from "./types";

export async function uploadFile(blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", blob);
  form.append("request_id", newRequestId());
  const saved = await request<StoredFile>("/files", { method: "POST", form });
  return saved.id;
}
