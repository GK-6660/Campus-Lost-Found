/** 组 C。 */

import { newRequestId, request } from "./client";
import type { Claim, ClaimResult } from "./types";

export function submitClaim(lostId: string, foundId: string, result: ClaimResult): Promise<Claim> {
  return request<Claim>("/claims", {
    method: "POST",
    body: {
      lost_item_id: lostId,
      found_item_id: foundId,
      result,
      request_id: newRequestId(),
    },
  });
}
