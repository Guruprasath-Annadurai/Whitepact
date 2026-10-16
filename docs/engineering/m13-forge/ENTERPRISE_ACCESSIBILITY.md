# Enterprise usability

Dashboard read failures keep a visible alert and Retry action. Workspace changes clear previous content and abort old reads; late transport responses cannot restore abandoned content. Invalid API-key scopes/metadata no longer crash rendering or masquerade as an empty inventory.

Focused DOM regressions exercise these failure states. The existing I2/I3 responsive Chromium wrappers passed: 2 tests, 42 explicit UI fixture checks at 375/768/1280, zero reported axe violations or mutations, 2 legacy-key deprecation warnings, 149.00 seconds. These fixtures are not authenticated customer proof; larger-display and complete interaction inventory remain outstanding. Automated checks cannot establish full WCAG conformance.
