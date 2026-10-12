package raiclient

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestGovernanceOutcomeContract(t *testing.T) {
	cases := []struct {
		body string
		want GovernanceState
	}{
		{`{"result":{},"outcome_status":"SUCCEEDED"}`, GovernanceSucceeded},
		{`{"result":null,"outcome_status":null}`, GovernanceSucceeded},
		{`{"result":42}`, GovernanceSucceeded},
		{`{"error":"governance_unknown_outcome"}`, GovernanceUnknown},
		{`{"result":{},"outcome_status":"UNKNOWN"}`, GovernanceUnknown},
		{`{"result":{},"reconciliation_required":true}`, GovernanceUnknown},
		{`{"error":"governance_denied"}`, GovernanceDenied},
		{`{"result":{},"decision":"DENY"}`, GovernanceDenied},
		{`{"result":{},"status":"DENIED"}`, GovernanceDenied},
		{`{"error":"governance_approval_required","approval_id":"a"}`, GovernancePending},
		{`{"result":{},"decision":"REQUIRE_APPROVAL"}`, GovernancePending},
		{`{"result":{},"status":"PENDING"}`, GovernancePending},
		{`{"result":{},"decision":"QUARANTINE"}`, GovernanceQuarantined},
		{`{"error":"governance_quarantined"}`, GovernanceQuarantined},
		{`{"result":{},"status":"FAILED"}`, GovernanceFailed},
		{`{"result":{},"error":null}`, GovernanceFailed},
		{`{"result":{},"pending":"false"}`, GovernanceFailed},
		{`{"result":{},"status":"FUTURE_STATE"}`, GovernanceFailed},
		{`{"result":{"error":"governance_unknown_outcome"},"approval_id":"a"}`, GovernanceUnknown},
		{`{"result":{"isError":true}}`, GovernanceFailed},
		{`{"result":{"decision":"DENY"}}`, GovernanceDenied},
		{`{"result":{"status":"PENDING"}}`, GovernancePending},
		{`{"approval_id":"a","result":{"result":{},"error":null}}`, GovernanceFailed},
		{`{"approval_id":"a","result":{"result":{},"error":false}}`, GovernanceFailed},
		{`{"approval_id":"a","result":{"result":{},"error":""}}`, GovernanceFailed},
		{`{"result":{"result":{"isError":true}}}`, GovernanceFailed},
		{`{}`, GovernanceFailed}, {`null`, GovernanceFailed}, {`[]`, GovernanceFailed},
	}
	for _, tc := range cases {
		t.Run(tc.body, func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(tc.body)) }))
			defer s.Close()
			out, err := New(Options{BaseURL: s.URL}).CallTool(context.Background(), "test", nil, "test")
			if tc.body == `null` || tc.body == `[]` {
				if err == nil {
					t.Fatal("non-object accepted")
				}
				return
			}
			if err != nil || out.State() != tc.want || out.Completed() != (tc.want == GovernanceSucceeded) {
				t.Fatalf("out=%v err=%v want=%s", out, err, tc.want)
			}
		})
	}
}

func TestGovernanceRoutesAndTenantAuthority(t *testing.T) {
	var calls []string
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls = append(calls, r.Method+" "+r.URL.RequestURI())
		if r.Header.Get("Authorization") != "Bearer local-test" {
			t.Error("missing bearer")
		}
		if r.Method == "POST" {
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Error(err)
			}
			if _, ok := body["organization_id"]; ok {
				t.Error("tenant supplied")
			}
			if r.URL.Path == "/api/v1/governance/tools/call" && (body["name"] != "tool" || body["purpose"] != "testing") {
				t.Error(body)
			}
		}
		w.Write([]byte(`{"result":{},"pending":[],"rules":[]}`))
	}))
	defer s.Close()
	c := New(Options{APIKey: "local-test", BaseURL: s.URL})
	ctx := context.Background()
	_, e := c.CallTool(ctx, "tool", map[string]any{"x": 1}, "testing")
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.GetPolicy(ctx)
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.ListPendingApprovals(ctx, 50)
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.GetApprovalVotes(ctx, "a")
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.ResolveApproval(ctx, "a", ApprovalApproved, "note")
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.ExecuteApproval(ctx, "a")
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.RevokeDelegation(ctx, "d", "reason")
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.ListGovernanceEvidence(ctx, 10)
	if e != nil {
		t.Fatal(e)
	}
	_, e = c.GetEvidenceAttestation(ctx, "e")
	if e != nil {
		t.Fatal(e)
	}
	want := []string{"POST /api/v1/governance/tools/call", "GET /api/governance/policy", "GET /api/governance/approvals?limit=50", "GET /api/governance/approvals/a/votes", "POST /api/governance/approvals/a/resolve", "POST /api/governance/approvals/a/execute", "POST /api/governance/delegations/d/revoke", "GET /api/governance/evidence?limit=10", "GET /api/governance/evidence/e/attestation"}
	if strings.Join(calls, "\n") != strings.Join(want, "\n") {
		t.Fatal(calls)
	}
	before := len(calls)
	for _, id := range []string{"", "../other", "a/b", "a?x=1", "a#fragment"} {
		if _, err := c.ExecuteApproval(ctx, id); err == nil {
			t.Errorf("accepted id %q", id)
		}
	}
	if _, err := c.ResolveApproval(ctx, "a", ApprovalResolution("ALLOW"), ""); err == nil {
		t.Error("bad vote")
	}
	if _, err := c.ListPendingApprovals(ctx, 201); err == nil {
		t.Error("bad limit")
	}
	if len(calls) != before {
		t.Fatal("invalid request transmitted")
	}
}

func TestGovernanceMutationTimeoutIsUncertainAndOneShot(t *testing.T) {
	calls := make(chan struct{}, 2)
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls <- struct{}{}
		time.Sleep(80 * time.Millisecond)
		w.Write([]byte(`{"result":{}}`))
	}))
	defer s.Close()
	_, err := New(Options{BaseURL: s.URL, Timeout: 10 * time.Millisecond}).CallTool(context.Background(), "tool", nil, "test")
	var uncertainty *MutationUncertainError
	if !errors.As(err, &uncertainty) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("%T %v", err, err)
	}
	if len(calls) != 1 {
		t.Fatal("mutation retried")
	}
}

func TestGovernanceRedirectErrorsAndMalformed(t *testing.T) {
	for _, status := range []int{302, 401, 403, 409, 500, 503} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			count := 0
			key := "local-secret"
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				count++
				w.Header().Set("Location", "/second")
				w.WriteHeader(status)
				w.Write([]byte(key))
			}))
			defer s.Close()
			_, err := New(Options{BaseURL: s.URL, APIKey: key}).ExecuteApproval(context.Background(), "a")
			var he *GovernanceHTTPError
			if !errors.As(err, &he) || he.StatusCode != status || strings.Contains(err.Error(), key) || count != 1 {
				t.Fatalf("%v count=%d", err, count)
			}
			var uncertain *MutationUncertainError
			if (status >= 500) != errors.As(err, &uncertain) {
				t.Fatalf("uncertain=%v", err)
			}
		})
	}
	for _, body := range []string{`{"result":{}} trailing`, `{"result":{}} {}`, `null`, `[]`, `{"result":`} {
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(body)) }))
		_, err := New(Options{BaseURL: s.URL}).ExecuteApproval(context.Background(), "a")
		s.Close()
		var uncertainty *MutationUncertainError
		if !errors.As(err, &uncertainty) {
			t.Fatalf("malformed mutation not uncertain: %q %v", body, err)
		}
	}
}

func TestGovernanceDeadlineCoversResponseBody(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		w.(http.Flusher).Flush()
		time.Sleep(80 * time.Millisecond)
		_, _ = w.Write([]byte(`{"result":{}}`))
	}))
	defer s.Close()
	_, err := New(Options{BaseURL: s.URL, Timeout: 10 * time.Millisecond}).ExecuteApproval(context.Background(), "a")
	var uncertain *MutationUncertainError
	if !errors.As(err, &uncertain) {
		t.Fatalf("body deadline must be uncertain: %v", err)
	}
}

func TestGovernanceRejectsInsecureTransportBeforeMutation(t *testing.T) {
	_, err := New(Options{BaseURL: "http://example.com", APIKey: "never-transmit"}).CallTool(context.Background(), "tool", nil, "test")
	if !errors.Is(err, ErrInsecureTransport) {
		t.Fatal(err)
	}
}
