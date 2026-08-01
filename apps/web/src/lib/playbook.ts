import { apiFetch } from "./api";

export type ClauseType =
  | "confidentiality"
  | "indemnification"
  | "limitation_of_liability"
  | "termination"
  | "governing_law"
  | "intellectual_property"
  | "payment_terms"
  | "warranty"
  | "non_compete"
  | "data_protection"
  | "force_majeure"
  | "other";

export type RiskLevel = "low" | "medium" | "high" | "unknown";

export interface PlaybookPosition {
  id: string;
  clause_type: ClauseType;
  title: string;
  preferred_language: string;
  fallback_language: string;
  risk_if_absent: RiskLevel;
  tags: string[];
}

export interface CreatePlaybookPayload {
  id?: string;
  clause_type: ClauseType;
  title: string;
  preferred_language: string;
  fallback_language: string;
  risk_if_absent: RiskLevel;
  tags: string[];
}

export interface UpdatePlaybookPayload {
  clause_type?: ClauseType;
  title?: string;
  preferred_language?: string;
  fallback_language?: string;
  risk_if_absent?: RiskLevel;
  tags?: string[];
}

// Every call here goes out with the bearer token (apiFetch's default). The
// backend's playbook router declares `Depends(get_current_user)` on the router
// itself, so *all six* endpoints need it — the playbook is what the judge
// grounds citations against, so write access to it is write access to every
// verdict. Sending the calls unauthenticated doesn't just fail: apiFetch clears
// the stored token on any 401, so one anonymous read here would sign the user
// out of the whole app.
export async function fetchPlaybookPositions(clauseType?: string): Promise<PlaybookPosition[]> {
  const query = clauseType ? `?clause_type=${encodeURIComponent(clauseType)}` : "";
  return apiFetch<PlaybookPosition[]>(`/playbook${query}`);
}

/** A single scored retrieval result — mirrors `RetrievalHit` in app/schemas.py. */
export interface RetrievalHit {
  position: PlaybookPosition;
  score: number;
  source: "dense" | "hybrid";
}

/**
 * Free-text semantic search over the playbook (the `/playbook/search` debug
 * endpoint). Unlike `fetchPlaybookPositions`, which lists everything, this
 * ranks positions by meaning via the retriever and returns scored hits.
 */
export async function searchPlaybook(q: string, topK = 5): Promise<RetrievalHit[]> {
  const params = new URLSearchParams({ q });
  if (topK) params.set("top_k", String(topK));
  return apiFetch<RetrievalHit[]>(`/playbook/search?${params.toString()}`);
}

export async function getPlaybookPosition(id: string): Promise<PlaybookPosition> {
  return apiFetch<PlaybookPosition>(`/playbook/${encodeURIComponent(id)}`);
}

export async function createPlaybookPosition(payload: CreatePlaybookPayload): Promise<PlaybookPosition> {
  return apiFetch<PlaybookPosition>("/playbook", {
    method: "POST",
    json: payload,
  });
}

export async function updatePlaybookPosition(
  id: string,
  payload: UpdatePlaybookPayload
): Promise<PlaybookPosition> {
  return apiFetch<PlaybookPosition>(`/playbook/${encodeURIComponent(id)}`, {
    method: "PUT",
    json: payload,
  });
}

export async function deletePlaybookPosition(id: string): Promise<void> {
  return apiFetch<void>(`/playbook/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
