package raiclient

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func newTestClient(t *testing.T, h http.HandlerFunc, key string) (*Client, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(h) // http://127.0.0.1:port -- loopback, so a key is allowed
	t.Cleanup(srv.Close)
	return New(Options{APIKey: key, BaseURL: srv.URL, Timeout: 2 * time.Second}), srv
}

func TestSendsBearerKeyAndParsesResponse(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer k-123" {
			t.Errorf("Authorization = %q", got)
		}
		if r.URL.Path != "/api/v1/health" {
			t.Errorf("path = %q", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}, "k-123")
	if _, err := c.Health(context.Background()); err != nil {
		t.Fatalf("Health: %v", err)
	}
}

func TestNon2xxIsAnErrorAndBodyIsBounded(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(strings.Repeat("x", 100000)))
	}, "k")
	_, err := c.Health(context.Background())
	if err == nil {
		t.Fatal("expected an error for 403")
	}
	if len(err.Error()) > maxErrorBody+200 {
		t.Fatalf("error message not bounded: %d bytes", len(err.Error()))
	}
}

func TestReflectedCredentialRedactedBeforeErrorTruncation(t *testing.T) {
	for _, size := range []int{24, 260} {
		key := "synthetic-private-key-" + strings.Repeat("K", size)
		for _, prefix := range []int{0, maxErrorBody - 8} {
			c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusForbidden)
				_, _ = w.Write([]byte(strings.Repeat("x", prefix) + r.Header.Get("Authorization")))
			}, key)
			_, err := c.Health(context.Background())
			if err == nil || !strings.Contains(err.Error(), "status 403") {
				t.Fatal("expected status-bearing HTTP error")
			}
			if strings.Contains(err.Error(), key) || strings.Contains(err.Error(), "Bearer s") {
				t.Fatal("configured credential was disclosed")
			}
			if len(err.Error()) > maxErrorBody+200 {
				t.Fatal("redacted error is not bounded")
			}
		}
	}
}

func TestRedirectsAreNotFollowedSoTheKeyCannotLeak(t *testing.T) {
	var hits int32
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		if r.Header.Get("Authorization") != "" {
			t.Errorf("credential leaked to the redirect target")
		}
	}))
	defer other.Close()
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, other.URL+"/steal", http.StatusFound)
	}, "secret")
	if _, err := c.Health(context.Background()); err == nil {
		t.Fatal("a redirect must surface as an error")
	}
	if atomic.LoadInt32(&hits) != 0 {
		t.Fatal("redirect target was contacted")
	}
}

func TestRefusesAPIKeyOverPlainHTTPToRemoteHost(t *testing.T) {
	c := New(Options{APIKey: "secret", BaseURL: "http://rai.example.com"})
	if _, err := c.Health(context.Background()); !errors.Is(err, ErrInsecureTransport) {
		t.Fatalf("want ErrInsecureTransport, got %v", err)
	}
	// https is fine (the request then fails at the network, not at the guard)
	c = New(Options{APIKey: "secret", BaseURL: "https://rai.invalid", Timeout: 200 * time.Millisecond})
	if _, err := c.Health(context.Background()); errors.Is(err, ErrInsecureTransport) {
		t.Fatal("https must not be refused")
	}
	// no key => nothing to protect
	c = New(Options{BaseURL: "http://rai.invalid", Timeout: 200 * time.Millisecond})
	if _, err := c.Health(context.Background()); errors.Is(err, ErrInsecureTransport) {
		t.Fatal("keyless http must not trip the guard")
	}
}

func TestMalformedAndHostileJSONDoNotPanic(t *testing.T) {
	for _, body := range []string{`{`, `null`, `[]`, `{"overall":"NaN"}`, strings.Repeat("[", 5000)} {
		body := body
		c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(body)) }, "")
		_, _ = c.Evaluate(context.Background(), EvaluateRequest{ModelName: "m", Provider: "p"})
	}
}

func TestContextCancellationAndTimeout(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) { time.Sleep(500 * time.Millisecond) }, "")
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	if _, err := c.Health(ctx); err == nil {
		t.Fatal("expected a deadline error")
	}
}

func TestTrailingSlashesAreNormalised(t *testing.T) {
	c := New(Options{BaseURL: "https://x.example.com///"})
	if got := c.url("/health"); got != "https://x.example.com/api/v1/health" {
		t.Fatalf("url = %q", got)
	}
}

func TestNegativeDeadlineFailsBeforeDispatch(t *testing.T) {
	var hits int32
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}, "synthetic")
	c = New(Options{BaseURL: c.baseURL, Timeout: -time.Second})
	if _, err := c.Health(context.Background()); err == nil {
		t.Fatal("negative deadline accepted")
	}
	if atomic.LoadInt32(&hits) != 0 {
		t.Fatal("invalid configuration dispatched")
	}
}

func TestScanRejectsMissingDecision(t *testing.T) {
	for _, body := range []string{`null`, `{}`, `{"is_blocked":null}`, `{"is_blocked":"false"}`} {
		c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(body)) }, "")
		if result, err := c.Scan(context.Background(), "text"); err == nil || result != nil {
			t.Fatal("missing or malformed scan decision became safe result")
		}
	}
}

func TestAnalyticsPathsMatchBackend(t *testing.T) {
	c, _ := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/scan":
			_, _ = w.Write([]byte(`{"is_blocked":false}`))
		case "/api/v1/hallucination":
			_, _ = w.Write([]byte(`{"hallucination_risk":0.1,"risk_level":"LOW"}`))
		default:
			http.NotFound(w, r)
		}
	}, "synthetic")
	if _, err := c.Scan(context.Background(), "text"); err != nil {
		t.Fatal("scan contract mismatch")
	}
	if _, err := c.AnalyzeHallucination(context.Background(), "text", nil); err != nil {
		t.Fatal("hallucination contract mismatch")
	}
}

func TestURLCredentialsAndUnsupportedSchemesFailBeforeDispatch(t *testing.T) {
	for _, base := range []string{"https://user:synthetic-secret@example.com", "ftp://127.0.0.1", "file:///private/test"} {
		c := New(Options{BaseURL: base, APIKey: "synthetic"})
		if _, err := c.Health(context.Background()); !errors.Is(err, ErrInvalidURL) {
			t.Fatal("unsafe URL was not rejected before network dispatch")
		}
	}
}
