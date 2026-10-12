# Support and end-of-life policy (DRAFT for founder adoption)

Status: **draft**. It becomes a policy only when the maintainer adopts it. It is written to match current practice
(`SECURITY.md`: one active line, fixes on the latest release).

* **Scope of support:** the latest minor release of `rai-governance-platform` receives security fixes and
  correctness fixes. Python 3.11 and 3.12 are supported; other interpreters are not.
* **Older releases:** critical security fixes only, at the maintainer's discretion, for **90 days after the next
  minor release**, then end of life. After end of life no security update is issued; users are told to upgrade.
* **Announcement:** a release that ends support for an earlier line says so in `CHANGELOG.md` and in the GitHub
  release notes, and a security advisory names the affected and fixed versions.
* **Experimental modules** (`docs/EXPERIMENTAL_MODULES.md`) carry no stability or support commitment.
* **Hosted service:** no availability or support commitment exists in this repository; none may be implied.
