/**
 * Safety API — business verification (Phase 8/9A), shapes verified against
 * apps/safety:
 * - GET /safety/verification/ lazily creates the row as SUBMITTED.
 * - PATCH is the submission act while SUBMITTED (details editable);
 *   UNDER_REVIEW/VERIFIED/REVOKED are locked; REJECTED may resubmit.
 * - evidence is a JSON dict (e.g. {registration_cert: url}).
 * - The two-step admin flow (SUBMITTED -> UNDER_REVIEW -> VERIFIED) is
 *   enforced server-side; the UI only displays status.
 */

import { api } from "./client";
import type { BusinessVerification } from "./types";

export async function getMyVerification(): Promise<BusinessVerification> {
  const { data } = await api.get<BusinessVerification>("/safety/verification/");
  return data;
}

export async function submitVerification(patch: {
  legal_name?: string;
  registration_reference?: string;
  evidence?: Record<string, string>;
}): Promise<BusinessVerification> {
  const { data } = await api.patch<BusinessVerification>("/safety/verification/", patch);
  return data;
}
