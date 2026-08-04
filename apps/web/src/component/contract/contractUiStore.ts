import { useSyncExternalStore } from "react";
import type { ClauseView } from "./types";

export type ClauseDecisionState = "accepted" | "overridden";

interface ContractUiState {
  clauses: ClauseView[];
  selectedClauseId: string | null;
  decisionStates: Record<string, ClauseDecisionState>;
  contextKey: string;
}

const listeners = new Set<() => void>();

let state: ContractUiState = {
  clauses: [],
  selectedClauseId: null,
  decisionStates: {},
  contextKey: "",
};

function emit() {
  for (const listener of listeners) listener();
}

function buildContextKey(clauses: ClauseView[], selectedClauseId: string | null) {
  return `${selectedClauseId ?? ""}::${clauses
    .map((clause) => `${clause.id}:${clause.accepted ? 1 : 0}:${clause.riskLevel}`)
    .join("|")}`;
}

function pruneDecisionStates(clauses: ClauseView[], decisionStates: Record<string, ClauseDecisionState>) {
  const clauseIds = new Set(clauses.map((clause) => clause.id));
  const nextDecisionStates: Record<string, ClauseDecisionState> = {};

  for (const [clauseId, decisionState] of Object.entries(decisionStates)) {
    if (clauseIds.has(clauseId)) {
      nextDecisionStates[clauseId] = decisionState;
    }
  }

  return nextDecisionStates;
}

export function setContractContext(clauses: ClauseView[], selectedClauseId: string | null) {
  const normalizedSelectedClauseId = selectedClauseId ?? null;
  const contextKey = buildContextKey(clauses, normalizedSelectedClauseId);

  if (state.contextKey === contextKey) return;

  state = {
    clauses: [...clauses],
    selectedClauseId: normalizedSelectedClauseId,
    decisionStates: pruneDecisionStates(clauses, state.decisionStates),
    contextKey,
  };
  emit();
}

export function setSelectedClauseId(selectedClauseId: string | null) {
  if (state.selectedClauseId === selectedClauseId) return;
  state = {
    ...state,
    selectedClauseId,
    contextKey: buildContextKey(state.clauses, selectedClauseId),
  };
  emit();
}

export function setClauseDecisionState(clauseId: string, decisionState: ClauseDecisionState | null) {
  const current = state.decisionStates[clauseId] ?? null;
  if (current === decisionState) return;

  const nextDecisionStates = { ...state.decisionStates };
  if (decisionState) {
    nextDecisionStates[clauseId] = decisionState;
  } else {
    delete nextDecisionStates[clauseId];
  }

  state = {
    ...state,
    decisionStates: nextDecisionStates,
  };
  emit();
}

export function useContractUiState() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
    () => state
  );
}
