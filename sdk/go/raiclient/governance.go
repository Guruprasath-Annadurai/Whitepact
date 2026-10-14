package raiclient

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

// GovernanceState describes a server response, never a client-issued grant.
type GovernanceState string

const (
	GovernanceSucceeded   GovernanceState = "SUCCEEDED"
	GovernanceDenied      GovernanceState = "DENIED"
	GovernancePending     GovernanceState = "PENDING"
	GovernanceQuarantined GovernanceState = "QUARANTINED"
	GovernanceUnknown     GovernanceState = "UNKNOWN"
	GovernanceFailed      GovernanceState = "FAILED"
)

// GovernanceResponse retains canonical server fields, including evidence IDs.
// No HTTP success or policy availability by itself implies completion.
type GovernanceResponse map[string]any

func (r GovernanceResponse) State() GovernanceState {
	if r == nil {
		return GovernanceFailed
	}
	if r["error"] == "governance_unknown_outcome" || r["reconciliation_required"] == true || r["status"] == "UNKNOWN" || r["outcome_status"] == "UNKNOWN" {
		return GovernanceUnknown
	}
	// Approval execution wraps the original governed result in a result envelope.
	nested, nestedOK := r["result"].(map[string]any)
	nestedState := GovernanceSucceeded
	nestedEnvelope := false
	if nestedOK {
		for _, field := range []string{"result", "error", "status", "outcome_status", "decision", "reconciliation_required", "denied", "requires_approval", "quarantined", "failed", "pending"} {
			if _, exists := nested[field]; exists {
				nestedEnvelope = true
				// Classify each nested envelope only once. Re-evaluating it for
				// both UNKNOWN and completion checks grows exponentially.
				nestedState = GovernanceResponse(nested).State()
				break
			}
		}
		if nestedState == GovernanceUnknown {
			return nestedState
		}
	}
	if r["error"] == "governance_denied" || r["denied"] == true || r["decision"] == "DENY" || r["decision"] == "DENIED" || r["status"] == "DENY" || r["status"] == "DENIED" {
		return GovernanceDenied
	}
	if r["error"] == "governance_approval_required" || r["requires_approval"] == true || r["decision"] == "REQUIRE_APPROVAL" || r["status"] == "PENDING" || r["pending"] == true {
		return GovernancePending
	}
	if r["error"] == "governance_quarantined" || r["quarantined"] == true || r["decision"] == "QUARANTINE" || r["status"] == "QUARANTINE" {
		return GovernanceQuarantined
	}
	if _, ok := r["result"]; !ok {
		return GovernanceFailed
	}
	if _, ok := r["error"]; ok {
		return GovernanceFailed
	}
	for _, field := range []string{"reconciliation_required", "denied", "requires_approval", "quarantined", "failed", "pending", "is_error", "isError"} {
		if value, ok := r[field]; ok && value != false {
			return GovernanceFailed
		}
	}
	if v, ok := r["status"]; ok && v != "SUCCEEDED" {
		return GovernanceFailed
	}
	if v, ok := r["outcome_status"]; ok && v != nil && v != "SUCCEEDED" {
		return GovernanceFailed
	}
	if v, ok := r["decision"]; ok && v != "ALLOW" && v != "ALLOW_WITH_REDACTION" {
		return GovernanceFailed
	}
	if nestedOK {
		if _, exists := nested["error"]; exists {
			if nestedState != GovernanceSucceeded {
				return nestedState
			}
			return GovernanceFailed
		}
		for _, field := range []string{"is_error", "isError"} {
			if value, exists := nested[field]; exists && value != false {
				return GovernanceFailed
			}
		}
		// If a result is itself a governed response, require its completion too.
		if nestedEnvelope {
			return nestedState
		}
	}
	return GovernanceSucceeded
}
func (r GovernanceResponse) Completed() bool { return r.State() == GovernanceSucceeded }

// MutationUncertainError means the server may have received the one-shot mutation.
// Do not retry automatically. Inspect tenant evidence/approval state and reconcile
// with an operator before authorizing another effect. There is no backend
// idempotency guarantee for a fresh tool call or arbitrary mutation retry.
type MutationUncertainError struct{ Cause error }

func (e *MutationUncertainError) Error() string {
	return "raiclient: mutation outcome uncertain; do not retry automatically: " + e.Cause.Error()
}
func (e *MutationUncertainError) Unwrap() error { return e.Cause }

// GovernanceHTTPError exposes status, with a bounded, configured-key-redacted detail.
type GovernanceHTTPError struct {
	StatusCode int
	Detail     string
}

func (e *GovernanceHTTPError) Error() string {
	return fmt.Sprintf("raiclient: governance status %d: %s", e.StatusCode, e.Detail)
}

// governanceRequest is one attempt. It uses the same transport restrictions,
// configured deadline and redirect rejection as the analytics client.
func (c *Client) governanceRequest(ctx context.Context, method, path string, body any) (GovernanceResponse, error) {
	if err := c.checkTransport(); err != nil {
		return nil, err
	}
	var input io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, errors.New("raiclient: invalid governance request")
		}
		input = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, input)
	if err != nil {
		return nil, ErrInvalidURL
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	wrap := func(err error) error {
		if method != http.MethodGet {
			return &MutationUncertainError{Cause: err}
		}
		return err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		// Never reflect request URLs, payloads, credentials or arbitrary transport errors.
		safe := errors.New("raiclient: governance transport failed")
		if errors.Is(err, context.DeadlineExceeded) {
			safe = context.DeadlineExceeded
		} else if errors.Is(err, context.Canceled) {
			safe = context.Canceled
		} else {
			var timeout net.Error
			if errors.As(err, &timeout) && timeout.Timeout() {
				safe = context.DeadlineExceeded
			}
		}
		return nil, wrap(safe)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, int64(maxErrorBody+len(c.apiKey))))
		detail := string(b)
		if c.apiKey != "" {
			detail = strings.ReplaceAll(detail, c.apiKey, "[REDACTED]")
		}
		if len(detail) > maxErrorBody {
			detail = detail[:maxErrorBody]
		}
		he := &GovernanceHTTPError{StatusCode: resp.StatusCode, Detail: detail}
		if resp.StatusCode >= 500 {
			return nil, wrap(he)
		}
		return nil, he
	}
	b, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBody+1))
	if err != nil || len(b) > maxResponseBody {
		return nil, wrap(errors.New("raiclient: governance response incomplete or oversized"))
	}
	var out GovernanceResponse
	if err = json.Unmarshal(b, &out); err != nil || out == nil {
		return nil, wrap(errors.New("raiclient: governance response must be a JSON object"))
	}
	return out, nil
}

// CallTool submits arguments and purpose to server-side governance. It never
// constructs authority, bypasses denial, or creates an execution grant locally.
func (c *Client) CallTool(ctx context.Context, name string, arguments map[string]any, purpose string) (GovernanceResponse, error) {
	if strings.TrimSpace(name) == "" || strings.TrimSpace(purpose) == "" {
		return nil, errors.New("raiclient: tool and purpose required")
	}
	if arguments == nil {
		arguments = map[string]any{}
	}
	return c.governanceRequest(ctx, http.MethodPost, "/api/v1/governance/tools/call", map[string]any{"name": name, "arguments": arguments, "purpose": purpose})
}

func governanceID(id string) (string, error) {
	if id == "" || id == "." || id == ".." || strings.ContainsAny(id, "/?#\\%") {
		return "", errors.New("raiclient: invalid resource identifier")
	}
	return url.PathEscape(id), nil
}
func governanceLimit(limit int) (string, error) {
	if limit < 1 || limit > 200 {
		return "", errors.New("raiclient: limit must be 1..200")
	}
	return strconv.Itoa(limit), nil
}

func (c *Client) GetPolicy(ctx context.Context) (GovernanceResponse, error) {
	return c.governanceRequest(ctx, http.MethodGet, "/api/governance/policy", nil)
}
func (c *Client) ListPendingApprovals(ctx context.Context, limit int) (GovernanceResponse, error) {
	v, e := governanceLimit(limit)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodGet, "/api/governance/approvals?limit="+v, nil)
}
func (c *Client) GetApprovalVotes(ctx context.Context, id string) (GovernanceResponse, error) {
	v, e := governanceID(id)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodGet, "/api/governance/approvals/"+v+"/votes", nil)
}

type ApprovalResolution string

const (
	ApprovalApproved ApprovalResolution = "APPROVED"
	ApprovalDenied   ApprovalResolution = "DENIED"
)

// ResolveApproval records a server-authorized vote; it does not imply execution.
func (c *Client) ResolveApproval(ctx context.Context, id string, outcome ApprovalResolution, notes string) (GovernanceResponse, error) {
	v, e := governanceID(id)
	if e != nil {
		return nil, e
	}
	if outcome != ApprovalApproved && outcome != ApprovalDenied {
		return nil, errors.New("raiclient: invalid approval resolution")
	}
	return c.governanceRequest(ctx, http.MethodPost, "/api/governance/approvals/"+v+"/resolve", map[string]any{"outcome": outcome, "notes": notes})
}

// ExecuteApproval uses server-side resume, fresh authority and durable nonce
// checks. A local approval record or previous ALLOW cannot authorize this call.
func (c *Client) ExecuteApproval(ctx context.Context, id string) (GovernanceResponse, error) {
	v, e := governanceID(id)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodPost, "/api/governance/approvals/"+v+"/execute", map[string]any{})
}
func (c *Client) RevokeDelegation(ctx context.Context, id, reason string) (GovernanceResponse, error) {
	v, e := governanceID(id)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodPost, "/api/governance/delegations/"+v+"/revoke", map[string]any{"reason": reason})
}
func (c *Client) ListGovernanceEvidence(ctx context.Context, limit int) (GovernanceResponse, error) {
	v, e := governanceLimit(limit)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodGet, "/api/governance/evidence?limit="+v, nil)
}
func (c *Client) GetEvidenceAttestation(ctx context.Context, id string) (GovernanceResponse, error) {
	v, e := governanceID(id)
	if e != nil {
		return nil, e
	}
	return c.governanceRequest(ctx, http.MethodGet, "/api/governance/evidence/"+v+"/attestation", nil)
}
