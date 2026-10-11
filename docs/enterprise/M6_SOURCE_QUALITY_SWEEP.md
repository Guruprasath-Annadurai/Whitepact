# M6 source quality sweep (engineering)

| Category | Action | Status |
|----------|--------|--------|
| License headers | `scripts/manage_license_headers.py --check` | CI OpenSSF |
| Secrets | Gitleaks | CI |
| Dependencies | pip-audit / Dependency Review | CI |
| TODO/FIXME in `src/` | Tracked via defect register for launch blockers | Ongoing |
| Legacy BiasBuster CLI | Intentional compatibility in `pyproject.toml` | Documented in `M6_VERSION_AUDIT.md` |

No broad refactors in M6; launch-critical findings → defect register.
