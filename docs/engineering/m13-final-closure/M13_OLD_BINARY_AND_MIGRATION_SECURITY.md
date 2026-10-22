# M13 old-binary and migration security — OPEN

Qualified baseline migration head:0065. This unqualified engineering candidate
proposes0066 (parent0065) for the independent pre-create containment association.
Its FK restricts organization deletion; no automatic evidence deletion is added.
Downgrade refuses any journal rows, including terminal evidence.

Fresh PostgreSQL16 upgrade, downgrade behavior, concurrent transitions, actual old
binary and credential retirement require fresh evidence. The old-binary experiment
in stash12b87ea5 remains preserved; it is not silently merged or represented PASS.

An old binary that ignores the new journal remains dangerous. The supported cutover
must fence execution, stop/independently contain old workers, revoke/retire their DB
roles, terminate old role sessions, migrate with a separate owner, and issue new
least-privilege runtime credentials before admission qualification. Verify old roles
cannot reconnect/write or resume. A downgrade refusal alone proves none of this.

These are required operator controls, not proof a deployment already performed
them. No production roles were modified, no live cutover occurred, and no historical
0064 security assertion was changed to manufacture compatibility.
