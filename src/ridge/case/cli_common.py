"""Shared pieces of the ``ridge-case`` command modules: keystore, KDF cost, passphrase prompt, output.

Command modules use these through the module (``common.KEYSTORE_FACTORY()``), so tests can replace
the keystore and the Argon2id cost in one place.
"""

from __future__ import annotations

import argparse
import getpass
from collections.abc import Callable

from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore
from ridge.errors import ParameterError

KEYSTORE_FACTORY: Callable[[], KeyStore] = KeyringKeyStore  # replaced in tests
KDF_PARAMS = KdfParams()  # replaced in tests with the minimum allowed cost


def read_passphrase(*, confirm: bool = False, prompt: str = "Examiner passphrase: ") -> str:
    """Prompt for a passphrase (twice when setting it); never from arguments or the environment."""
    first = getpass.getpass(prompt)
    if confirm and getpass.getpass("Repeat passphrase: ") != first:
        raise ParameterError("the passphrases do not match")
    return first


def say(text: str) -> None:
    """Write one line of command output."""
    print(text)  # noqa: T201  # CLI output


def nfiq2_command(args: argparse.Namespace) -> list[str] | None:
    """Build the NFIQ 2 command line from ``--nfiq2`` and ``--nfiq2-arg`` (None without ``--nfiq2``)."""
    return [str(args.nfiq2), *args.nfiq2_arg] if args.nfiq2 else None
