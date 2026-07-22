"""Role/plan hierarchy and permission helpers."""

from __future__ import annotations

from responsibleai.rbac.models import Plan, Role

_HIERARCHY: dict[Role, int] = {
    Role.OWNER: 4,
    Role.ADMIN: 3,
    Role.ANALYST: 2,
    Role.VIEWER: 1,
}

_PLAN_HIERARCHY: dict[Plan, int] = {
    Plan.ENTERPRISE: 3,
    Plan.PRO: 2,
    Plan.FREE: 1,
}


def has_permission(user_role: Role, required_role: Role) -> bool:
    """Return True if *user_role* satisfies the *required_role* minimum."""
    return _HIERARCHY.get(user_role, 0) >= _HIERARCHY.get(required_role, 0)


def has_plan(user_plan: Plan, required_plan: Plan) -> bool:
    """Return True if *user_plan* satisfies the *required_plan* minimum."""
    return _PLAN_HIERARCHY.get(user_plan, 0) >= _PLAN_HIERARCHY.get(required_plan, 0)


def role_from_str(s: str) -> Role:
    try:
        return Role(s.upper())
    except ValueError:
        return Role.VIEWER


def roles_above(min_role: Role) -> list[Role]:
    """Return all roles that satisfy *min_role* or higher."""
    floor = _HIERARCHY[min_role]
    return [r for r, level in _HIERARCHY.items() if level >= floor]
