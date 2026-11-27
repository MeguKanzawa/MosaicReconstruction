"""Similarity metrics between an image and its mosaic (MSE, SSIM)."""

import numpy as np
from skimage.metrics import structural_similarity

from . import config
from .utils import InvalidParameterError


def _check_pair(img1, img2):
    """Check that two images can be compared and return them as arrays.

    Parameters
    ----------
    img1, img2 : numpy.ndarray or PIL.Image.Image
        Images of the same shape.

    Returns
    -------
    tuple of (numpy.ndarray, numpy.ndarray)

    Raises
    ------
    InvalidParameterError
        If the shapes differ or the images are empty.
    """
    a, b = np.asarray(img1), np.asarray(img2)
    if a.shape != b.shape:
        raise InvalidParameterError(
            f"Images must have the same shape to be compared, got {a.shape} and {b.shape}. "
            "Compare the mosaic with the cropped input (see MosaicBuilder.compute_similarity).")
    if a.size == 0:
        raise InvalidParameterError("Cannot compare empty images.")
    return a, b


def calculate_mse(img1, img2):
    """Mean squared error between two images (0 = identical; lower is better).

    Computed in one float64 pass plus a dot product; exact for 8-bit images.

    Parameters
    ----------
    img1, img2 : numpy.ndarray or PIL.Image.Image
        Images of the same shape.

    Returns
    -------
    float
        Mean of the squared pixel differences.

    Raises
    ------
    InvalidParameterError
        If the shapes differ.

    Example
    -------
    >>> a = np.zeros((2, 2, 3), np.uint8); b = np.full((2, 2, 3), 2, np.uint8)
    >>> calculate_mse(a, b)
    4.0
    """
    a, b = _check_pair(img1, img2)
    diff = np.subtract(a, b, dtype=np.float64).ravel()
    return float(diff @ diff) / diff.size


def calculate_ssim(img1, img2):
    """Structural similarity (SSIM) between two RGB images (1 = identical).

    Uses scikit-image with a window of up to ``config.SSIM_MAX_WINDOW`` px
    (shrunk to an odd size for small images), averaged over the color channels.

    Parameters
    ----------
    img1, img2 : numpy.ndarray or PIL.Image.Image
        RGB images of the same shape (H, W, 3).

    Returns
    -------
    float
        Mean SSIM in [-1, 1]; 0.0 if the images are smaller than 3 px.

    Raises
    ------
    InvalidParameterError
        If the shapes differ.
    """
    a, b = _check_pair(img1, img2)
    min_dim = min(a.shape[0], a.shape[1])
    win_size = min(config.SSIM_MAX_WINDOW, min_dim if min_dim % 2 else min_dim - 1)
    if win_size < 3:
        return 0.0
    return float(structural_similarity(a, b, channel_axis=2, win_size=win_size))


def compute_metrics(img1, img2):
    """Both similarity metrics at once.

    Parameters
    ----------
    img1, img2 : numpy.ndarray or PIL.Image.Image
        RGB images of the same shape.

    Returns
    -------
    dict
        ``{"mse": float, "ssim": float}``.
    """
    return {"mse": calculate_mse(img1, img2), "ssim": calculate_ssim(img1, img2)}
