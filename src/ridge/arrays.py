"""Array type aliases shared across Ridge."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

type ImageU8 = NDArray[np.uint8]
"""8-bit image: H x W (grayscale) or H x W x 3 (BGR)."""

type FloatImage = NDArray[np.float32]
"""Single-channel float32 image or map."""

type Mask = NDArray[np.bool_]
"""Boolean H x W mask."""
