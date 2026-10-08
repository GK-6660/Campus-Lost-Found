/** 组 C。 */

import { request } from "./client";
import type { MatchList } from "./types";

export function loadMatches(itemId: string): Promise<MatchList> {
  return request<MatchList>(`/items/${itemId}/matches`);
}
