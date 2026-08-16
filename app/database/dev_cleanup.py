"""Development-only cleanup for local test accounts / organizations.

Usage (local development only):
    python -m app.database.dev_cleanup --dry-run
    python -m app.database.dev_cleanup --confirm

Preserves seeded demo organizations (demo-org, other-org) and their demo users.
Removes:
  - organizations created via public registration / ad-hoc testing
  - non-demo users invited into demo orgs (so emails can be reused)
  - related workflow / notification rows (via CASCADE or explicit deletes)

Never runs unless APP_ENV is development/test and --confirm is passed
(or --dry-run for a preview).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from sqlalchemy import delete, or_, select, text

from app.auth.store import build_demo_users
from app.config.settings import get_settings
from app.database.errors import DatabaseNotConfiguredError, DatabaseUnavailableError
from app.database.models.notification import NotificationEventRecord
from app.database.models.organization import Organization
from app.database.models.user import UserRecord
from app.database.session import session_scope

PROTECTED_ORG_IDS = frozenset({"demo-org", "other-org"})
PROTECTED_USER_IDS = frozenset(user.user_id for user in build_demo_users())
_ALLOWED_ENVS = frozenset({"development", "dev", "test", "testing", "local"})


@dataclass
class CleanupPlan:
    organizations_to_delete: list[tuple[str, str]] = field(default_factory=list)
    users_to_delete: list[tuple[str, str, str]] = field(default_factory=list)
    notification_org_ids: list[str] = field(default_factory=list)
    workflow_run_count: int = 0
    notification_count: int = 0


def _assert_dev_environment() -> None:
    env = get_settings().app_env.strip().lower()
    if env not in _ALLOWED_ENVS:
        raise RuntimeError(
            f"Refusing to run: APP_ENV={env!r}. "
            "dev_cleanup is allowed only for development/test/local."
        )


def build_cleanup_plan() -> CleanupPlan:
    """Inspect the database and return what would be removed."""

    _assert_dev_environment()
    plan = CleanupPlan()
    with session_scope() as session:
        orgs = list(session.scalars(select(Organization)).all())
        for org in orgs:
            if org.organization_id not in PROTECTED_ORG_IDS:
                plan.organizations_to_delete.append((org.organization_id, org.name))

        users = list(session.scalars(select(UserRecord)).all())
        for user in users:
            in_doomed_org = user.organization_id not in PROTECTED_ORG_IDS
            non_demo_in_seed_org = (
                user.organization_id in PROTECTED_ORG_IDS
                and user.user_id not in PROTECTED_USER_IDS
            )
            if in_doomed_org or non_demo_in_seed_org:
                plan.users_to_delete.append(
                    (user.user_id, user.username, user.organization_id)
                )

        doomed_org_ids = {oid for oid, _ in plan.organizations_to_delete}
        # Notifications for doomed orgs, plus any tied to doomed users still in seed orgs.
        doomed_user_ids = {uid for uid, _, _ in plan.users_to_delete}
        notif_orgs = set(doomed_org_ids)
        if doomed_user_ids:
            rows = session.execute(
                select(NotificationEventRecord.organization_id).where(
                    NotificationEventRecord.recipient_user_id.in_(doomed_user_ids)
                )
            )
            notif_orgs.update(r[0] for r in rows if r[0])
        plan.notification_org_ids = sorted(notif_orgs)

        if doomed_org_ids:
            plan.workflow_run_count = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM workflow_runs "
                        "WHERE organization_id = ANY(:orgs)"
                    ),
                    {"orgs": list(doomed_org_ids)},
                ).scalar()
                or 0
            )
        if plan.notification_org_ids:
            plan.notification_count = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM notification_events "
                        "WHERE organization_id = ANY(:orgs) "
                        "   OR recipient_user_id = ANY(:uids)"
                    ),
                    {
                        "orgs": plan.notification_org_ids or [""],
                        "uids": list(doomed_user_ids) or [""],
                    },
                ).scalar()
                or 0
            )
    return plan


def execute_cleanup(plan: CleanupPlan | None = None) -> CleanupPlan:
    """Apply cleanup. Cascades remove workflow_runs → decisions/approvals/audits/metrics."""

    _assert_dev_environment()
    plan = plan or build_cleanup_plan()
    doomed_org_ids = [oid for oid, _ in plan.organizations_to_delete]
    doomed_user_ids = [uid for uid, _, _ in plan.users_to_delete]

    with session_scope() as session:
        # 1) Notification events (no FK to organizations — delete explicitly).
        notif_filters = []
        if doomed_org_ids:
            notif_filters.append(
                NotificationEventRecord.organization_id.in_(doomed_org_ids)
            )
        if doomed_user_ids:
            notif_filters.append(
                NotificationEventRecord.recipient_user_id.in_(doomed_user_ids)
            )
        if notif_filters:
            session.execute(delete(NotificationEventRecord).where(or_(*notif_filters)))

        # 2) Non-demo users inside protected orgs (invites / ad-hoc accounts).
        seed_org_user_ids = [
            uid
            for uid, _, oid in plan.users_to_delete
            if oid in PROTECTED_ORG_IDS
        ]
        if seed_org_user_ids:
            session.execute(
                delete(UserRecord).where(
                    UserRecord.user_id.in_(seed_org_user_ids),
                    UserRecord.organization_id.in_(PROTECTED_ORG_IDS),
                )
            )

        # 3) Non-protected organizations — CASCADE deletes their users + workflow trees.
        if doomed_org_ids:
            session.execute(
                delete(Organization).where(Organization.organization_id.in_(doomed_org_ids))
            )

    return plan


def _print_plan(plan: CleanupPlan) -> None:
    print("Protected organizations:", ", ".join(sorted(PROTECTED_ORG_IDS)))
    print("Protected demo user_ids:", len(PROTECTED_USER_IDS))
    print()
    print(f"Organizations to delete ({len(plan.organizations_to_delete)}):")
    for oid, name in plan.organizations_to_delete:
        print(f"  - {oid} ({name})")
    if not plan.organizations_to_delete:
        print("  (none)")
    print(f"Users to delete ({len(plan.users_to_delete)}):")
    for uid, username, oid in plan.users_to_delete:
        print(f"  - {username} [{uid}] org={oid}")
    if not plan.users_to_delete:
        print("  (none)")
    print(f"Workflow runs in doomed orgs: {plan.workflow_run_count}")
    print(f"Notification events to clear: {plan.notification_count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove local development/test accounts so emails can be reused."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deletions without changing data.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to actually delete data (development/test only).",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="After cleanup, upsert demo seed organizations/users.",
    )
    args = parser.parse_args(argv)

    if not args.dry_run and not args.confirm:
        print(
            "Refusing to modify data. Pass --dry-run to preview or --confirm to apply.",
            file=sys.stderr,
        )
        return 2

    try:
        plan = build_cleanup_plan()
    except DatabaseNotConfiguredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except DatabaseUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_plan(plan)

    if args.dry_run:
        print("\nDry run only — no changes made.")
        return 0

    try:
        execute_cleanup(plan)
    except DatabaseUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cleanup failed ({type(exc).__name__}: {exc}).", file=sys.stderr)
        return 1

    print("\nCleanup applied.")

    if args.reseed:
        from app.database.seed import seed_development_data

        seed_development_data()
        print("Demo seed organizations/users upserted.")

    # Post-verification summary
    with session_scope() as session:
        remaining_users = list(
            session.execute(
                text("SELECT username, organization_id, role FROM users ORDER BY username")
            )
        )
        remaining_orgs = list(
            session.execute(text("SELECT organization_id, name FROM organizations ORDER BY 1"))
        )
    print("\nRemaining organizations:")
    for oid, name in remaining_orgs:
        print(f"  - {oid} ({name})")
    print("Remaining users:")
    for username, oid, role in remaining_users:
        print(f"  - {username} org={oid} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
