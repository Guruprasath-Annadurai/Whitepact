"""Controlled authenticator fixture using real server enrollment and verification."""

import hashlib
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric import ec

from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.service import compute_canonical_operation_digest
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from tests.webauthn_fakes import assertion_blob, registration_blob


async def qualify_owner(engine, actor):
    repository = WebIdentityRepository(engine)
    token, _ = await repository.create_session(actor.user_id, org_id=actor.org_id)
    identity = IdentitySecurityService(engine, origin="http://localhost", rp_id="localhost")
    _, _, session = await identity.load_session(token)
    key = ec.generate_private_key(ec.SECP256R1())
    challenge = await identity.begin_webauthn(
        user_id=actor.user_id,
        session_id=session.session_id,
        ceremony="register",
        org_id=actor.org_id,
    )
    client, authenticator, credential, _ = registration_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(challenge["challenge"]),
        private_key=key,
    )
    grant = await identity.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=actor.org_id)
    await identity.finish_passkey_registration(
        user_id=actor.user_id,
        session=session,
        client_data_b64=client,
        authenticator_data_b64=authenticator,
        grant=grant,
    )
    challenge = await identity.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate"
    )
    client, authenticator, signature = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(challenge["challenge"]),
        private_key=key,
    )
    _, _, verified = await identity.authenticate_passkey(
        client_data_b64=client,
        authenticator_data_b64=authenticator,
        signature_b64=signature,
        credential_id=credential,
        org_id=actor.org_id,
    )
    return replace(actor, session_id=verified.session_id), key, credential


async def root_completion_assertion(service, actor, ceremony, public_key, key, credential):
    digest = compute_canonical_operation_digest(
        "COMPLETE_ROOT_BOOTSTRAP",
        {
            "org_id": actor.org_id,
            "nonce": ceremony["nonce"],
            "token_hash": hashlib.sha256(ceremony["token"].encode()).hexdigest(),
            "root_public_key": public_key,
        },
    )
    challenge = await service.create_authority_stepup_challenge(
        actor,
        org_id=actor.org_id,
        action="COMPLETE_ROOT_BOOTSTRAP",
        operation_digest=digest,
    )
    client, authenticator, signature = assertion_blob(
        rp_id=challenge["rp_id"],
        origin=challenge["origin"],
        challenge=b64url_decode(challenge["challenge"]),
        private_key=key,
        sign_count=2,
    )
    return {
        "credential_id": credential,
        "client_data_json": client,
        "authenticator_data": authenticator,
        "signature": signature,
    }
