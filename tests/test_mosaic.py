"""Unit tests for the mosaic_generator package.

Run from the project folder:  pytest tests/ -v

The tests build their own small tile library in a temporary folder, so they do
not depend on tiles/ or on any image files.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # project folder

from mosaic_generator import (ImageLoadError, InvalidParameterError, MosaicBuilder,  # noqa: E402
                              TileLoadError, TileManager, calculate_mse, calculate_ssim)
from mosaic_generator.image_processor import (cell_average_colors, compute_grid,  # noqa: E402
                                              crop_to_grid, draw_grid, load_image)

# Solid-color tiles: their average colors are known exactly.
TILE_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (0, 0, 0),
               (128, 128, 128), (255, 255, 0), (0, 255, 255)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tile_dir(tmp_path_factory):
    """Folder with 8 solid-color tiles of different sizes and one broken file."""
    folder = tmp_path_factory.mktemp("tiles")
    for i, color in enumerate(TILE_COLORS):
        Image.new("RGB", (20 + i, 20 + i), color).save(folder / f"tile_{i}.png")
    (folder / "broken.png").write_text("this is not an image")
    return folder


@pytest.fixture(scope="module")
def tiles(tile_dir):
    return TileManager(tile_directory=tile_dir)


@pytest.fixture(scope="module")
def photo():
    """Deterministic 300x200 RGB test image with structure and noise."""
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:200, 0:300]
    img = np.stack([x * 255 / 300, y * 255 / 200, (1 - x / 300) * 255], axis=-1)
    img += rng.normal(0, 20, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def naive_mosaic(img, tile_size, tiles):
    """Reference implementation with explicit loops, for checking the fast version."""
    h, w, _ = img.shape
    n = min(h // tile_size, w // tile_size)
    top, left = (h - n * tile_size) // 2, (w - n * tile_size) // 2
    crop = img[top:top + n * tile_size, left:left + n * tile_size]
    resized = tiles.resized(tile_size)
    out = np.zeros_like(crop)
    for r in range(n):
        for c in range(n):
            cell = crop[r * tile_size:(r + 1) * tile_size, c * tile_size:(c + 1) * tile_size]
            color = cell.reshape(-1, 3).mean(axis=0)
            best = int(np.argmin(((tiles.avg_colors - color) ** 2).sum(axis=1)))
            out[r * tile_size:(r + 1) * tile_size, c * tile_size:(c + 1) * tile_size] = resized[best]
    return out


# ---------------------------------------------------------------------------
# TileManager
# ---------------------------------------------------------------------------

def test_loads_tiles_and_skips_unreadable_files(tiles):
    assert len(tiles) == len(TILE_COLORS)
    assert [p.name for p, _ in tiles.skipped] == ["broken.png"]
    assert tiles.avg_colors.shape == (len(TILE_COLORS), 3)


def test_average_colors_are_tile_features(tiles):
    colors = {tuple(int(v) for v in c) for c in tiles.avg_colors}
    assert colors == set(TILE_COLORS)


def test_missing_tile_folder_raises(tmp_path):
    with pytest.raises(TileLoadError, match="does not exist"):
        TileManager(tile_directory=tmp_path / "nope")


def test_folder_without_readable_tiles_raises(tmp_path):
    (tmp_path / "bad.png").write_text("not an image")
    with pytest.raises(TileLoadError, match="No readable tiles"):
        TileManager(tile_directory=tmp_path)


def test_kdtree_search_matches_looped_search(tiles):
    colors = np.random.default_rng(1).uniform(0, 255, (12, 9, 3))
    np.testing.assert_array_equal(tiles.nearest(colors), tiles.nearest_looped(colors))


def test_resized_tiles_are_cached(tiles):
    first = tiles.resized(16)
    assert first.shape == (len(tiles), 16, 16, 3)
    assert tiles.resized(16) is first
    tiles.clear_cache()
    assert tiles.resized(16) is not first


# ---------------------------------------------------------------------------
# image_processor
# ---------------------------------------------------------------------------

def test_grid_from_tile_size_is_lab1_square_crop():
    grid = compute_grid((200, 300, 3), tile_size=16)
    assert (grid.rows, grid.cols, grid.tile_size) == (12, 12, 16)
    assert (grid.top, grid.left) == (4, 54)


def test_grid_from_grid_size_square_and_rectangular():
    assert compute_grid((512, 512, 3), grid_size=(32, 32)).tile_size == 16
    grid = compute_grid((200, 300, 3), grid_size=(10, 20))
    assert (grid.rows, grid.cols, grid.tile_size) == (10, 20, 15)
    assert (grid.height, grid.width) == (150, 300)


@pytest.mark.parametrize("kwargs, message", [
    ({"tile_size": 500}, "larger than the image"),
    ({"grid_size": 400}, "Use a smaller grid"),
    ({"tile_size": 0}, "between"),
    ({"grid_size": (0, 4)}, "positive integer"),
    ({"grid_size": "big"}, "int or a"),
    ({}, "exactly one"),
    ({"grid_size": 8, "tile_size": 8}, "exactly one"),
])
def test_invalid_grid_parameters_raise(kwargs, message):
    with pytest.raises(InvalidParameterError, match=message):
        compute_grid((200, 300, 3), **kwargs)


def test_cell_averages_match_per_cell_mean(photo):
    grid = compute_grid(photo.shape, grid_size=(5, 7))
    crop = crop_to_grid(photo, grid)
    t = grid.tile_size
    expected = np.array([[crop[r * t:(r + 1) * t, c * t:(c + 1) * t].mean(axis=(0, 1))
                          for c in range(grid.cols)] for r in range(grid.rows)])
    np.testing.assert_array_equal(cell_average_colors(crop, grid), expected)


def test_grid_lines_drawn_between_tiles_only():
    seg = draw_grid(np.zeros((40, 40, 3), np.uint8), 10)
    red_rows = [r for r in range(40) if (seg[r, :] == (255, 0, 0)).all()]
    assert red_rows == [10, 20, 30]


def test_load_image_errors(tmp_path):
    with pytest.raises(ImageLoadError, match="not found"):
        load_image(tmp_path / "missing.png")
    (tmp_path / "fake.png").write_text("text")
    with pytest.raises(ImageLoadError, match="Could not read"):
        load_image(tmp_path / "fake.png")
    with pytest.raises(InvalidParameterError, match="Unsupported array"):
        load_image(np.zeros((10, 10, 2), np.uint8))


def test_grayscale_and_rgba_inputs_become_rgb():
    assert load_image(np.zeros((10, 12), np.uint8)).shape == (10, 12, 3)
    assert load_image(Image.new("RGBA", (12, 10))).shape == (10, 12, 3)


# ---------------------------------------------------------------------------
# MosaicBuilder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tile_size", [4, 10, 16, 33])
def test_mosaic_matches_naive_reference(tiles, photo, tile_size):
    builder = MosaicBuilder(tiles, tile_size=tile_size)
    np.testing.assert_array_equal(builder.create_mosaic(photo), naive_mosaic(photo, tile_size, tiles))


def test_example_usage_from_assignment(tiles, photo):
    builder = MosaicBuilder(tiles, grid_size=(32, 32))
    mosaic = builder.create_mosaic(Image.fromarray(photo))
    assert mosaic.shape == (192, 192, 3)          # 32 tiles x 6 px
    similarity = builder.compute_similarity(Image.fromarray(photo), mosaic)
    assert similarity["mse"] >= 0 and -1 <= similarity["ssim"] <= 1


def test_image_made_of_tiles_is_reconstructed_exactly(tiles):
    rng = np.random.default_rng(2)
    choice = rng.integers(0, len(TILE_COLORS), (6, 8))
    image = np.array(TILE_COLORS, dtype=np.uint8)[choice].repeat(10, axis=0).repeat(10, axis=1)
    result = MosaicBuilder(tiles).build(image, grid_size=(6, 8), compute_metrics=True)
    np.testing.assert_array_equal(result.mosaic, image)
    assert result.mse == 0.0 and math.isclose(result.ssim, 1.0)


def test_build_records_all_stage_timings(tiles, photo):
    result = MosaicBuilder(tiles).build(photo, tile_size=16, compute_metrics=True)
    assert list(result.timings) == ["load", "crop_grid", "cell_avg", "search",
                                    "resize", "paste", "mse", "ssim"]
    assert result.total_ms >= result.generation_ms > 0


def test_compare_with_looped_agrees(tiles, photo):
    builder = MosaicBuilder(tiles)
    ms, same = builder.compare_with_looped(builder.build(photo, tile_size=20))
    assert same and ms > 0


def test_builder_rejects_bad_arguments(tiles):
    with pytest.raises(InvalidParameterError, match="TileManager"):
        MosaicBuilder("tiles/")
    with pytest.raises(InvalidParameterError, match="not both"):
        MosaicBuilder(tiles, grid_size=8, tile_size=8)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def test_metrics_for_identical_and_different_images(photo):
    assert calculate_mse(photo, photo) == 0.0
    assert math.isclose(calculate_ssim(photo, photo), 1.0)
    shifted = np.clip(photo.astype(int) + 10, 0, 255).astype(np.uint8)
    assert calculate_mse(photo, shifted) > 0
    assert calculate_ssim(photo, shifted) < 1


def test_metrics_reject_different_shapes(photo):
    with pytest.raises(InvalidParameterError, match="same shape"):
        calculate_mse(photo, photo[:100])
