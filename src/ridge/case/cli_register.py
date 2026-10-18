"""``ridge-case`` key register (OQ-9): check a register file, and name key holders in the offline checks.

ridge-case register --check REGISTER.json
ridge-case key-card (--store STORE | --fqm-key KEY) --holder NAME --to CARD.json
ridge-case register-add --card CARD.json (--register OLD.json | --laboratory NAME) --to NEW.json
                        [--valid-from YYYY-MM-DD] [--valid-until YYYY-MM-DD]
ridge-case check-report|check-log|check-head|check-package ... --register REGISTER.json
ridge-case limits --check FILE --register REGISTER.json
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.identity import unlock_identity
from ridge.case.key_card import check_card, register_add, write_card
from ridge.case.key_register import confirm_key, describe, load_register
from ridge.case.limits_signing import unlock_fqm_key


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


def cmd_key_card(args: argparse.Namespace) -> None:
    """Write a self-signed key card for the examiner identity or the FQM key."""
    if args.fqm_key:
        signer, role = unlock_fqm_key(args.fqm_key, common.read_passphrase(prompt="FQM key passphrase: ")), "fqm"
    else:
        signer, role = unlock_identity(args.store, common.read_passphrase(), common.KEYSTORE_FACTORY()), "examiner"
    card = write_card(signer, role, args.holder, args.to)
    common.say(f"key card for {role} key {card.key_id} written to {args.to}")
    common.say("give it to the laboratory, which confirms who you are before adding it to its register")


def cmd_register_add(args: argparse.Namespace) -> None:
    """Add a checked key card to a new version of the register."""
    card = check_card(args.card)
    count = register_add(
        card,
        args.to,
        register=args.register,
        laboratory=args.laboratory,
        valid_from=args.valid_from or datetime.now(UTC).date(),
        valid_until=args.valid_until,
    )
    common.say(f"{card.role} key {card.key_id} of {card.holder} added; {args.to} lists {count} key(s)")


def add_commands(sub: Any) -> None:
    """Register the key register commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("register", help="check the laboratory's key register (holders, roles, validity)")
    p.add_argument("--check", type=Path, required=True, help="a ridge.key-register/1 file")
    p.set_defaults(func=cmd_register)
    p = sub.add_parser("key-card", help="write a self-signed card of your public key for the laboratory")
    whose = p.add_mutually_exclusive_group(required=True)
    whose.add_argument("--store", type=Path, help="the case store whose examiner identity the card is for")
    whose.add_argument("--fqm-key", type=Path, help="the FQM key file the card is for")
    p.add_argument("--holder", required=True, help="your name as the laboratory registers it")
    p.add_argument("--to", type=Path, required=True)
    p.set_defaults(func=cmd_key_card)
    p = sub.add_parser("register-add", help="add a key card to a new version of the key register")
    p.add_argument("--card", type=Path, required=True)
    old = p.add_mutually_exclusive_group(required=True)
    old.add_argument("--register", type=Path, help="the current register (it is not changed)")
    old.add_argument("--laboratory", help="the laboratory's name, for a first register")
    p.add_argument("--to", type=Path, required=True, help="where to write the new register")
    p.add_argument("--valid-from", type=date.fromisoformat, help="first valid day (default: today, UTC)")
    p.add_argument("--valid-until", type=date.fromisoformat, help="last valid day (default: open)")
    p.set_defaults(func=cmd_register_add)
