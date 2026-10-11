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
