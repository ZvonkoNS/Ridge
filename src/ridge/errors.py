"""Typed errors for expected, user-facing failures.

Every expected failure raises a ``RidgeError`` subclass whose message is safe to show to the
examiner: it never contains pixel data, keys or stack traces. Extraction and input errors
also derive from ``ValueError`` so code written against v0 (which raised ``ValueError``)
keeps working.
"""

from __future__ import annotations


class RidgeError(Exception):
    """Base class for expected Ridge failures."""


class InputError(RidgeError, ValueError):
    """An input file cannot be used."""


class InputRejectedError(InputError):
    """The input violates a limit or the format allow-list; it was not fully decoded."""


class DecodeError(InputError):
    """The input is corrupt, truncated or otherwise undecodable."""


class ParameterError(RidgeError, ValueError):
    """A caller-supplied parameter is out of range or of the wrong type."""


class OutputError(RidgeError):
    """An output cannot be written."""


class OutputExistsError(OutputError):
    """The output file already exists and overwriting was not requested."""


class ExtractionError(RidgeError, ValueError):
    """The photo was read but no fingerprint could be extracted."""


class ImageTooSmallError(ExtractionError):
    """The image is too small to measure the ridge spacing."""


class ResolutionTooLowError(ExtractionError):
    """Ridges are too close together in pixels to be resolved."""


class NoRidgePatternError(ExtractionError):
    """No area with a clear, repeating ridge pattern was found."""


class WorkAreaTooLargeError(ExtractionError):
    """At this ridge spacing the finger area would need too much memory to process."""
