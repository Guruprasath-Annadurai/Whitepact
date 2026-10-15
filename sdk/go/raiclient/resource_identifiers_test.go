package raiclient

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
)

func TestInvalidResourceIDsNeverDispatch(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		w.Write([]byte(`{"result":{}}`))
	}))
	defer server.Close()
	client := New(Options{BaseURL: server.URL})
	ops := []func(string) error{
		func(id string) error {
			_, err := client.ResolveApproval(context.Background(), id, ApprovalApproved, "")
			return err
		},
		func(id string) error { _, err := client.ExecuteApproval(context.Background(), id); return err },
		func(id string) error { _, err := client.RevokeDelegation(context.Background(), id, "test"); return err },
		func(id string) error { _, err := client.GetApprovalVotes(context.Background(), id); return err },
		func(id string) error { _, err := client.GetEvidenceAttestation(context.Background(), id); return err },
	}
	for _, id := range []string{"", ".", "..", "../other", "a/b", "a\\b", "a?b", "a#b", "%2e%2e", " a", "a ", "a b", "a\t", "a\n", "a\x00", "a\x7f", "a\u00a0b", "a\u0080b", string([]byte{0xff})} {
		for _, op := range ops {
			if err := op(id); err == nil {
				t.Errorf("invalid resource identifier accepted")
			}
		}
	}
	if requests.Load() != 0 {
		t.Fatalf("sent %d invalid requests", requests.Load())
	}
}
