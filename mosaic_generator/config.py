"""Configuration constants for the mosaic generator.

Change values here rather than in the code that uses them.
"""

from PIL import Image

# --- Tiles -----------------------------------------------------------------
# Folder of tile images, relative to the working directory (as in Lab 1).
TILE_DIRECTORY = "tiles"

# File patterns loaded from the tile folder, in this order. Same as Lab 1, so tile
# indices match the baseline exactly; add "*.jpeg" here to load .jpeg tiles too.
TILE_PATTERNS = ("*.png", "*.jpg")

# Filter used to resize tiles. BILINEAR matches Lab 1, so mosaics are identical.
RESAMPLE = Image.Resampling.BILINEAR

# --- Grid ------------------------------------------------------------------
# Default grid: number of tiles per side, as (rows, cols).
DEFAULT_GRID_SIZE = (32, 32)

# Default tile size in pixels (the web app's slider starts here, as in Lab 1).
DEFAULT_TILE_SIZE = 32

# Allowed tile sizes in pixels. Cell sums are kept as exact uint32 values, which
# cannot overflow for tiles up to 4096 x 4096 px.
MIN_TILE_SIZE = 1
MAX_TILE_SIZE = 4096

# Largest input image accepted, in pixels (guards against running out of memory).
MAX_IMAGE_PIXELS = 50_000_000

# Color of the grid lines drawn on the "segmented" preview (RGB).
GRID_LINE_COLOR = (255, 0, 0)

# --- Metrics ---------------------------------------------------------------
# Largest SSIM window (must be odd); smaller images use a smaller odd window.
SSIM_MAX_WINDOW = 7

# --- Web app ---------------------------------------------------------------
APP_TITLE = "Mosaic Reconstruction Tool"
SLIDER_MIN = 8
SLIDER_MAX = 128
SLIDER_STEP = 8

# Example images offered in the web app, relative to the project folder.
EXAMPLE_DIRECTORY = "img"
EXAMPLE_EXTENSIONS = (".png", ".jpg", ".jpeg")
DEFAULT_EXAMPLE = "cake4.png"
