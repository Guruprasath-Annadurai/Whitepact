# Flight Recorder

`build_flight_recording` reconstructs a stable timeline from canonical evidence via
`build_trace_from_evidence`. Each event records provenance:

- `DATABASE_FACT`
- `DERIVED_FROM_FACTS`
- `MISSING`
- `UNKNOWN`

Stages are not invented when persistence lacks facts.
