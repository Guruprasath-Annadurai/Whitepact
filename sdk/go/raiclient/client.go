// Package raiclient provides a Go HTTP client for the ResponsibleAI Governance Platform.
package raiclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const defaultBaseURL = "http://localhost:8765"
const apiVersion = "v1"

// Client is the ResponsibleAI API client.
//
// Example:
//
//	c := raiclient.New(raiclient.Options{APIKey: "rai-xxx", BaseURL: "https://rai.example.com"})
//	score, err := c.Evaluate(ctx, raiclient.EvaluateRequest{
//	    ModelName: "gpt-4o", Provider: "openai", Fairness: 0.85,
//	})
type Client struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// Options configures a new Client.
type Options struct {
	APIKey  string
	BaseURL string
	Timeout time.Duration
}

// New creates a new Client. All fields in Options are optional.
func New(opts Options) *Client {
	base := opts.BaseURL
	if base == "" {
		base = defaultBaseURL
	}
	// Strip trailing slash
	for len(base) > 0 && base[len(base)-1] == '/' {
		base = base[:len(base)-1]
	}
	timeout := opts.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	return &Client{
		baseURL: base,
		apiKey:  opts.APIKey,
		httpClient: &http.Client{Timeout: timeout},
	}
}

func (c *Client) url(path string) string {
	if len(path) > 0 && path[0] == '/' {
		path = path[1:]
	}
	return fmt.Sprintf("%s/api/%s/%s", c.baseURL, apiVersion, path)
}

func (c *Client) do(ctx context.Context, method, path string, body interface{}, out interface{}) error {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("raiclient: marshal request: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.url(path), bodyReader)
	if err != nil {
		return fmt.Errorf("raiclient: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("raiclient: %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("raiclient: %s %s status %d: %s", method, path, resp.StatusCode, string(b))
	}

	if out != nil {
		if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
			return fmt.Errorf("raiclient: decode response: %w", err)
		}
	}
	return nil
}

// ── Trust Scoring ──────────────────────────────────────────────────────────────

// Evaluate computes and records a trust score for a model.
func (c *Client) Evaluate(ctx context.Context, req EvaluateRequest) (*TrustScore, error) {
	if req.UseCase == "" {
		req.UseCase = "general"
	}
	if req.Fairness == 0 {
		req.Fairness = 0.75
	}
	if req.Privacy == 0 {
		req.Privacy = 0.80
	}
	if req.Security == 0 {
		req.Security = 0.70
	}
	if req.Robustness == 0 {
		req.Robustness = 0.75
	}
	if req.Compliance == 0 {
		req.Compliance = 0.80
	}
	if req.Authenticity == 0 {
		req.Authenticity = 0.85
	}
	req.RecordDrift = true

	var out TrustScore
	if err := c.do(ctx, http.MethodPost, "evaluate", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Guardrails ──────────────────────────────────────────────────────────────────

// Scan scans text for PII, toxicity, and policy violations.
func (c *Client) Scan(ctx context.Context, text string) (*GuardrailScan, error) {
	var out GuardrailScan
	if err := c.do(ctx, http.MethodPost, "guardrails/scan", map[string]string{"text": text}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Hallucination ───────────────────────────────────────────────────────────────

// AnalyzeHallucination assesses hallucination risk in a model response.
func (c *Client) AnalyzeHallucination(ctx context.Context, text string, candidates []string) (*HallucinationAnalysis, error) {
	body := map[string]interface{}{"text": text}
	if len(candidates) > 0 {
		body["candidates"] = candidates
	}
	var out HallucinationAnalysis
	if err := c.do(ctx, http.MethodPost, "hallucination/analyze", body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Cost ────────────────────────────────────────────────────────────────────────

// RecordUsage records token usage and returns cost breakdown.
func (c *Client) RecordUsage(ctx context.Context, req RecordUsageRequest) (*CostRecord, error) {
	if req.Team == "" {
		req.Team = "default"
	}
	if req.Application == "" {
		req.Application = "default"
	}
	var out CostRecord
	if err := c.do(ctx, http.MethodPost, "cost/record", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Health ──────────────────────────────────────────────────────────────────────

// Health checks the platform health status.
func (c *Client) Health(ctx context.Context) (*HealthStatus, error) {
	var out HealthStatus
	if err := c.do(ctx, http.MethodGet, "health", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
