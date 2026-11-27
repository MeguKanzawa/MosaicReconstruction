"""Tile loading, caching, and feature extraction."""

import glob
import logging
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError
from scipy.spatial import cKDTree

from . import config
from .image_processor import validate_tile_size
from .utils import InvalidParameterError, TileLoadError

logger = logging.getLogger(__name__)


class TileManager:
    """Loads the tile library once and answers "which tile is closest to this color?".

    On creation it reads every tile from disk, computes each tile's average color
    (its feature) and builds a k-d tree over those colors. Resized copies of the
    tiles are cached per tile size, so each size is resized only once.

    Parameters
    ----------
    tile_directory : str or pathlib.Path, optional
        Folder of tile images. Defaults to ``config.TILE_DIRECTORY``.
    patterns : tuple of str, optional
        Glob patterns of the files to load, in order. Defaults to ``config.TILE_PATTERNS``.
    resample : PIL.Image.Resampling, optional
        Filter used to resize tiles. Defaults to ``config.RESAMPLE``.

    Attributes
    ----------
    images : list of PIL.Image.Image
        The loaded tiles, in RGB.
    paths : list of pathlib.Path
        File of each loaded tile, in the same order.
    avg_colors : numpy.ndarray
        Average RGB color of each tile, shape (N, 3), float64.
    skipped : list of tuple of (pathlib.Path, str)
        Files that could not be read, with the reason.

    Raises
    ------
    TileLoadError
        If the folder does not exist or contains no readable tiles.

    Example
    -------
        tiles = TileManager(tile_directory="tiles/")
        len(tiles) > 0
    True
        tiles.nearest(np.array([[255.0, 0.0, 0.0]]))   # index of the reddest tile
    array([...])
    """

    def __init__(self, tile_directory=config.TILE_DIRECTORY, patterns=config.TILE_PATTERNS,
                 resample=config.RESAMPLE):
        """Load all tiles and precompute their features (see the class docstring)."""
        self.directory = Path(tile_directory)
        self.resample = resample
        if not self.directory.is_dir():
            raise TileLoadError(
                f"Tile folder '{self.directory}' does not exist "
                f"(looked in {self.directory.resolve()}).")

        self.images, self.paths, self.skipped = [], [], []
        colors = []
        for path in self._find_files(patterns):          # runs once, at startup
            try:
                with Image.open(path) as im:
                    img = im.convert("RGB")
                if img.width == 0 or img.height == 0:
                    raise ValueError("image is empty")
            except (UnidentifiedImageError, OSError, ValueError) as e:
                logger.warning("Skipping unreadable tile %s: %s", path, e)
                self.skipped.append((path, str(e)))
                continue
            self.images.append(img)
            self.paths.append(path)
            colors.append(self.average_color(img))

        if not self.images:
            detail = f" ({len(self.skipped)} file(s) could not be read)" if self.skipped else ""
            raise TileLoadError(
                f"No readable tiles matching {', '.join(patterns)} in "
                f"'{self.directory}'{detail}.")

        self.avg_colors = np.array(colors)            # (N, 3) float64
        self._tree = cKDTree(self.avg_colors)         # built once
        self._resized = {}                            # tile_size -> (N, s, s, 3) uint8
        logger.info("Loaded %d tiles from %s (%d skipped)",
                    len(self.images), self.directory, len(self.skipped))

    def _find_files(self, patterns):
        """List tile files, pattern by pattern, in file-system order (as Lab 1's glob).

        Parameters
        ----------
        patterns : tuple of str
            Glob patterns such as ``"*.png"``.

        Returns
        -------
        list of pathlib.Path
        """
        files = []
        for pattern in patterns:
            files += [Path(p) for p in glob.glob(str(self.directory / pattern)) if Path(p).is_file()]
        return files

    @staticmethod
    def average_color(img):
        """Average RGB color of an image (the feature used for matching).

        Parameters
        ----------
        img : PIL.Image.Image
            RGB image.

        Returns
        -------
        numpy.ndarray
            Shape (3,), float64.
        """
        return np.asarray(img).mean(axis=(0, 1))

    def __len__(self):
        """Number of tiles in the library.

        Returns
        -------
        int
        """
        return len(self.images)

    def resized(self, tile_size):
        """All tiles at ``tile_size`` x ``tile_size`` px, resized once and then cached.

        Parameters
        ----------
        tile_size : int
            Side of each tile in pixels.

        Returns
        -------
        numpy.ndarray
            Shape (N, tile_size, tile_size, 3), dtype uint8. Do not modify it: the
            same array is returned on every call.
        """
        tile_size = validate_tile_size(tile_size)
        tiles = self._resized.get(tile_size)
        if tiles is None:
            tiles = np.stack([np.asarray(t.resize((tile_size, tile_size), self.resample))
                              for t in self.images])
            tiles.flags.writeable = False
            self._resized[tile_size] = tiles
        return tiles

    def clear_cache(self):
        """Forget all resized tiles (e.g. to measure the cost of a first, uncached call).

        Returns
        -------
        None
        """
        self._resized.clear()

    def nearest(self, colors):
        """Index of the closest tile for each color, using the k-d tree.

        Distance is Euclidean in RGB space, the same as the Lab 1 search.

        Parameters
        ----------
        colors : numpy.ndarray
            Colors of shape (..., 3), e.g. (rows, cols, 3) cell averages.

        Returns
        -------
        numpy.ndarray
            Integer tile indices with shape ``colors.shape[:-1]``.

        Raises
        ------
        InvalidParameterError
            If the last axis is not of length 3.
        """
        colors = np.asarray(colors, dtype=np.float64)
        if colors.ndim < 1 or colors.shape[-1] != 3:
            raise InvalidParameterError(f"colors must have shape (..., 3), got {colors.shape}")
        _, idx = self._tree.query(colors.reshape(-1, 3))
        return idx.reshape(colors.shape[:-1])

    def nearest_looped(self, colors):
        """Reference search with explicit Python loops (the Lab 1 baseline).

        Much slower than ``nearest``; kept to verify it and to measure the speedup.

        Parameters
        ----------
        colors : numpy.ndarray
            Cell colors of shape (rows, cols, 3).

        Returns
        -------
        numpy.ndarray
            Integer tile indices of shape (rows, cols).
        """
        rows, cols, _ = colors.shape
        best_indices = np.zeros((rows, cols), dtype=int)
        for r in range(rows):
            for c in range(cols):
                cell_rgb = colors[r, c]
                min_dist = float("inf")
                best_idx = 0
                for idx, tile_rgb in enumerate(self.avg_colors):
                    dist = np.sum((cell_rgb - tile_rgb) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = idx
                best_indices[r, c] = best_idx
        return best_indices
