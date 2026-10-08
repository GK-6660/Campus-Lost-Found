/** 组 B。每 2 秒拉一次，直到 succeeded 或 failed。 */

import { request } from "./client";
import type { Job } from "./types";

const POLL_INTERVAL_MS = 2000;

export async function pollJob(jobId: string): Promise<Job> {
  for (;;) {
    const job = await request<Job>(`/jobs/${jobId}`);
    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
