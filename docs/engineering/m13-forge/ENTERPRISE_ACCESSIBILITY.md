# Enterprise usability

Dashboard read failures keep a visible alert and Retry action. Workspace changes clear previous content and abort old reads; late transport responses cannot restore abandoned content. Invalid API-key scopes/metadata no longer crash rendering or masquerade as an empty inventory.

Focused DOM regressions exercise these failure states. Fresh real-browser coverage at 375, 768, 1280 and larger displays remains outstanding for this checkpoint. Automated checks cannot establish full WCAG conformance.
