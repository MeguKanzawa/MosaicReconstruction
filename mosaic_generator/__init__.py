"""mosaic_generator: build photo mosaics from a library of tile images.
"""

from .metrics import calculate_mse, calculate_ssim, compute_metrics
from .mosaic_builder import MosaicBuilder, MosaicResult
from .tile_manager import TileManager
from .utils import ImageLoadError, InvalidParameterError, MosaicError, TileLoadError

__version__ = "1.0.0"

__all__ = [
    "MosaicBuilder",
    "MosaicResult",
    "TileManager",
    "calculate_mse",
    "calculate_ssim",
    "compute_metrics",
    "MosaicError",
    "ImageLoadError",
    "TileLoadError",
    "InvalidParameterError",
]
