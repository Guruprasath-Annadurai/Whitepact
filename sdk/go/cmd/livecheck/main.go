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
	key := ""
	if len(os.Args) > 1 {
		base = os.Args[1]
	}
	if len(os.Args) > 2 {
		key = os.Args[2]
	}
	c := raiclient.New(raiclient.Options{APIKey: key, BaseURL: base, Timeout: 5 * time.Second})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	h, err := c.Health(ctx)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	_ = json.NewEncoder(os.Stdout).Encode(h)
}
