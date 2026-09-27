# Actionable Checklist: Owner-Only Actions Required

**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Target:** Repository Owner / Primary Maintainer (`Guruprasath-Annadurai`)  
**Scope:** Actions Requiring GitHub Administrative Privileges, Account 2FA, or External Portal Submissions  
**Date:** 2026-09-28  

---

## 1. Executive Summary

This document provides a concise, step-by-step checklist of all tasks that **cannot be performed by code, automated workflows, or AI agents**. These actions require the repository owner's direct credentials, browser session, or account-level administrative authority.

Completing these actions will finalize the external verification requirements for OpenSSF Best Practices Silver refresh, OpenSSF OSPS Baseline Level 2 public claims, and the Cloud Security Alliance (CSA) STAR Level 1 registry listing.

---

## 2. Action Checklist

### Phase 1: GitHub Account & Organization Security Settings
- [ ] **Action 1.1: Verify & Enforce Account 2FA (`require_2FA`)**
  - **Location:** GitHub Settings $\rightarrow$ Password and authentication.
  - **Requirement:** Ensure Two-Factor Authentication (2FA) is enabled on the maintainer account.
  - **Evidence Needed:** Record confirmation for OpenSSF BadgeApp criterion `require_2FA`.
- [ ] **Action 1.2: Enforce Cryptographic Second Factor (`secure_2FA`)**
  - **Requirement:** Ensure the primary 2FA method utilizes a cryptographic authenticator: a FIDO2/WebAuthn security key (e.g. YubiKey), platform passkey (TouchID/FaceID), or TOTP authenticator app (e.g. Google Authenticator/1Password). SMS-based 2FA should be disabled or demoted.
  - **Evidence Needed:** Satisfies OpenSSF BadgeApp criterion `secure_2FA`.

---

### Phase 2: GitHub Repository Security & Branch Protection Configuration
- [ ] **Action 2.1: Audit & Lock Branch Protection for `main`**
  - **Location:** Repository Settings $\rightarrow$ Branches $\rightarrow$ Branch protection rule for `main`.
  - **Configuration:**
    - [x] Check: `Require a pull request before merging`.
    - [x] Check: `Require status checks to pass before merging`.
    - [x] Select required checks:
      - `Lint, Format, Typecheck & Tests (Python 3.11)`
      - `Lint, Format, Typecheck & Tests (Python 3.12)`
      - `OpenSSF Policy & License Guard`
      - `Dependency Review`
      - `Gitleaks`
      - `CodeQL`
    - [x] Check: `Require linear history`.
    - [x] Check: `Do not allow bypassing the above settings` (or strictly restrict).
    - [x] Check: `Block force pushes` and `Block deletions`.
- [ ] **Action 2.2: Verify GitHub Code Security & Analysis Features**
  - **Location:** Repository Settings $\rightarrow$ Code security and analysis.
  - **Verify Active:**
    - `Private vulnerability reporting` $\rightarrow$ **Enabled**.
    - `Dependency graph` $\rightarrow$ **Enabled**.
    - `Dependabot alerts` $\rightarrow$ **Enabled**.
    - `Dependabot security updates` $\rightarrow$ **Enabled**.
    - `Secret scanning` $\rightarrow$ **Enabled**.
    - `Secret scanning push protection` $\rightarrow$ **Enabled**.

---

### Phase 3: External Portal Submissions & Registry Listings
- [ ] **Action 3.1: Submit CSA STAR Level 1 CAIQ Assessment (Zero-Cost)**
  - **Portal:** `https://cloudsecurityalliance.org/star/registry/submission/`
  - **Steps:**
    1. Log in or create a free Cloud Security Alliance account.
    2. Register WhitePact as an Open Source / Cloud Service provider.
    3. Upload the completed spreadsheet: `compliance/CAIQv4.0.3_WhitePact_completed.xlsx`.
    4. Provide the project repository URL: `https://github.com/Guruprasath-Annadurai/Whitepact`.
    5. Submit for publication on the official public CSA STAR Registry.
- [ ] **Action 3.2: Update OpenSSF Best Practices BadgeApp (Project ID: 14112)**
  - **Portal:** `https://bestpractices.coreinfrastructure.org/en/projects/14112`
  - **Steps:**
    1. Log in via GitHub OAuth.
    2. Update Silver badge evidence with links to updated repository files:
       - `copyright_per_file`: link to `scripts/manage_license_headers.py`.
       - `license_per_file`: link to `docs/compliance/OPENSSF_GOLD_GAP_ANALYSIS.md`.
       - `require_2FA`: mark Met (confirm account 2FA is active).
       - `secure_2FA`: mark Met (confirm cryptographic 2FA is active).
       - `hardened_site`: mark Met with reference to `compliance/HARDENED_SITE_VERIFICATION.md` and `https://whitepact.com`.
    3. Save the entry to ensure the official Silver badge metadata reflects 100% current criteria compliance.
- [ ] **Action 3.3: Self-Attest OSPS Baseline Level 2**
  - **Portal:** OpenSSF OSPS Assessment portal / BadgeApp.
  - **Steps:** Record Level 2 conformance based on the verified evidence in `docs/compliance/OSPS_BASELINE_2026_08_28_EVIDENCE.md`.

---

### Phase 4: Release Key Hygiene
- [ ] **Action 4.1: Maintain Signing Key Access**
  - **Requirement:** Ensure the SSH release signing key (`milchcreamfoods@gmail.com`) listed in `security/release-signers.allowed` is backed up securely and accessible for future production releases (`v1.3.x+`).
