"""
Lab 8: optimized mosaic reconstruction tool.

Megu Kanzawa | 11/27/2026

Same inputs, outputs and Streamlit app as lab1.py, restructured for speed:

  1. Vectorized grid operations: the red grid, cell averaging and tile pasting use
     NumPy slicing, reshaping and fancy indexing; no loops over cells or pixels.
  2. Color matching: tile average colors and a k-d tree over them are computed once
     at startup; each call is a single vectorized nearest-neighbor query. The slow
     looped search is no longer run on every call (it is kept as a reference).
  3. Caching: tiles are loaded from disk once and shared across Streamlit reruns.
  4. Resizing: each tile size is resized once and cached, instead of resizing the
     whole library on every call. BILINEAR is kept so mosaics match lab1 exactly.
  5. Quality metrics (MSE, SSIM) are a separate, optional step. MSE uses one pass
     plus a BLAS dot product; SSIM is unchanged (scikit-image).

Run the app:      streamlit run lab8.py
Use as a module:  import lab8; lab8.mosaic_construction(image, tile_size)
"""

import functools
import glob
import time
from dataclasses import dataclass, field

import numpy as np
import streamlit as st
from PIL import Image
from scipy.spatial import cKDTree
from skimage.metrics import structural_similarity as ssim

TILE_FOLDER = "tiles"
RESAMPLE = Image.Resampling.BILINEAR   # same filter as lab1, so the mosaics are identical
GRID_COLOR = np.array([255, 0, 0], dtype=np.uint8)
TOO_LARGE_MSG = "Tile size is too large for this image."

STAGE_LABELS = {
    "to_array": "Convert to array",
    "crop_grid": "Crop + red grid",
    "cell_avg": "Cell averages",
    "search": "Nearest-tile search (k-d tree)",
    "resize": "Resize tiles (cached per size)",
    "paste": "Paste tiles",
    "mse": "MSE",
    "ssim": "SSIM",
    "to_pil": "Convert to PIL",
}


def _running_in_streamlit():
    """True under `streamlit run`, False when imported by tests or a notebook."""
    try:
        from streamlit import runtime
        return runtime.exists()
    except Exception:
        return False


IN_STREAMLIT = _running_in_streamlit()

if IN_STREAMLIT:
    st.set_page_config(page_title="Mosaic Reconstruction Tool", layout="wide")

cache_resource = st.cache_resource(show_spinner=False) if IN_STREAMLIT else functools.cache


# ---------------------------------------------------------------------------
# Tile library: loaded once, features precomputed, resized versions cached
# ---------------------------------------------------------------------------

class TileLibrary:
    """Tile images loaded once, with precomputed average colors, a k-d tree over
    those colors, and a cache of resized tiles per tile size."""

    def __init__(self, folder=TILE_FOLDER):
        # Same file order as lab1, so tile indices can be compared directly.
        paths = glob.glob(f"{folder}/*.png") + glob.glob(f"{folder}/*.jpg")

        self.images = []
        colors = []
        for p in paths:                       # runs once, at startup
            try:
                img = Image.open(p).convert("RGB")
            except Exception as e:
                print(f"Error loading tile {p}: {e}")
                continue
            self.images.append(img)
            colors.append(np.asarray(img).mean(axis=(0, 1)))

        if not self.images:
            raise FileNotFoundError(f"No .png or .jpg tiles found in '{folder}/'")

        self.avg_colors = np.array(colors)        # (N, 3) float64
        self.tree = cKDTree(self.avg_colors)      # nearest-neighbor index over tile colors
        self._resized = {}                        # tile_size -> (N, s, s, 3) uint8

    def __len__(self):
        return len(self.images)

    def resized(self, tile_size):
        """All tiles at tile_size x tile_size as one (N, s, s, 3) array, resized only once."""
        tiles = self._resized.get(tile_size)
        if tiles is None:
            tiles = np.stack([np.asarray(t.resize((tile_size, tile_size), RESAMPLE))
                              for t in self.images])
            self._resized[tile_size] = tiles
        return tiles

    def clear_resize_cache(self):
        """Forget resized tiles (used to measure the cost of a first, uncached call)."""
        self._resized.clear()

    def nearest(self, colors):
        """Index of the closest tile (Euclidean RGB distance) for each color in an (..., 3) array."""
        _, idx = self.tree.query(colors.reshape(-1, 3))
        return idx.reshape(colors.shape[:-1])


@cache_resource
def get_tile_library(folder=TILE_FOLDER):
    return TileLibrary(folder)


TILES = get_tile_library()

# Same names as lab1, for the test suite and existing code.
tile_images_pil = TILES.images
tile_avg_colors = TILES.avg_colors


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

def calculate_mse(img1, img2):
    """Mean squared error. One float64 pass plus a BLAS dot product; exact for 8-bit images."""
    diff = np.subtract(img1, img2, dtype=np.float64).ravel()
    return float(diff @ diff) / diff.size


def calculate_ssim(img1, img2):
    """SSIM between two RGB images (unchanged from lab1)."""
    min_dim = min(img1.shape[0], img1.shape[1])
    win_size = min(7, min_dim if min_dim % 2 != 0 else min_dim - 1)
    if win_size < 3:
        return 0.0
    return ssim(img1, img2, channel_axis=2, win_size=win_size)


# ---------------------------------------------------------------------------
# Mosaic building blocks (all vectorized)
# ---------------------------------------------------------------------------

class TileSizeError(ValueError):
    """Raised when not even one tile fits in the image."""


def to_rgb_array(image):
    """PIL image or array -> (H, W, 3) uint8 array. Grayscale and RGBA are converted."""
    if isinstance(image, Image.Image):
        return np.asarray(image if image.mode == "RGB" else image.convert("RGB"))
    arr = np.asarray(image)
    if arr.ndim == 3 and arr.shape[2] == 3 and arr.dtype == np.uint8:
        return arr
    return np.asarray(Image.fromarray(arr).convert("RGB"))


def center_crop_square(img, tile_size):
    """Largest centered square made of whole tiles. Returns (cropped view, grid_dim)."""
    h, w, _ = img.shape
    grid_dim = min(h // tile_size, w // tile_size)
    if grid_dim == 0:
        raise TileSizeError(TOO_LARGE_MSG)
    side = grid_dim * tile_size
    top, left = (h - side) // 2, (w - side) // 2
    return img[top:top + side, left:left + side], grid_dim


def draw_grid(cropped, tile_size):
    """Copy of the image with a red line every tile_size pixels (two slice assignments)."""
    segmented = cropped.copy()
    segmented[tile_size::tile_size, :] = GRID_COLOR
    segmented[:, tile_size::tile_size] = GRID_COLOR
    return segmented


def cell_average_colors(cropped, grid_dim, tile_size):
    """Average color of every grid cell, shape (grid_dim, grid_dim, 3).

    The reshape splits each axis into (cell, pixel within cell). Summing over the
    pixel rows first adds whole contiguous rows at once, which is much faster than
    averaging a transposed array. uint32 sums are exact (no overflow below 4096 px
    tiles), so the result is bit-identical to lab1's np.mean.
    """
    blocks = cropped.reshape(grid_dim, tile_size, grid_dim, tile_size, 3)
    sums = blocks.sum(axis=1, dtype=np.uint32).sum(axis=2)
    return sums / (tile_size * tile_size)


def assemble_mosaic(resized_tiles, tile_indices):
    """Place the chosen tile in every cell with one fancy-indexing step.

    resized_tiles[tile_indices] has shape (grid, grid, s, s, 3); the transpose and
    reshape are the inverse of the cell-splitting reshape.
    """
    g = tile_indices.shape[0]
    s = resized_tiles.shape[1]
    return resized_tiles[tile_indices].transpose(0, 2, 1, 3, 4).reshape(g * s, g * s, 3)


def find_best_tile(cell_avg_colors):
    """Closest tile for every cell, shape (rows, cols), using the precomputed k-d tree."""
    return TILES.nearest(cell_avg_colors)


def find_best_tile_looped(cell_avg_colors):
    """Reference implementation with explicit loops (from lab1). Not used to build mosaics."""
    rows, cols, _ = cell_avg_colors.shape
    best_indices = np.zeros((rows, cols), dtype=int)
    for r in range(rows):
        for c in range(cols):
            cell_rgb = cell_avg_colors[r, c]
            min_dist = float("inf")
            best_idx = 0
            for idx, tile_rgb in enumerate(tile_avg_colors):
                dist = np.sum((cell_rgb - tile_rgb) ** 2)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx
            best_indices[r, c] = best_idx
    return best_indices


# ---------------------------------------------------------------------------
# Mosaic generation
# ---------------------------------------------------------------------------

@dataclass
class MosaicResult:
    cropped: np.ndarray            # square-cropped input, (D, D, 3)
    segmented: np.ndarray          # cropped input with the red grid drawn on it
    mosaic: np.ndarray             # final mosaic, (D, D, 3)
    cell_avg_colors: np.ndarray    # (grid, grid, 3)
    tile_indices: np.ndarray       # (grid, grid) index of the tile used in each cell
    tile_size: int
    grid_dim: int
    timings: dict = field(default_factory=dict)   # stage key -> ms
    mse: float | None = None
    ssim: float | None = None


def build_mosaic(image, tile_size, compute_metrics=True, tiles=None):
    """Build the mosaic as arrays and record how long each stage took."""
    tiles = TILES if tiles is None else tiles
    tile_size = int(tile_size)
    timings = {}
    last = time.time()

    def lap(stage):
        nonlocal last
        now = time.time()
        timings[stage] = (now - last) * 1000
        last = now

    img = to_rgb_array(image)
    lap("to_array")

    cropped, grid_dim = center_crop_square(img, tile_size)
    segmented = draw_grid(cropped, tile_size)
    lap("crop_grid")

    cell_avg = cell_average_colors(cropped, grid_dim, tile_size)
    lap("cell_avg")

    indices = tiles.nearest(cell_avg)
    lap("search")

    resized = tiles.resized(tile_size)
    lap("resize")

    mosaic = assemble_mosaic(resized, indices)
    lap("paste")

    result = MosaicResult(cropped, segmented, mosaic, cell_avg, indices,
                          tile_size, grid_dim, timings)
    if compute_metrics:
        result.mse = calculate_mse(cropped, mosaic)
        lap("mse")
        result.ssim = calculate_ssim(cropped, mosaic)
        lap("ssim")
    return result


def format_summary(result, total_ms, n_tiles, looped=None):
    d = result.grid_dim * result.tile_size
    lines = [
        "RECONSTRUCTION SUMMARY",
        "----------------------",
        f"Total Processing Time: {total_ms:.2f} ms",
        f"Tile Size: {result.tile_size} x {result.tile_size} px",
        f"Grid Resolution: {result.grid_dim} x {result.grid_dim} tiles ({d} x {d} px total)",
        f"Tile Library Size: {n_tiles} tiles",
        "",
        "STAGE TIMINGS",
        "-------------",
    ]
    lines += [f"{STAGE_LABELS[k]}: {v:.2f} ms" for k, v in result.timings.items()]

    if looped is not None:
        looped_ms, matches = looped
        speedup = looped_ms / max(result.timings["search"], 1e-4)
        lines += ["", "LOOPED SEARCH COMPARISON", "------------------------",
                  f"Looped Time: {looped_ms:.2f} ms",
                  f"k-d Tree Time: {result.timings['search']:.2f} ms",
                  f"Speedup: {speedup:.1f}x faster",
                  f"Same tiles chosen: {'yes' if matches else 'NO'}"]

    lines += ["", "QUALITY METRICS", "---------------"]
    if result.mse is None:
        lines.append("Skipped (quality metrics turned off)")
    else:
        lines += [f"Mean Squared Error (MSE): {result.mse:.2f}",
                  f"Structural Similarity Index (SSIM): {result.ssim:.4f}"]
    return "\n".join(lines)


def mosaic_construction(image, tile_size, compute_metrics=True, compare_looped=False):
    """Drop-in replacement for lab1.mosaic_construction.

    Returns (cropped, segmented, mosaic, summary): three PIL images and a text
    summary, or None for no image. compare_looped=True also times the slow looped
    search for comparison; it is off by default because it is redundant work.
    """
    if image is None:
        return None
    start = time.time()

    try:
        result = build_mosaic(image, tile_size, compute_metrics)
    except TileSizeError:
        original = Image.fromarray(to_rgb_array(image))
        return original, original, original, TOO_LARGE_MSG

    t = time.time()
    outputs = (Image.fromarray(result.cropped),
               Image.fromarray(result.segmented),
               Image.fromarray(result.mosaic))
    result.timings["to_pil"] = (time.time() - t) * 1000
    total_ms = (time.time() - start) * 1000

    looped = None
    if compare_looped:   # timed separately, not part of the total
        t = time.time()
        looped_indices = find_best_tile_looped(result.cell_avg_colors)
        looped = ((time.time() - t) * 1000,
                  np.array_equal(looped_indices, result.tile_indices))

    return (*outputs, format_summary(result, total_ms, len(TILES), looped))


# ---------------------------------------------------------------------------
# Streamlit app (runs only under `streamlit run lab8.py`)
# ---------------------------------------------------------------------------

def main():
    st.title("Mosaic Reconstruction Tool")
    st.markdown("Upload an image and adjust the tile size slider to view dynamic "
                "square mosaic reconstruction.")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
        tile_size = st.slider("Tile Size (px)", min_value=8, max_value=128, value=32, step=8)
        compute_metrics = st.checkbox("Compute quality metrics (MSE, SSIM)", value=True)
        compare_looped = st.checkbox("Compare with looped tile search", value=False)

    with col_right:
        if uploaded_file is None:
            st.info("Upload an image in the left panel to begin reconstruction.")
            return

        cropped, segmented, mosaic, summary = mosaic_construction(
            Image.open(uploaded_file), tile_size, compute_metrics, compare_looped)

        if summary == TOO_LARGE_MSG:
            st.warning(summary)
            return

        img_col1, img_col2, img_col3 = st.columns(3)
        with img_col1:
            st.image(cropped, caption="Square Crop", use_container_width=True)
        with img_col2:
            st.image(segmented, caption="Segmented Grid Overlay", use_container_width=True)
        with img_col3:
            st.image(mosaic, caption="Final Mosaic", use_container_width=True)

        st.text_area("Performance & Quality Metrics", value=summary, height=320)


if IN_STREAMLIT:
    main()