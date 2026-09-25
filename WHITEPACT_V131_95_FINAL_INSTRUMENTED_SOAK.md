# Phase 0C — LOCAL INSTRUMENTED SOAK

Duration: **1800s** | Workers: **4** | DB: PostgreSQL | Redis: `redis://127.0.0.1:6379/0`

| requests | errors | p95 ms |
|---:|---:|---:|
| 11517 | 0 | 7.60 |

**Leak assessment:** NO SIGNIFICANT LEAK OBSERVED DURING 30-MIN LOCAL SOAK

RSS kb (start→end): 908124 → 936960

Open FDs (start→end): 0 → 0

## Sample points (25% quartiles)

```json
[
  {
    "t": 0.3,
    "server": {
      "pids": [
        668644,
        668653,
        668655,
        668656,
        668657,
        668658
      ],
      "rss_kb_total": 908124,
      "threads_total": 14,
      "open_fds_total": 0
    },
    "db_active": 1,
    "db_idle": 4,
    "redis_connected_clients": 2
  },
  {
    "t": 450.0,
    "server": {
      "pids": [
        668644,
        668653,
        668655,
        668656,
        668657,
        668658
      ],
      "rss_kb_total": 935852,
      "threads_total": 14,
      "open_fds_total": 0
    },
    "db_active": 1,
    "db_idle": 5,
    "redis_connected_clients": 1
  },
  {
    "t": 900.1,
    "server": {
      "pids": [
        668644,
        668653,
        668655,
        668656,
        668657,
        668658
      ],
      "rss_kb_total": 936744,
      "threads_total": 14,
      "open_fds_total": 0
    },
    "db_active": 1,
    "db_idle": 5,
    "redis_connected_clients": 1
  },
  {
    "t": 1350.1,
    "server": {
      "pids": [
        668644,
        668653,
        668655,
        668656,
        668657,
        668658
      ],
      "rss_kb_total": 936960,
      "threads_total": 14,
      "open_fds_total": 0
    },
    "db_active": 1,
    "db_idle": 6,
    "redis_connected_clients": 1
  },
  {
    "t": 1755.1,
    "server": {
      "pids": [
        668644,
        668653,
        668655,
        668656,
        668657,
        668658
      ],
      "rss_kb_total": 936960,
      "threads_total": 14,
      "open_fds_total": 0
    },
    "db_active": 1,
    "db_idle": 6,
    "redis_connected_clients": 1
  }
]
```
