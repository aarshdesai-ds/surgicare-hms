"""Append-only audit logging helper.

Call within the same DB connection/transaction as the action being audited so
the audit row commits atomically with it.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def write_audit(
    conn: asyncpg.Connection,
    *,
    actor_id: str | None,
    action: str,
    entity: str,
    entity_id: Any = None,
    detail: dict | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO public.audit_log
            (actor_user_id, action, entity, entity_id, detail)
        VALUES ($1::uuid, $2, $3, $4, $5)
        """,
        actor_id,
        action,
        entity,
        str(entity_id) if entity_id is not None else None,
        detail,
    )
