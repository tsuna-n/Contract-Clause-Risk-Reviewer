import { useSyncExternalStore } from "react";
import type { ClauseView } from "./types";

export type ClauseDecisionState = "accepted" | "overridden";

interface ContractUiState {
  clauses: ClauseView[];
  selectedClauseId: string | null;
  decisionStates: Record<string, ClauseDecisionState>;
  reportId: string | null;
}

const listeners = new Set<() => void>();

let state: ContractUiState = {
  clauses: [],
  selectedClauseId: null,
  decisionStates: {},
  reportId: null,
};

function emit() {
  for (const listener of listeners) listener();
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

export function setContractContext(
  reportId: string,
  clauses: ClauseView[],
  selectedClauseId: string | null
) {
  const normalizedSelectedClauseId = selectedClauseId ?? null;

  if (
    state.reportId === reportId && state.clauses === clauses &&
    state.selectedClauseId === normalizedSelectedClauseId
  ) return;

  state = {
    clauses,
    selectedClauseId: normalizedSelectedClauseId,
    decisionStates: state.reportId === reportId
      ? pruneDecisionStates(clauses, state.decisionStates) : {},
    reportId,
  };
  emit();
}

export function setSelectedClauseId(selectedClauseId: string | null) {
  if (state.selectedClauseId === selectedClauseId) return;
  state = {
    ...state,
    selectedClauseId,
  };
  emit();
}

export function setClauseDecisionState(
  reportId: string,
  clauseId: string,
  decisionState: ClauseDecisionState | null
) {
  // A mutation from a report we already left must not update the next one.
  if (state.reportId !== reportId) return;
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

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getContractUiSnapshot() {
  return state;
}

export function useContractUiState() {
  return useSyncExternalStore(subscribe, getContractUiSnapshot, getContractUiSnapshot);
}
