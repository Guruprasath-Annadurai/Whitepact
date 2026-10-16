// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
package raiclient

import "testing"

func TestCanonicalAllowWithRedactionNeedsSuccessfulExecution(t *testing.T) {
	for _, decision := range []string{"ALLOW", "ALLOW_WITH_REDACTION"} {
		if !(GovernanceResponse{"decision": decision, "result": map[string]any{}, "outcome_status": "SUCCEEDED"}).Completed() {
			t.Fatal("completed canonical allowing outcome rejected", decision)
		}
		if (GovernanceResponse{"decision": decision}).Completed() {
			t.Fatal("decision alone became execution", decision)
		}
	}
}
