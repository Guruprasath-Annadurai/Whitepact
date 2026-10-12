package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/raiclient"
)

func main() {
	base := "http://127.0.0.1:19595"
	key := os.Getenv("WHITEPACT_API_KEY")
	if len(os.Args) > 1 {
		base = os.Args[1]
	}
	if len(os.Args) > 2 {
		if os.Args[2] != "--analytics" {
			fmt.Fprintln(os.Stderr, "Use WHITEPACT_API_KEY privately; credentials are not accepted as command arguments")
			os.Exit(2)
		}
	}
	c := raiclient.New(raiclient.Options{APIKey: key, BaseURL: base, Timeout: 5 * time.Second})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	h, err := c.Health(ctx)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if len(os.Args) > 2 {
		scan, scanErr := c.Scan(ctx, "Email demo@example.com")
		analysis, analysisErr := c.AnalyzeHallucination(ctx, "Local demonstration text", nil)
		if scanErr != nil || analysisErr != nil {
			fmt.Fprintln(os.Stderr, "Analytics request failed; no confirmed result")
			os.Exit(1)
		}
		_ = json.NewEncoder(os.Stdout).Encode(map[string]interface{}{
			"health": h.Status, "scan_blocked": scan.IsBlocked,
			"heuristic_risk_level": analysis.RiskLevel,
		})
	} else {
		_ = json.NewEncoder(os.Stdout).Encode(h)
	}
}
