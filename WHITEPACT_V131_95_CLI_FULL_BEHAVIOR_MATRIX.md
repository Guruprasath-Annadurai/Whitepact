# CLI full behavior matrix (9.5 closure)

Discovered verbs: **41**

| command | test | cwd | exit | crash |
|---|---|---|---:|---|
| `authority compare` | REAL_ATTEMPT | repo-root | 0 | OK |
| `authority diff` | REAL_ATTEMPT | repo-root | 0 | OK |
| `authority drift` | REAL_ATTEMPT | repo-root | 0 | OK |
| `capsule create` | REAL_ATTEMPT | repo-root | 0 | OK |
| `capsule inspect` | REAL_ATTEMPT | repo-root | 0 | OK |
| `capsule reproduce` | REAL_ATTEMPT | repo-root | 0 | OK |
| `capsule validate` | REAL_ATTEMPT | repo-root | 0 | OK |
| `ci` | REAL_ATTEMPT | repo-root | 0 | OK |
| `connect` | REAL_ATTEMPT | repo-root | 0 | OK |
| `context current` | REAL_ATTEMPT | repo-root | 0 | OK |
| `context current` | REAL_ATTEMPT | /tmp | 0 | OK |
| `context current` | REAL_ATTEMPT | home | 0 | OK |
| `context list` | REAL_ATTEMPT | repo-root | 0 | OK |
| `context list` | REAL_ATTEMPT | /tmp | 0 | OK |
| `context list` | REAL_ATTEMPT | home | 0 | OK |
| `context use` | REAL_ATTEMPT | repo-root | 0 | OK |
| `doctor` | REAL_ATTEMPT | repo-root | 0 | OK |
| `doctor` | REAL_ATTEMPT | /tmp | 0 | OK |
| `doctor` | REAL_ATTEMPT | home | 0 | OK |
| `explain` | REAL_ATTEMPT | repo-root | 0 | OK |
| `gauntlet` | REAL_ATTEMPT | repo-root | 0 | OK |
| `init` | REAL_ATTEMPT | repo-root | 0 | OK |
| `list-probes` | REAL_ATTEMPT | repo-root | 0 | OK |
| `list-probes` | REAL_ATTEMPT | /tmp | 0 | OK |
| `list-probes` | REAL_ATTEMPT | home | 0 | OK |
| `policy diff` | REAL_ATTEMPT | repo-root | 0 | OK |
| `policy lint` | REAL_ATTEMPT | repo-root | 0 | OK |
| `policy simulate` | REAL_ATTEMPT | repo-root | 0 | OK |
| `policy test` | REAL_ATTEMPT | repo-root | 0 | OK |
| `policy validate` | REAL_ATTEMPT | repo-root | 0 | OK |
| `prove` | REAL_ATTEMPT | repo-root | 0 | OK |
| `replay` | REAL_ATTEMPT | repo-root | 0 | OK |
| `run` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sandbox` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sandbox` | REAL_ATTEMPT | /tmp | 0 | OK |
| `sandbox` | REAL_ATTEMPT | home | 0 | OK |
| `shadow` | REAL_ATTEMPT | repo-root | 0 | OK |
| `simulate blast-radius` | REAL_ATTEMPT | repo-root | 0 | OK |
| `simulate mission` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sovereign ci` | HELP_ONLY | repo-root | 0 | OK |
| `sovereign doctor` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sovereign gauntlet` | HELP_ONLY | repo-root | 0 | OK |
| `sovereign manifest validate` | HELP_ONLY | repo-root | 0 | OK |
| `sovereign sandbox` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sovereign shadow` | HELP_ONLY | repo-root | 0 | OK |
| `sovereign simulate blast-radius` | HELP_ONLY | repo-root | 0 | OK |
| `sovereign status` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sovereign version` | REAL_ATTEMPT | repo-root | 0 | OK |
| `sovereign xray` | HELP_ONLY | repo-root | 0 | OK |
| `trace` | REAL_ATTEMPT | repo-root | 0 | OK |
| `xray` | REAL_ATTEMPT | repo-root | 0 | OK |
