"""``ridge-case`` limits-of-use commands (PRD §12 item 8): show, check and sign the limits file.

ridge-case limits --store STORE                   (the store's limits and who signed them)
ridge-case limits --check FILE [--key-id KEY_ID]  (validate a file, and its FILE.sig if present)
ridge-case limits --sign FILE --key FQM_KEY [--overwrite]   (the FQM writes FILE.sig)
ridge-case fqm-key --to FQM_KEY                   (create the FQM's sealed signing key)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.cli_register import add_register_argument, confirm
from ridge.case.limits import FILE, LimitsOfUse, load_limits, read_limits
from ridge.case.limits_signing import create_fqm_key, sign_limits
from ridge.errors import ParameterError

FQM_PROMPT = "FQM key passphrase: "


def _show(limits: LimitsOfUse, expected_key_id: str | None, args: argparse.Namespace) -> None:
    common.say(f"limits of use from {limits.source}, sha256 {limits.sha256}")
    signer = limits.signed_by["key_id"] if limits.signed_by else None
    if expected_key_id and signer != expected_key_id:
        raise ParameterError(
            f"the limits are {'signed with key ' + signer if signer else 'not signed'}, not {expected_key_id}"
        )
    if signer and confirm(args, signer, "fqm"):  # the limits apply now, so the key must be valid today
        pass
    elif signer:
        confirmed = "" if expected_key_id else " (confirm it is the FQM's key, or pass --key-id or --register)"
        common.say(f"signed with key {signer}{confirmed}")
    else:
        common.say("not signed")
    for key, value in limits.to_json().items():
        common.say(f"  {key}: {value}")


def cmd_limits(args: argparse.Namespace) -> None:
    """Show a store's limits of use, check a limits file, or sign one with the FQM key."""
    if args.sign:
        if not args.key:
            raise ParameterError("--sign needs --key, the FQM key file")
        dest = sign_limits(args.sign, args.key, common.read_passphrase(prompt=FQM_PROMPT), overwrite=args.overwrite)
        common.say(f"signed: {dest} (place it in the store beside {FILE})")
        return
    limits = read_limits(args.check) if args.check else load_limits(args.store)
    if limits is None:
        common.say(f"no limits of use configured ({args.store / FILE} does not exist)")
        return
    _show(limits, args.key_id, args)


def cmd_fqm_key(args: argparse.Namespace) -> None:
    """Create the Forensic Quality Manager's sealed key for signing limits of use."""
    signer = create_fqm_key(args.to, common.read_passphrase(confirm=True, prompt=FQM_PROMPT), common.KDF_PARAMS)
    common.say(f"FQM key {signer.key_id} written to {args.to}")
    common.say("register this key id with the laboratory; keep the file off examiner workstations")


def add_commands(sub: Any) -> None:
    """Register the limits commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("limits", help="show, check or sign the limits of use (PRD section 12)")
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--store", type=Path, help="the case store whose limits-of-use.json to show")
    where.add_argument("--check", type=Path, help="a limits file to validate before it is placed in a store")
    where.add_argument("--sign", type=Path, metavar="FILE", help="sign a limits file with the FQM key (FILE.sig)")
    p.add_argument("--key", type=Path, help="the FQM key file (with --sign)")
    p.add_argument("--key-id", help="the FQM key id the limits must be signed with")
    p.add_argument("--overwrite", action="store_true", help="replace an existing FILE.sig (with --sign)")
    add_register_argument(p)
    p.set_defaults(func=cmd_limits)
    p = sub.add_parser("fqm-key", help="create the Forensic Quality Manager's key for signing limits of use")
    p.add_argument("--to", type=Path, required=True)
    p.set_defaults(func=cmd_fqm_key)
