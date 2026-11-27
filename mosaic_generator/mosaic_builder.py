"""Main mosaic construction logic."""

from dataclasses import dataclass, field

import numpy as np

from . import config
from .image_processor import (GridSpec, cell_average_colors, center_crop, compute_grid,
                              crop_to_grid, draw_grid, load_image)
from .metrics import calculate_mse, calculate_ssim
from .tile_manager import TileManager
from .utils import InvalidParameterError, StageTimer, time_call


@dataclass
class MosaicResult:
    """Everything produced by one mosaic run.

    Attributes
    ----------
    cropped : numpy.ndarray
        Input image cropped to the grid, shape (H, W, 3).
    segmented : numpy.ndarray
        ``cropped`` with the grid lines drawn on it.
    mosaic : numpy.ndarray
        The mosaic, shape (H, W, 3), uint8.
    cell_colors : numpy.ndarray
        Average color of each cell, shape (rows, cols, 3).
    tile_indices : numpy.ndarray
        Index of the tile used in each cell, shape (rows, cols).
    grid : GridSpec
        Grid layout used.
    timings : dict
        Milliseconds per stage, in order.
    mse, ssim : float or None
        Similarity between ``cropped`` and ``mosaic``; None if not computed.
    """
    cropped: np.ndarray
    segmented: np.ndarray
    mosaic: np.ndarray
    cell_colors: np.ndarray
    tile_indices: np.ndarray
    grid: GridSpec
    timings: dict = field(default_factory=dict)
    mse: float | None = None
    ssim: float | None = None

    @property
    def total_ms(self):
        """Total processing time over all recorded stages.

        Returns
        -------
        float
            Milliseconds.
        """
        return sum(self.timings.values())

    @property
    def generation_ms(self):
        """Time spent building the mosaic, excluding the quality metrics.

        Returns
        -------
        float
            Milliseconds.
        """
        return sum(v for k, v in self.timings.items() if k not in ("mse", "ssim"))


class MosaicBuilder:
    """Builds photo mosaics from a tile library.

    Parameters
    ----------
    tile_manager : TileManager
        Loaded tile library.
    grid_size : int or tuple of (int, int), optional
        Default number of tiles per side, or (rows, cols). Used when neither size
        is passed to ``build``. Defaults to ``config.DEFAULT_GRID_SIZE``.
    tile_size : int, optional
        Default tile side in pixels, instead of ``grid_size`` (Lab 1 behavior:
        the largest square grid of such tiles that fits).

    Raises
    ------
    InvalidParameterError
        If both ``grid_size`` and ``tile_size`` are given, or ``tile_manager`` is
        not a TileManager.

    Example
    -------
        from mosaic_generator import MosaicBuilder, TileManager
        tile_manager = TileManager(tile_directory="tiles/")
        builder = MosaicBuilder(tile_manager, grid_size=(32, 32))
        mosaic = builder.create_mosaic("img/cake4.png")
        similarity = builder.compute_similarity("img/cake4.png", mosaic)
        sorted(similarity)
    ['mse', 'ssim']
    """

    def __init__(self, tile_manager, grid_size=None, tile_size=None):
        """Store the tile library and default size (see the class docstring)."""
        if not isinstance(tile_manager, TileManager):
            raise InvalidParameterError(
                f"tile_manager must be a TileManager, got {type(tile_manager).__name__}")
        if grid_size is not None and tile_size is not None:
            raise InvalidParameterError("Give grid_size or tile_size, not both.")
        if grid_size is None and tile_size is None:
            grid_size = config.DEFAULT_GRID_SIZE
        self.tile_manager = tile_manager
        self.grid_size = grid_size
        self.tile_size = tile_size

    def _sizes(self, grid_size, tile_size):
        """Pick the size for one call: the call's arguments, else the builder's defaults.

        Parameters
        ----------
        grid_size : int or tuple of (int, int) or None
        tile_size : int or None

        Returns
        -------
        tuple
            (grid_size, tile_size), exactly one of them not None.
        """
        if grid_size is not None and tile_size is not None:
            raise InvalidParameterError("Give grid_size or tile_size, not both.")
        if grid_size is None and tile_size is None:
            return self.grid_size, self.tile_size
        return grid_size, tile_size

    def build(self, image, grid_size=None, tile_size=None, compute_metrics=False):
        """Build a mosaic and return every intermediate result with stage timings.

        Parameters
        ----------
        image : str, pathlib.Path, file-like, PIL.Image.Image or numpy.ndarray
            Input image (see ``image_processor.load_image``).
        grid_size : int or tuple of (int, int), optional
            Tiles per side, or (rows, cols), for this call only.
        tile_size : int, optional
            Tile side in pixels, for this call only.
        compute_metrics : bool, optional
            Also compute MSE and SSIM against the cropped input (default False).

        Returns
        -------
        MosaicResult

        Raises
        ------
        ImageLoadError
            If the image cannot be read.
        InvalidParameterError
            If a size is invalid or the grid does not fit in the image.
        """
        grid_size, tile_size = self._sizes(grid_size, tile_size)
        timer = StageTimer()

        img = load_image(image)
        timer.lap("load")

        grid = compute_grid(img.shape, grid_size=grid_size, tile_size=tile_size)
        cropped = crop_to_grid(img, grid)
        segmented = draw_grid(cropped, grid.tile_size)
        timer.lap("crop_grid")

        cell_colors = cell_average_colors(cropped, grid)
        timer.lap("cell_avg")

        indices = self.tile_manager.nearest(cell_colors)
        timer.lap("search")

        tiles = self.tile_manager.resized(grid.tile_size)
        timer.lap("resize")

        mosaic = self.assemble(tiles, indices)
        timer.lap("paste")

        result = MosaicResult(cropped, segmented, mosaic, cell_colors, indices, grid,
                              timer.timings)
        if compute_metrics:
            result.mse = calculate_mse(cropped, mosaic)
            timer.lap("mse")
            result.ssim = calculate_ssim(cropped, mosaic)
            timer.lap("ssim")
        return result

    @staticmethod
    def assemble(tiles, tile_indices):
        """Place the chosen tile in every cell with one fancy-indexing step.

        ``tiles[tile_indices]`` has shape (rows, cols, s, s, 3); the transpose and
        reshape undo the cell-splitting reshape used for the cell averages.

        Parameters
        ----------
        tiles : numpy.ndarray
            Resized tiles, shape (N, s, s, 3).
        tile_indices : numpy.ndarray
            Tile index per cell, shape (rows, cols).

        Returns
        -------
        numpy.ndarray
            Mosaic of shape (rows * s, cols * s, 3), uint8.
        """
        rows, cols = tile_indices.shape
        s = tiles.shape[1]
        return tiles[tile_indices].transpose(0, 2, 1, 3, 4).reshape(rows * s, cols * s, 3)

    def create_mosaic(self, image, grid_size=None, tile_size=None):
        """Build a mosaic and return only the image.

        Parameters
        ----------
        image : str, pathlib.Path, file-like, PIL.Image.Image or numpy.ndarray
            Input image.
        grid_size : int or tuple of (int, int), optional
            Overrides the builder's default for this call.
        tile_size : int, optional
            Overrides the builder's default for this call.

        Returns
        -------
        numpy.ndarray
            Mosaic of shape (H, W, 3), uint8. ``PIL.Image.fromarray(mosaic)`` makes
            it a PIL image.
        """
        return self.build(image, grid_size, tile_size).mosaic

    def compute_similarity(self, image, mosaic):
        """MSE and SSIM between an input image and its mosaic.

        The mosaic covers a centered crop of the input (whole tiles only), so the
        input is cropped the same way before comparing.

        Parameters
        ----------
        image : str, pathlib.Path, file-like, PIL.Image.Image or numpy.ndarray
            The original input image.
        mosaic : numpy.ndarray or PIL.Image.Image
            Mosaic built from that image.

        Returns
        -------
        dict
            ``{"mse": float, "ssim": float}``.

        Raises
        ------
        InvalidParameterError
            If the mosaic is larger than the image.
        """
        img = load_image(image)
        mosaic = np.asarray(mosaic)
        cropped = center_crop(img, mosaic.shape[0], mosaic.shape[1])
        return {"mse": calculate_mse(cropped, mosaic), "ssim": calculate_ssim(cropped, mosaic)}

    def compare_with_looped(self, result):
        """Time the looped reference search on a result's cells and check it agrees.

        Parameters
        ----------
        result : MosaicResult
            Result of ``build``.

        Returns
        -------
        tuple of (float, bool)
            Looped search time in ms, and whether it chose the same tiles.
        """
        indices, ms = time_call(self.tile_manager.nearest_looped, result.cell_colors)
        return ms, bool(np.array_equal(indices, result.tile_indices))
