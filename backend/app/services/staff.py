"""Staff / profile management (admin-only).

Manages roles and active status of existing users. Email is read from
auth.users (the backend connects with a privileged role that can read it).
"""

from __future__ import annotations

import asyncpg
import httpx

from ..config import settings
from ..errors import AppError
from ..schemas.staff import StaffCreate, StaffUpdate
from ..utils.audit import write_audit


async def list_staff(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT p.id, p.full_name, p.role, p.is_active, p.created_at,
               u.email
        FROM public.profiles p
        LEFT JOIN auth.users u ON u.id = p.id
        ORDER BY p.is_active DESC, p.created_at
        """
    )
    return [dict(r) for r in rows]


async def create_staff(
    conn: asyncpg.Connection, data: StaffCreate, actor_id: str
) -> dict:
    """Create a login via the Supabase Auth admin API, then set the role.

    The DB trigger auto-creates a profile row (default role 'reception') when the
    auth user is inserted; we then set the requested role on it.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise AppError(
            "NOT_CONFIGURED",
            "Supabase URL / service role key are not configured on the server.",
            status_code=500,
        )

    url = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    body = {
        "email": data.email,
        "password": data.password,
        "email_confirm": True,  # usable immediately, no confirmation email
        "user_metadata": {"full_name": data.full_name, "phone": data.phone},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=body)

    payload = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        msg = (
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or "Could not create the user."
        )
        raise AppError("USER_CREATE_FAILED", msg, status_code=400)

    new_id = payload.get("id")
    if not new_id:
        raise AppError(
            "USER_CREATE_FAILED",
            "Unexpected response from the auth service.",
            status_code=502,
        )

    # Ensure the profile exists with the requested role (trigger may set default).
    await conn.execute(
        """
        INSERT INTO public.profiles (id, full_name, phone, role)
        VALUES ($1::uuid, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
            role = EXCLUDED.role,
            full_name = COALESCE(EXCLUDED.full_name, public.profiles.full_name),
            phone = COALESCE(EXCLUDED.phone, public.profiles.phone)
        """,
        new_id, data.full_name, data.phone, data.role,
    )
    await write_audit(
        conn, actor_id=actor_id, action="create", entity="profiles",
        entity_id=new_id, detail={"role": data.role, "email": data.email},
    )
    return {
        "id": new_id, "email": data.email, "full_name": data.full_name,
        "role": data.role, "is_active": True,
    }


async def update_staff(
    conn: asyncpg.Connection, staff_id: str, data: StaffUpdate, actor_id: str
) -> dict:
    # Guard against self-lockout: an admin can't change their own role/status
    # (editing your own name is fine). This guarantees ≥1 active admin remains.
    if str(staff_id) == str(actor_id) and (
        data.role is not None or data.is_active is not None
    ):
        raise AppError(
            code="SELF_EDIT",
            message="You can't change your own role or status.",
            status_code=422,
        )

    exists = await conn.fetchval(
        "SELECT 1 FROM public.profiles WHERE id = $1::uuid", staff_id
    )
    if not exists:
        raise AppError("NOT_FOUND", "Staff member not found.", status_code=404)

    sets: list[str] = []
    params: list = []
    if data.role is not None:
        params.append(data.role)
        sets.append(f"role = ${len(params)}")
    if data.is_active is not None:
        params.append(data.is_active)
        sets.append(f"is_active = ${len(params)}")
    if data.full_name is not None:
        params.append(data.full_name)
        sets.append(f"full_name = ${len(params)}")
    params.append(staff_id)

    row = await conn.fetchrow(
        f"""
        UPDATE public.profiles SET {', '.join(sets)}
        WHERE id = ${len(params)}::uuid
        RETURNING id, full_name, role, is_active, created_at
        """,
        *params,
    )
    email = await conn.fetchval(
        "SELECT email FROM auth.users WHERE id = $1::uuid", staff_id
    )
    await write_audit(
        conn, actor_id=actor_id, action="update", entity="profiles",
        entity_id=staff_id,
        detail={k: v for k, v in data.model_dump(exclude_unset=True).items()},
    )
    result = dict(row)
    result["email"] = email
    return result
