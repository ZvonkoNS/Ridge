"""Ridge: extract fingerprints from photos of fingers as white ridges on a black background.

Ridge is an image-enhancement aid for qualified examiners. It does not identify anyone and
draws no conclusions.

Library use::

    from ridge import extract_fingerprint
    result = extract_fingerprint(bgr_uint8_array)
    result.image, result.period, result.found_finger
"""

from __future__ import annotations

from ridge.errors import (
    DecodeError,
    ExtractionError,
    ImageTooSmallError,
    InputError,
    InputRejectedError,
    NoRidgePatternError,
    OutputError,
    OutputExistsError,
    ParameterError,
    ResolutionTooLowError,
    RidgeError,
    WorkAreaTooLargeError,
)
from ridge.pipeline import DebugImages, ExtractionResult, extract_fingerprint

__version__ = "0.2.0"

__all__ = [
    "DebugImages",
    "DecodeError",
    "ExtractionError",
    "ExtractionResult",
    "ImageTooSmallError",
    "InputError",
    "InputRejectedError",
    "NoRidgePatternError",
    "OutputError",
    "OutputExistsError",
    "ParameterError",
    "ResolutionTooLowError",
    "RidgeError",
    "WorkAreaTooLargeError",
    "__version__",
    "extract_fingerprint",
]
