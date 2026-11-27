# Mosaic Generator

Turns a photo into a mosaic made of small tile images. Each grid cell of the photo is replaced by the tile whose average color is closest to it.

This is the Lab 8 version: the Lab 1 single-file app, optimized for speed and refactored into a package (`mosaic_generator`) with a Streamlit web interface.

**Live app:** <https://mugk-mosaicreconstruction.streamlit.app/>

## Project structure

```text
mosaic_generator/
├── __init__.py          # Exports MosaicBuilder, TileManager, metrics and error types
├── image_processor.py   # Image loading, validation, resizing, grid planning and division
├── tile_manager.py      # TileManager: tile loading, caching, features, nearest-tile search
├── mosaic_builder.py    # MosaicBuilder: the reconstruction algorithm
├── metrics.py           # MSE and SSIM
├── config.py            # Configuration constants
└── utils.py             # Error types, stage timer, summary formatting
app.py                   # Streamlit web interface
tiles/                   # Tile images (.png, .jpg)
tests/test_mosaic.py     # Unit tests
requirements.txt
```

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/MeguKanzawa/MosaicReconstruction.git
cd MosaicReconstruction
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Put your tile images in `tiles/` (PNG or JPG, any size).

## Usage

### Web app

```bash
streamlit run app.py
```

Then open the address Streamlit prints (normally <http://localhost:8501>). Pick one of the bundled example images (from `img/`, default `cake4.png`) or upload your own, choose a tile size in pixels or a grid size in tiles per side, and the app shows:

- the square crop of the input, the crop with the grid drawn on it, and the mosaic;
- processing time: total, mosaic generation, and quality metrics, plus a per-stage table;
- MSE and SSIM between the crop and the mosaic (optional: SSIM is the slowest step);
- optionally, the speed of the k-d tree tile search compared with the original looped search.

### Python

```python
from mosaic_generator import MosaicBuilder, TileManager

tile_manager = TileManager(tile_directory="tiles/")       # loads tiles once
builder = MosaicBuilder(tile_manager, grid_size=(32, 32))

mosaic = builder.create_mosaic("img/cake4.png")            # NumPy array (H, W, 3)
similarity = builder.compute_similarity("img/cake4.png", mosaic)
print(similarity)                                          # {'mse': ..., 'ssim': ...}
```

Inputs can be a file path, a PIL image, a NumPy array or an uploaded file. More options:

```python
from PIL import Image

builder.create_mosaic(image, tile_size=16)          # 16 px tiles, largest square grid (Lab 1 behavior)
builder.create_mosaic(image, grid_size=(20, 40))    # 20 rows x 40 columns
Image.fromarray(mosaic).save("mosaic.png")

result = builder.build(image, tile_size=16, compute_metrics=True)
result.mosaic, result.tile_indices, result.mse, result.ssim
result.timings          # {'load': 0.4, 'crop_grid': 0.3, ...} in ms
```

Invalid input raises an error with an explanation, all subclasses of `MosaicError`:

```python
from mosaic_generator import InvalidParameterError

try:
    builder.create_mosaic(image, tile_size=5000)
except InvalidParameterError as e:
    print(e)   # Tile size 5000 px is larger than the image (512x512 px). Use a tile size of at most 512 px.
```

Unreadable tile files are skipped with a warning and listed in `tile_manager.skipped`. A missing tile folder, or one with no readable tiles, raises `TileLoadError`.

### Tests

```bash
pip install pytest
pytest tests/ -v
```

The tests create their own tile library in a temporary folder. Among other things, they check that the fast mosaic matches a straightforward loop-based implementation pixel for pixel.

## Performance

Measured with `profiling_analysis.ipynb` (Part 5) on an Apple M4 Pro, with a library of 14 tiles. Times are the mean of 3 runs after a warm-up run.

The baseline is my own Lab 1 code (`lab1.py`), whose pipeline runs the looped tile search (`find_best_tile_looped`) on every call. Mosaic generation excludes the quality metrics; end to end includes MSE and SSIM.

**Mosaic generation**

| Image | Grid | Baseline (s) | Lab 8 (s) | Speedup |
|---|---|---|---|---|
| 256 × 256 | 16 × 16 | 0.0284 | 0.0005 | 57.4× |
| 512 × 512 | 32 × 32 | 0.0572 | 0.0014 | 40.8× |
| 1024 × 1024 | 64 × 64 | 0.1627 | 0.0054 | 30.2× |

**End to end (with MSE and SSIM)**

| Image | Grid | Baseline (s) | Lab 8 (s) | Speedup |
|---|---|---|---|---|
| 256 × 256 | 16 × 16 | 0.0429 | 0.0145 | 3.0× |
| 512 × 512 | 32 × 32 | 0.1362 | 0.0858 | 1.6× |
| 1024 × 1024 | 64 × 64 | 0.6736 | 0.4672 | 1.4× |

The tile search alone (looped search to k-d tree) is 96–116× faster. Full tables are in `perf_results/`.

Correctness: Lab 8 assigns the same tile as the baseline to 100% of cells in all 9 configurations, and the MSE between the two mosaics is 0.0 (pixel-identical).

Where the speed comes from:

- **Tile search:** a k-d tree over the tile colors, built once, replaces a triple Python loop over cells and tiles.
- **Vectorized grid operations:** cell averages, grid lines and tile placement use NumPy reshaping, slicing and fancy indexing, with no loops over cells or pixels.
- **Caching:** tiles are loaded once per server; resized tiles are cached per tile size.
- **Metrics:** MSE takes a single pass. SSIM (scikit-image) is unchanged and is now optional. It is the slowest remaining step, so end-to-end speedups are smaller than mosaic-generation speedups.

## Configuration

Defaults live in `mosaic_generator/config.py`: tile folder and file types, resize filter, default grid and tile size, allowed tile sizes, maximum image size, grid line color, SSIM window and the web app's slider range.

## Why Streamlit

*(Adjust to your situation.)* The web interface uses Streamlit, as in Lab 1. It reruns the script on every slider move, which suits a live preview, and `st.cache_resource` keeps the tile library in memory across reruns, so tiles are read from disk only once.

## Deployment (Streamlit Community Cloud)

1. Push the project to a public GitHub repository, including `tiles/` and `requirements.txt`.
2. At <https://share.streamlit.io>, choose **Create app**, pick the repository and branch, and set the main file to `app.py`.
3. Deploy, then put the app's URL at the top of this README.
