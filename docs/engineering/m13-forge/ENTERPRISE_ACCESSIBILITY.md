# Enterprise usability

Dashboard read failures keep a visible alert and Retry action. Workspace changes clear previous content and abort old reads; late transport responses cannot restore abandoned content. Invalid API-key scopes/metadata no longer crash rendering or masquerade as an empty inventory.

Focused DOM regressions exercise these failure states. The existing I2/I3 responsive Chromium wrappers passed: 2 tests, 42 explicit UI fixture checks at 375/768/1280, zero reported axe violations or mutations, 2 legacy-key deprecation warnings, 149.00 seconds. These fixtures are not authenticated customer proof; larger-display and complete interaction inventory remain outstanding. Automated checks cannot establish full WCAG conformance.

New read-only account page is wired into authenticated navigation. DOM keyboard/literal metadata/no-mutation test passes. Complete real-app fixture journey also passes with actual session email, existing password-reset link and zero horizontal overflow checked at **375, 768, 1280 and 1920px** (12 account checks). Broader interaction/long-data coverage remains unfinished; these checks do not establish full conformance or privileged account-management qualification.
