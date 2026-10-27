// data/liveClient.ts — Communicates with the SC-S4 live comparison API.

import type { LiveCompareRequest, LiveCompareResponse } from "../types/live";

const API_BASE = "/api/v1";

export async function submitLiveQuery(
  request: LiveCompareRequest
): Promise<LiveCompareResponse> {
  const res = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${detail}`);
  }

  return res.json() as Promise<LiveCompareResponse>;
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const res = await fetch("/health", { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
