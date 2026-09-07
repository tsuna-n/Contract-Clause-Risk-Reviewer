import assert from "node:assert/strict";
import { test } from "node:test";
import {
  getContractUiSnapshot,
  setClauseDecisionState,
  setContractContext,
  setSelectedClauseId,
} from "../src/component/contract/contractUiStore.ts";

const clause = (text) => ({ id: "clause-1", text, accepted: false, riskLevel: "HIGH" });

test("reports sharing clause IDs do not share review decisions or text", () => {
  setContractContext("report-a", [clause("First contract")], "clause-1");
  setClauseDecisionState("report-a", "clause-1", "accepted");
  setContractContext("report-b", [clause("Second contract")], "clause-1");

  assert.deepEqual(getContractUiSnapshot().decisionStates, {});
  assert.equal(getContractUiSnapshot().clauses[0].text, "Second contract");

  // The first report's request may finish after navigation.
  setClauseDecisionState("report-a", "clause-1", "overridden");
  assert.deepEqual(getContractUiSnapshot().decisionStates, {});
});

test("updated report content is retained even when risk and selection stay the same", () => {
  setContractContext("report-c", [clause("Original wording")], "clause-1");
  setContractContext("report-c", [clause("Updated wording")], "clause-1");
  assert.equal(getContractUiSnapshot().clauses[0].text, "Updated wording");
});

test("selection changes retain decisions in the same report", () => {
  const clauses = [clause("Same contract")];
  setContractContext("report-d", clauses, null);
  setClauseDecisionState("report-d", "clause-1", "overridden");
  setSelectedClauseId("clause-1");
  setContractContext("report-d", clauses, "clause-1");
  assert.equal(getContractUiSnapshot().decisionStates["clause-1"], "overridden");

  setClauseDecisionState("report-d", "clause-1", null);
  assert.deepEqual(getContractUiSnapshot().decisionStates, {});
});

test("unchanged context keeps a stable snapshot without an extra render", () => {
  const clauses = [clause("Same contract")];
  setContractContext("report-e", clauses, "clause-1");
  const snapshot = getContractUiSnapshot();
  setContractContext("report-e", clauses, "clause-1");
  assert.equal(getContractUiSnapshot(), snapshot);
});
