// governancecheck exercises the SDK against an explicitly selected local test
// server. Credentials are environment-only and results are deliberately minimal.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/raiclient"
	"os"
	"time"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: governancecheck URL operation")
		os.Exit(2)
	}
	var input struct {
		Name      string
		Purpose   string
		Arguments map[string]any
		ID        string
		Outcome   raiclient.ApprovalResolution
	}
	if err := json.NewDecoder(os.Stdin).Decode(&input); err != nil {
		fmt.Fprintln(os.Stderr, "invalid input")
		os.Exit(2)
	}
	c := raiclient.New(raiclient.Options{BaseURL: os.Args[1], APIKey: os.Getenv("WHITEPACT_API_KEY"), Timeout: 5 * time.Second})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var result raiclient.GovernanceResponse
	var err error
	switch os.Args[2] {
	case "call":
		result, err = c.CallTool(ctx, input.Name, input.Arguments, input.Purpose)
	case "policy":
		result, err = c.GetPolicy(ctx)
	case "pending":
		result, err = c.ListPendingApprovals(ctx, 50)
	case "execute":
		result, err = c.ExecuteApproval(ctx, input.ID)
	case "resolve":
		result, err = c.ResolveApproval(ctx, input.ID, input.Outcome, "local test")
	case "revoke":
		result, err = c.RevokeDelegation(ctx, input.ID, "local test")
	case "evidence":
		result, err = c.ListGovernanceEvidence(ctx, 50)
	default:
		fmt.Fprintln(os.Stderr, "unsupported operation")
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	// Do not print arbitrary tool payloads or bearer credentials.
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"state": result.State(), "completed": result.Completed(), "approval_id": result["approval_id"], "has_pending": result["pending"] != nil, "has_rules": result["rules"] != nil, "has_evidence": result["evidence"] != nil})
}
