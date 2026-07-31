"""Pharmacy delivery adapter (anti-corruption layer).

Prescriptions are queued in `pharmacy_outbox` as a stable JSON payload. HOW that
payload reaches Visual Chemist depends on what the vendor supports — swap the
adapter without touching the rest of the app:

  * RestPharmacyAdapter  — POST to a Visual Chemist REST endpoint (needs the
    vendor's base URL, auth, and request format).
  * DbPharmacyAdapter    — write into Visual Chemist's MySQL/Postgres tables
    (needs their schema + credentials; it supports PostgreSQL).
  * FileDropAdapter      — write a JSON/CSV file to a shared folder / SFTP the
    pharmacy imports (most likely for the on-prem Windows app).
  * ManualAdapter (default) — no auto-delivery; staff pull the payload / print
    the Rx and mark it sent from the Pharmacy screen. Works today.

To go live: implement `deliver()` for the real transport and select it here.
"""

from __future__ import annotations

from typing import Protocol


class PharmacyAdapter(Protocol):
    async def deliver(self, payload: dict) -> None:
        """Send one prescription payload to the pharmacy. Raise on failure."""
        ...


class ManualAdapter:
    """Default: no automated push. The outbox holds 'pending' entries that staff
    action from the Pharmacy screen (copy JSON / print, then mark sent)."""

    async def deliver(self, payload: dict) -> None:  # noqa: D401 - see class doc
        raise NotImplementedError(
            "No automated pharmacy transport is configured yet. Provide Visual "
            "Chemist's API/DB/file spec, then implement a real adapter."
        )


def get_adapter() -> PharmacyAdapter:
    """Return the configured adapter. Swap this once the vendor transport is known."""
    return ManualAdapter()
