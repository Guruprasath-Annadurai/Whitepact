# OpenSSF source licensing evidence

WhitePact is released under the MIT License. The authoritative project license is the repository root `LICENSE`, which identifies **Guruprasath Annadurai** as the 2026 copyright holder.

## Per-file source metadata

Tracked, first-party source files under these roots are required to carry both:

- `Copyright (c) 2026 Guruprasath Annadurai`
- `SPDX-License-Identifier: MIT`

Enforced roots:

- `src/`
- `tests/`
- `scripts/`
- `examples/`

The deterministic checker is `scripts/manage_license_headers.py`.

Run locally:

```bash
python scripts/manage_license_headers.py --check
```

The OpenSSF Policy Guard runs this check in CI so new tracked first-party source files cannot silently omit the required copyright/SPDX metadata.

## Scope boundary

The checker intentionally does not rewrite binary assets, dependency/vendor content, generated files outside the first-party source roots, data files, or documentation merely to increase a compliance count. Those artifacts remain governed by their actual provenance and applicable license information.

This evidence closes the repository-side implementation for the OpenSSF Best Practices Gold `copyright_per_file` and `license_per_file` criteria once the hardening branch has passed final CI and is merged into the authoritative branch.
