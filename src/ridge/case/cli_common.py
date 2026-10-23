"""Shared pieces of the ``ridge-case`` command modules: keystore, KDF cost, passphrase prompt, output.

Every line ``ridge-case`` writes goes through `say` or `warn`, which show hidden and control
characters as ``<U+XXXX>``: file names, labels, notes and metadata are attacker-controlled
(CWE-150, CVE-2021-42574).

Command modules use these through the module (``common.KEYSTORE_FACTORY()``), so tests can replace
the keystore and the Argon2id cost in one place.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable

from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore
from ridge.errors import ParameterError
from ridge.terminal import safe

KEYSTORE_FACTORY: Callable[[], KeyStore] = KeyringKeyStore  # replaced in tests
KDF_PARAMS = KdfParams()  # replaced in tests with the minimum allowed cost


def read_passphrase(*, confirm: bool = False, prompt: str = "Examiner passphrase: ") -> str:
    """Prompt for a passphrase (twice when setting it); never from arguments or the environment."""
    first = getpass.getpass(prompt)
    if confirm and getpass.getpass("Repeat passphrase: ") != first:
        raise ParameterError("the passphrases do not match")
    return first


def say(text: str, *, lines: bool = False) -> None:
    """Write one line of command output; hidden and control characters appear as ``<U+XXXX>``.

    Line breaks in `text` are shown too, unless `lines=True`: only for text whose untrusted parts
    cannot contain one, such as JSON from ``json.dumps`` (``ridge.terminal.safe``).
    """
    print(safe(text, lines=lines))  # noqa: T201  # CLI output


def warn(text: str, *, lines: bool = False) -> None:
    """Write a message or error to stderr, made safe like `say` output."""
    print(safe(text, lines=lines), file=sys.stderr)  # noqa: T201  # CLI output


def nfiq2_command(args: argparse.Namespace) -> list[str] | None:
    """Build the NFIQ 2 command line from ``--nfiq2`` and ``--nfiq2-arg`` (None without ``--nfiq2``)."""
    return [str(args.nfiq2), *args.nfiq2_arg] if args.nfiq2 else None
