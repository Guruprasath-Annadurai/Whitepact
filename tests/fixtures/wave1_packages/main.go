// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
package main

import (
	"context"
	"errors"
	"fmt"

	"github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/raiclient"
)

func main() {
	client := raiclient.New(raiclient.Options{
		BaseURL: "http://example.invalid", APIKey: "local-synthetic-key",
	})
	_, err := client.Health(context.Background())
	if !errors.Is(err, raiclient.ErrInsecureTransport) {
		panic("external consumer accepted insecure bearer transport")
	}
	_, err = client.CallTool(context.Background(), "supported_tool", nil, "qualification")
	if !errors.Is(err, raiclient.ErrInsecureTransport) {
		panic("external governance consumer accepted insecure bearer transport")
	}
	for _, status := range []string{"UNKNOWN", "DENIED", "PENDING", "FAILED"} {
		if (raiclient.GovernanceResponse{"result": map[string]any{}, "status": status}).Completed() {
			panic("external governance consumer completed a non-success outcome")
		}
	}
	fmt.Println("external Go consumer rejects insecure bearer transport")
}
