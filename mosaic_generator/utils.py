"""Helper functions and classes shared by the other modules: error types,
a stage timer, and summary formatting."""

import time


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MosaicError(Exception):
    """Base class for every error raised by the mosaic_generator package."""


class ImageLoadError(MosaicError):
    """An input image could not be opened or decoded."""


class TileLoadError(MosaicError):
    """The tile folder is missing or contains no readable tiles."""


class InvalidParameterError(MosaicError, ValueError):
    """A parameter (image, grid size or tile size) is invalid."""


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

class StageTimer:
    """Records how long consecutive stages of a computation take.

    Uses ``time.perf_counter``, the highest-resolution clock for measuring
    durations.

    Example
    -------
        timer = StageTimer()
        # ... first stage ...
        timer.lap("load")
        # ... second stage ...
        timer.lap("process")
        sorted(timer.timings)
    ['load', 'process']
    """

    def __init__(self):
        """Start the timer.

        Returns
        -------
        None
        """
        self.timings = {}
        self._start = self._last = time.perf_counter()

    def lap(self, stage):
        """Record the time since the previous lap (or the start) under a stage name.

        Parameters
        ----------
        stage : str
            Name of the stage that just finished.

        Returns
        -------
        float
            Duration of the stage in milliseconds.
        """
        now = time.perf_counter()
        ms = (now - self._last) * 1000
        self.timings[stage] = ms
        self._last = now
        return ms

    @property
    def total_ms(self):
        """Milliseconds since the timer started.

        Returns
        -------
        float
            Elapsed time in milliseconds.
        """
        return (time.perf_counter() - self._start) * 1000


def time_call(fn, *args, **kwargs):
    """Call a function once and measure how long it takes.

    Parameters
    ----------
    fn : callable
        Function to call.
    *args, **kwargs
        Arguments passed to ``fn``.

    Returns
    -------
    tuple of (object, float)
        The function's return value and the elapsed time in milliseconds.

    Example
    -------
    >>> value, ms = time_call(sum, [1, 2, 3])
    >>> value
    6
    """
    start = time.perf_counter()
    value = fn(*args, **kwargs)
    return value, (time.perf_counter() - start) * 1000


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    "load": "Load image",
    "crop_grid": "Crop + grid overlay",
    "cell_avg": "Cell averages",
    "search": "Nearest-tile search (k-d tree)",
    "resize": "Resize tiles (cached per size)",
    "paste": "Paste tiles",
    "mse": "MSE",
    "ssim": "SSIM",
}


def stage_label(key):
    """Human-readable name of a timing stage.

    Parameters
    ----------
    key : str
        Stage key, e.g. ``"search"``.

    Returns
    -------
    str
        Label for tables and summaries (the key itself if it is not known).
    """
    return STAGE_LABELS.get(key, key)


def format_summary(result, n_tiles, looped=None):
    """Plain-text summary of a mosaic run, like the Lab 1 metrics box.

    Parameters
    ----------
    result : mosaic_generator.mosaic_builder.MosaicResult
        Result returned by ``MosaicBuilder.build``.
    n_tiles : int
        Number of tiles in the library.
    looped : tuple of (float, bool), optional
        Time of the looped reference search in ms, and whether it chose the same
        tiles as the k-d tree. Omitted from the summary when None.

    Returns
    -------
    str
        Multi-line summary text.
    """
    g = result.grid
    lines = [
        "RECONSTRUCTION SUMMARY",
        "----------------------",
        f"Total Processing Time: {result.total_ms:.2f} ms",
        f"Tile Size: {g.tile_size} x {g.tile_size} px",
        f"Grid Resolution: {g.rows} x {g.cols} tiles ({g.width} x {g.height} px total)",
        f"Tile Library Size: {n_tiles} tiles",
        "",
        "STAGE TIMINGS",
        "-------------",
    ]
    lines += [f"{stage_label(k)}: {v:.2f} ms" for k, v in result.timings.items()]

    if looped is not None:
        looped_ms, same = looped
        speedup = looped_ms / max(result.timings["search"], 1e-4)
        lines += ["", "LOOPED SEARCH COMPARISON", "------------------------",
                  f"Looped Time: {looped_ms:.2f} ms",
                  f"k-d Tree Time: {result.timings['search']:.2f} ms",
                  f"Speedup: {speedup:.1f}x faster",
                  f"Same tiles chosen: {'yes' if same else 'NO'}"]

    lines += ["", "QUALITY METRICS", "---------------"]
    if result.mse is None:
        lines.append("Skipped (quality metrics turned off)")
    else:
        lines += [f"Mean Squared Error (MSE): {result.mse:.2f}",
                  f"Structural Similarity Index (SSIM): {result.ssim:.4f}"]
    return "\n".join(lines)
