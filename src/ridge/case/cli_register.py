"""``ridge-case`` key register (OQ-9): check a register file, and name key holders in the offline checks.

ridge-case register --check REGISTER.json
ridge-case check-report|check-log|check-head|check-package ... --register REGISTER.json
ridge-case limits --check FILE --register REGISTER.json
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.key_register import confirm_key, describe, load_register


def add_register_argument(parser: Any) -> None:
    """Add ``--register`` to a check command."""
    parser.add_argument(
        "--register",
        type=Path,
        help="the laboratory's key register: name the key's holder and check its role and validity",
    )


def confirm(args: argparse.Namespace, key_id: str, role: str, signed_utc: str | None = None) -> bool:
    """Name the registered holder of `key_id`; refuse an unregistered or invalid key.

    Returns False when no register was given, so the caller can ask for a manual key check.
    """
    if not getattr(args, "register", None):
        return False
    register = load_register(args.register)
    when = signed_utc or datetime.now(UTC).isoformat()
    common.say(f"key {key_id} {describe(register, confirm_key(register, key_id, role, when))}")
    return True


def cmd_register(args: argparse.Namespace) -> None:
    """Validate a key register and list its keys."""
    register = load_register(args.check)
    common.say(f"{register.laboratory} key register, {len(register.keys)} key(s), sha256 {register.sha256}")
    for key in register.keys.values():
        until = key.valid_until or "open"
        revoked = f", revoked {key.revoked}" if key.revoked else ""
        common.say(f"  {key.key_id}  {key.role:8}  {key.holder}  {key.valid_from} to {until}{revoked}")


def add_commands(sub: Any) -> None:
    """Register the key register command on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("register", help="check the laboratory's key register (holders, roles, validity)")
    p.add_argument("--check", type=Path, required=True, help="a ridge.key-register/1 file")
    p.set_defaults(func=cmd_register)
