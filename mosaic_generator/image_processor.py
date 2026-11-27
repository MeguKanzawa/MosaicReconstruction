"""Image loading, resizing, and grid division.

Everything here is vectorized NumPy: no loops over grid cells or pixels.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from . import config
from .utils import ImageLoadError, InvalidParameterError


# ---------------------------------------------------------------------------
# Loading and conversion
# ---------------------------------------------------------------------------

def load_image(source):
    """Load an image from a path, file object, PIL image or array as RGB.

    Parameters
    ----------
    source : str, pathlib.Path, file-like, PIL.Image.Image or numpy.ndarray
        The image. File-like objects include Streamlit's ``UploadedFile``.
        Grayscale and RGBA inputs are converted to RGB.

    Returns
    -------
    numpy.ndarray
        Array of shape (H, W, 3) and dtype uint8. It may be read-only; copy it
        before modifying it in place.

    Raises
    ------
    ImageLoadError
        If the file is missing or cannot be decoded as an image.
    InvalidParameterError
        If the image is empty or larger than ``config.MAX_IMAGE_PIXELS``.

    Example
    -------
    >>> img = load_image("img/cake4.png")
    >>> img.shape[2]
    3
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise ImageLoadError(f"Image file not found: '{path}'")
        try:
            with Image.open(path) as im:
                arr = to_rgb_array(im)
        except (UnidentifiedImageError, OSError) as e:
            raise ImageLoadError(f"Could not read '{path}' as an image: {e}") from e
    elif hasattr(source, "read"):
        name = getattr(source, "name", "uploaded file")
        if hasattr(source, "seek"):
            source.seek(0)          # the same upload can be read on every rerun
        try:
            arr = to_rgb_array(Image.open(source))
        except (UnidentifiedImageError, OSError) as e:
            raise ImageLoadError(f"Could not read '{name}' as an image: {e}") from e
    else:
        arr = to_rgb_array(source)
    validate_image(arr)
    return arr


def to_rgb_array(image):
    """Convert a PIL image or array to an RGB uint8 array without unnecessary copies.

    Parameters
    ----------
    image : PIL.Image.Image or numpy.ndarray
        Input image. Arrays may be (H, W) grayscale, (H, W, 3) RGB or (H, W, 4) RGBA.

    Returns
    -------
    numpy.ndarray
        Array of shape (H, W, 3) and dtype uint8.

    Raises
    ------
    InvalidParameterError
        If the input is not an image or has an unsupported shape or type.
    """
    if isinstance(image, Image.Image):
        return np.asarray(image if image.mode == "RGB" else image.convert("RGB"))
    if not isinstance(image, np.ndarray):
        raise InvalidParameterError(
            f"Expected a file path, PIL image or NumPy array, got {type(image).__name__}")
    if image.ndim == 3 and image.shape[2] == 3 and image.dtype == np.uint8:
        return image
    if image.dtype != np.uint8 or image.ndim not in (2, 3) or (image.ndim == 3 and image.shape[2] not in (3, 4)):
        raise InvalidParameterError(
            f"Unsupported array: shape {image.shape}, dtype {image.dtype}. "
            "Expected uint8 with shape (H, W), (H, W, 3) or (H, W, 4).")
    return np.asarray(Image.fromarray(image).convert("RGB"))


def validate_image(arr):
    """Check that an RGB array is a usable input image.

    Parameters
    ----------
    arr : numpy.ndarray
        Array of shape (H, W, 3).

    Returns
    -------
    None

    Raises
    ------
    InvalidParameterError
        If the image is empty or larger than ``config.MAX_IMAGE_PIXELS``.
    """
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        raise InvalidParameterError(f"The image is empty ({w}x{h} px).")
    if h * w > config.MAX_IMAGE_PIXELS:
        raise InvalidParameterError(
            f"The image is {w}x{h} px ({h * w / 1e6:.1f} MP); the limit is "
            f"{config.MAX_IMAGE_PIXELS / 1e6:.0f} MP. Resize it first.")


def resize_image(image, size, resample=Image.Resampling.LANCZOS):
    """Resize an image to an exact size.

    Parameters
    ----------
    image : PIL.Image.Image or numpy.ndarray
        Input image.
    size : tuple of (int, int)
        Target (width, height) in pixels.
    resample : PIL.Image.Resampling, optional
        Resampling filter. LANCZOS (default) gives the best quality for photos.

    Returns
    -------
    numpy.ndarray
        Resized image, shape (height, width, 3), dtype uint8.

    Example
    -------
    >>> small = resize_image(np.zeros((100, 200, 3), np.uint8), (50, 25))
    >>> small.shape
    (25, 50, 3)
    """
    w, h = size
    if w < 1 or h < 1:
        raise InvalidParameterError(f"Target size must be positive, got {size}")
    pil = image if isinstance(image, Image.Image) else Image.fromarray(to_rgb_array(image))
    return np.asarray(pil.convert("RGB").resize((int(w), int(h)), resample))


# ---------------------------------------------------------------------------
# Grid planning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GridSpec:
    """Where the mosaic grid sits in the input image.

    Attributes
    ----------
    rows, cols : int
        Number of tiles vertically and horizontally.
    tile_size : int
        Side of each (square) tile in pixels.
    top, left : int
        Offset of the centered crop in the input image.
    """
    rows: int
    cols: int
    tile_size: int
    top: int
    left: int

    @property
    def height(self):
        """Height of the mosaic in pixels.

        Returns
        -------
        int
        """
        return self.rows * self.tile_size

    @property
    def width(self):
        """Width of the mosaic in pixels.

        Returns
        -------
        int
        """
        return self.cols * self.tile_size


def normalize_grid_size(grid_size):
    """Turn a grid size given as an int or a pair into (rows, cols).

    Parameters
    ----------
    grid_size : int or tuple of (int, int)
        Tiles per side, or (rows, cols).

    Returns
    -------
    tuple of (int, int)
        (rows, cols).

    Raises
    ------
    InvalidParameterError
        If the value is not a positive integer or a pair of them.
    """
    if isinstance(grid_size, (int, np.integer)) and not isinstance(grid_size, bool):
        rows = cols = int(grid_size)
    elif isinstance(grid_size, (tuple, list)) and len(grid_size) == 2:
        rows, cols = grid_size
    else:
        raise InvalidParameterError(
            f"grid_size must be an int or a (rows, cols) pair, got {grid_size!r}")
    for name, v in (("rows", rows), ("cols", cols)):
        if not isinstance(v, (int, np.integer)) or isinstance(v, bool) or v < 1:
            raise InvalidParameterError(f"grid_size {name} must be a positive integer, got {v!r}")
    return int(rows), int(cols)


def validate_tile_size(tile_size):
    """Check a tile size in pixels.

    Parameters
    ----------
    tile_size : int
        Side of each tile in pixels.

    Returns
    -------
    int
        The tile size as a Python int.

    Raises
    ------
    InvalidParameterError
        If it is not an integer between ``config.MIN_TILE_SIZE`` and ``config.MAX_TILE_SIZE``.
    """
    if not isinstance(tile_size, (int, np.integer)) or isinstance(tile_size, bool):
        raise InvalidParameterError(f"tile_size must be an integer, got {tile_size!r}")
    if not config.MIN_TILE_SIZE <= tile_size <= config.MAX_TILE_SIZE:
        raise InvalidParameterError(
            f"tile_size must be between {config.MIN_TILE_SIZE} and "
            f"{config.MAX_TILE_SIZE} px, got {tile_size}")
    return int(tile_size)


def compute_grid(image_shape, grid_size=None, tile_size=None):
    """Plan the grid: tile size, number of tiles, and the centered crop.

    Give exactly one of ``grid_size`` or ``tile_size``:

    * ``tile_size``: tiles of that many pixels, in the largest square grid that
      fits (Lab 1 behavior).
    * ``grid_size``: that many tiles, each as large as fits in the image.

    Parameters
    ----------
    image_shape : tuple
        Shape of the image, (H, W) or (H, W, C).
    grid_size : int or tuple of (int, int), optional
        Tiles per side, or (rows, cols).
    tile_size : int, optional
        Side of each tile in pixels.

    Returns
    -------
    GridSpec
        Rows, columns, tile size and crop offset.

    Raises
    ------
    InvalidParameterError
        If both or neither size is given, a size is invalid, or the grid does not
        fit in the image.

    Example
    -------
    >>> compute_grid((512, 600, 3), tile_size=16)
    GridSpec(rows=32, cols=32, tile_size=16, top=0, left=44)
    >>> compute_grid((512, 512, 3), grid_size=(32, 32)).tile_size
    16
    """
    h, w = image_shape[:2]
    if (grid_size is None) == (tile_size is None):
        raise InvalidParameterError("Give exactly one of grid_size or tile_size.")

    if tile_size is not None:
        tile = validate_tile_size(tile_size)
        n = min(h // tile, w // tile)
        if n == 0:
            raise InvalidParameterError(
                f"Tile size {tile} px is larger than the image ({w}x{h} px). "
                f"Use a tile size of at most {min(h, w)} px.")
        rows = cols = n
    else:
        rows, cols = normalize_grid_size(grid_size)
        tile = min(h // rows, w // cols)
        if tile == 0:
            raise InvalidParameterError(
                f"A {rows}x{cols} grid needs an image of at least {cols}x{rows} px, "
                f"but the image is {w}x{h} px. Use a smaller grid.")
        validate_tile_size(tile)

    top = (h - rows * tile) // 2
    left = (w - cols * tile) // 2
    return GridSpec(rows, cols, tile, top, left)


# ---------------------------------------------------------------------------
# Grid division
# ---------------------------------------------------------------------------

def crop_to_grid(img, grid):
    """Centered crop of the image to exactly the grid's area (a view, no copy).

    Parameters
    ----------
    img : numpy.ndarray
        Image of shape (H, W, 3).
    grid : GridSpec
        Grid from ``compute_grid``.

    Returns
    -------
    numpy.ndarray
        View of shape (grid.height, grid.width, 3).
    """
    return img[grid.top:grid.top + grid.height, grid.left:grid.left + grid.width]


def center_crop(img, height, width):
    """Centered crop to a given size, using the same offsets as ``compute_grid``.

    Parameters
    ----------
    img : numpy.ndarray
        Image of shape (H, W, 3).
    height, width : int
        Size of the crop in pixels.

    Returns
    -------
    numpy.ndarray
        View of shape (height, width, 3).

    Raises
    ------
    InvalidParameterError
        If the crop is larger than the image.
    """
    h, w = img.shape[:2]
    if height > h or width > w:
        raise InvalidParameterError(
            f"Cannot crop a {width}x{height} px region from a {w}x{h} px image.")
    top, left = (h - height) // 2, (w - width) // 2
    return img[top:top + height, left:left + width]


def draw_grid(cropped, tile_size, color=config.GRID_LINE_COLOR):
    """Copy of the image with a line between every pair of neighboring tiles.

    Parameters
    ----------
    cropped : numpy.ndarray
        Image already cropped to the grid, shape (H, W, 3).
    tile_size : int
        Tile side in pixels.
    color : tuple of (int, int, int), optional
        RGB color of the lines.

    Returns
    -------
    numpy.ndarray
        New array, same shape as ``cropped``.
    """
    segmented = cropped.copy()
    rgb = np.asarray(color, dtype=np.uint8)
    segmented[tile_size::tile_size, :] = rgb     # horizontal lines
    segmented[:, tile_size::tile_size] = rgb     # vertical lines
    return segmented


def cell_average_colors(cropped, grid):
    """Average RGB color of every grid cell, computed with one reshape.

    The reshape splits each image axis into (cell, pixel within cell). Summing
    over the pixel rows first adds whole contiguous rows at once, which is much
    faster than averaging a transposed array. The uint32 sums are exact, so the
    averages are identical to ``np.mean`` over each cell.

    Parameters
    ----------
    cropped : numpy.ndarray
        Image cropped to the grid, shape (grid.height, grid.width, 3), uint8.
    grid : GridSpec
        Grid from ``compute_grid``.

    Returns
    -------
    numpy.ndarray
        Float array of shape (grid.rows, grid.cols, 3).
    """
    t = grid.tile_size
    blocks = cropped.reshape(grid.rows, t, grid.cols, t, 3)
    sums = blocks.sum(axis=1, dtype=np.uint32).sum(axis=2)
    return sums / (t * t)
