# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Protected cross-store tenant generation and completion projection.

Existing tenants are deliberately not assigned generations or completion rows.
The controller role has NOLOGIN and no membership is enrolled by migration.
Application and controller database identities must be separated operationally.
"""

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        raise RuntimeError("Cross-store provisioning requires PostgreSQL")
    op.create_table(
        "tenant_provisioning_records",
        sa.Column(
            "tenant_id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column("deployment_id", sa.String(256), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False, unique=True),
        sa.Column("generation_id", sa.String(64), nullable=False, unique=True),
        sa.Column("principal_id", sa.String(36), nullable=False),
        sa.Column("operation_digest", sa.String(64), nullable=False),
        sa.Column("pending_receipt_digest", sa.String(64), nullable=False),
        sa.Column("publication_manifest", sa.Text),
        sa.Column("publication_signature", sa.Text),
        sa.Column("publication_digest", sa.String(64)),
        sa.Column("completion_digest", sa.String(64)),
        sa.Column("security_epoch", sa.BigInteger, nullable=False),
        sa.Column("revocation_floor", sa.BigInteger, nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING','PUBLISHED','COMPLETE')", name="ck_tenant_provisioning_state"
        ),
        sa.CheckConstraint("length(generation_id)=64", name="ck_tenant_generation_length"),
        sa.CheckConstraint(
            "security_epoch>=1 AND revocation_floor>=1", name="ck_tenant_initial_floors"
        ),
        sa.CheckConstraint(
            "state='PENDING' OR publication_digest IS NOT NULL",
            name="ck_tenant_publication_receipt",
        ),
        sa.CheckConstraint(
            "state!='COMPLETE' OR completion_digest IS NOT NULL",
            name="ck_tenant_completion_receipt",
        ),
    )
    op.create_table(
        "tenant_provisioning_outbox",
        sa.Column("receipt_id", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            nullable=False,
            unique=True,
        ),
        sa.Column("generation_id", sa.String(64), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("receipt_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    connection.execute(
        sa.text("""
        DO $roles$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='whitepact_tenant_controller') THEN
            CREATE ROLE whitepact_tenant_controller NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='whitepact_tenant_controller'
            AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolcanlogin)) THEN
            RAISE EXCEPTION 'Unsafe tenant controller role configuration';
          END IF;
        END $roles$;
    """)
    )
    connection.execute(sa.text("REVOKE ALL ON tenant_provisioning_records FROM PUBLIC"))
    connection.execute(sa.text("REVOKE ALL ON tenant_provisioning_outbox FROM PUBLIC"))
    connection.execute(
        sa.text("GRANT SELECT,INSERT ON tenant_provisioning_outbox TO whitepact_tenant_controller")
    )
    connection.execute(
        sa.text("""
        CREATE FUNCTION whitepact_guard_provisioning_outbox() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $guard$
        BEGIN
          IF TG_OP <> 'INSERT' OR current_user <> 'whitepact_tenant_controller' THEN
            RAISE EXCEPTION 'Immutable protected provisioning receipt' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END $guard$;
    """)
    )
    connection.execute(
        sa.text("""
        CREATE TRIGGER guard_provisioning_outbox BEFORE INSERT OR UPDATE OR DELETE
        ON tenant_provisioning_outbox FOR EACH ROW EXECUTE FUNCTION whitepact_guard_provisioning_outbox()
    """)
    )
    connection.execute(
        sa.text(
            "GRANT SELECT,INSERT,UPDATE ON tenant_provisioning_records TO whitepact_tenant_controller"
        )
    )
    connection.execute(
        sa.text(
            "GRANT SELECT,INSERT ON organizations,web_memberships,enterprise_environments "
            "TO whitepact_tenant_controller"
        )
    )
    connection.execute(
        sa.text("GRANT UPDATE(governance_status) ON organizations TO whitepact_tenant_controller")
    )
    connection.execute(
        sa.text("GRANT SELECT ON web_users,web_sessions TO whitepact_tenant_controller")
    )
    connection.execute(sa.text("GRANT SELECT ON alembic_version TO whitepact_tenant_controller"))
    connection.execute(
        sa.text("GRANT EXECUTE ON FUNCTION pg_control_system() TO whitepact_tenant_controller")
    )
    # PostgreSQL row locking requires UPDATE on at least one selected column.
    # No authentication/verification attribute is granted for UPDATE.
    connection.execute(sa.text("GRANT UPDATE(id) ON web_users TO whitepact_tenant_controller"))
    connection.execute(
        sa.text("GRANT UPDATE(org_id) ON web_sessions TO whitepact_tenant_controller")
    )
    connection.execute(
        sa.text(
            "GRANT SELECT,INSERT ON governance_revocation_epochs TO whitepact_tenant_controller"
        )
    )
    connection.execute(sa.text("GRANT SELECT ON tenant_tombstones TO whitepact_tenant_controller"))
    connection.execute(
        sa.text("""
        CREATE FUNCTION whitepact_guard_tenant_provisioning() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $guard$
        BEGIN
          IF current_user <> 'whitepact_tenant_controller' THEN
            RAISE EXCEPTION 'Protected tenant controller required' USING ERRCODE='42501';
          END IF;
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Tenant provisioning evidence cannot be deleted';
          END IF;
          IF TG_OP='UPDATE' THEN
            IF (NEW.tenant_id,NEW.deployment_id,NEW.request_id,NEW.generation_id,NEW.principal_id,
                NEW.operation_digest,NEW.pending_receipt_digest)
              IS DISTINCT FROM
               (OLD.tenant_id,OLD.deployment_id,OLD.request_id,OLD.generation_id,OLD.principal_id,
                OLD.operation_digest,OLD.pending_receipt_digest) THEN
              RAISE EXCEPTION 'Immutable provisioning identity';
            END IF;
            IF NEW.security_epoch < OLD.security_epoch OR NEW.revocation_floor < OLD.revocation_floor
              OR array_position(ARRAY['PENDING','PUBLISHED','COMPLETE'],NEW.state)
                 < array_position(ARRAY['PENDING','PUBLISHED','COMPLETE'],OLD.state) THEN
              RAISE EXCEPTION 'Provisioning rollback rejected';
            END IF;
            IF OLD.publication_digest IS NOT NULL AND NEW.publication_digest IS DISTINCT FROM OLD.publication_digest
              OR OLD.completion_digest IS NOT NULL AND NEW.completion_digest IS DISTINCT FROM OLD.completion_digest THEN
              RAISE EXCEPTION 'Immutable provisioning receipts';
            END IF;
          END IF;
          RETURN NEW;
        END $guard$;
    """)
    )
    connection.execute(
        sa.text("""
        CREATE TRIGGER guard_tenant_provisioning BEFORE INSERT OR UPDATE OR DELETE
        ON tenant_provisioning_records FOR EACH ROW EXECUTE FUNCTION whitepact_guard_tenant_provisioning()
    """)
    )
    connection.execute(
        sa.text("""
        CREATE FUNCTION whitepact_guard_tenant_activation() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $guard$
        BEGIN
          IF NEW.governance_status='ACTIVE' THEN
            IF TG_OP='INSERT' THEN
              RAISE EXCEPTION 'New tenant must be pending and disabled' USING ERRCODE='42501';
            ELSIF OLD.governance_status IS DISTINCT FROM 'ACTIVE' THEN
              IF current_user <> 'whitepact_tenant_controller' OR NOT EXISTS (
                SELECT 1 FROM public.tenant_provisioning_records p WHERE p.tenant_id=NEW.id
                  AND p.principal_id=NEW.owner_user_id AND p.state='COMPLETE'
              ) THEN
                RAISE EXCEPTION 'Completed protected provisioning required' USING ERRCODE='42501';
              END IF;
            END IF;
          END IF;
          RETURN NEW;
        END $guard$;
    """)
    )
    connection.execute(
        sa.text("""
        CREATE TRIGGER guard_tenant_activation BEFORE INSERT OR UPDATE ON organizations
        FOR EACH ROW EXECUTE FUNCTION whitepact_guard_tenant_activation()
    """)
    )
    op.alter_column("organizations", "governance_status", server_default="DISABLED")


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE tenant_provisioning_records IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT count(*) FROM tenant_provisioning_records")):
        raise RuntimeError("Downgrade refused: provisioning evidence must be retained")
    if connection.scalar(sa.text("SELECT count(*) FROM tenant_provisioning_outbox")):
        raise RuntimeError("Downgrade refused: provisioning outbox must be retained")
    op.execute("DROP TRIGGER guard_provisioning_outbox ON tenant_provisioning_outbox")
    op.execute("DROP FUNCTION whitepact_guard_provisioning_outbox()")
    op.drop_table("tenant_provisioning_outbox")
    op.execute("DROP TRIGGER guard_tenant_activation ON organizations")
    op.execute("DROP FUNCTION whitepact_guard_tenant_activation()")
    op.execute("DROP TRIGGER guard_tenant_provisioning ON tenant_provisioning_records")
    op.execute("DROP FUNCTION whitepact_guard_tenant_provisioning()")
    op.drop_table("tenant_provisioning_records")
    op.alter_column("organizations", "governance_status", server_default="ACTIVE")
    # The NOLOGIN role may be referenced by another isolated database; retain it.
