# """
# Test suite for lab1.py mosaic reconstruction at multiple image sizes.

# Run the tests:        pytest test_lab8.py -v
# Run the benchmark:    python test_lab8.py
# """

# import os
# import re
# from pathlib import Path

# import numpy as np
# import pytest
# from PIL import Image

# # lab1.py loads tiles from the relative "tiles/" folder, so make sure we run
# # from the project directory before importing it.
# PROJECT_DIR = Path(__file__).resolve().parent
# os.chdir(PROJECT_DIR)

# # imports lab1 to run all Streamlit calls
# import lab1  

# IMAGE_SIZES = [256, 512, 1024]
# TILE_SIZES = [8, 16, 32, 64]
# TEST_IMAGE_DIR = PROJECT_DIR / "test_images"
# SOURCE_IMAGE = PROJECT_DIR / "img" / "cake4.png"


# # ---------------------------------------------------------------------------
# # Test image generation
# # ---------------------------------------------------------------------------

# # resizes img/cake4.png to 256, 512, 1024 squares
# def make_test_image(size):
#     """Resize a real photo to size x size if available, else use a synthetic one."""
#     if SOURCE_IMAGE.exists():
#         return Image.open(SOURCE_IMAGE).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
#     raise FileNotFoundError("img/cake4.png not found")

# # saves the results of make_test_images into 
# # test_images/test_<size>x<size>.png
# def generate_test_images():
#     """Write test_images/test_<size>.png for every size (also handy for manual UI testing)."""
#     TEST_IMAGE_DIR.mkdir(exist_ok=True)
#     paths = {}
#     for size in IMAGE_SIZES:
#         path = TEST_IMAGE_DIR / f"test_{size}x{size}.png"
#         if not path.exists():
#             make_test_image(size).save(path)
#         paths[size] = path
#     return paths


# @pytest.fixture(scope="session")
# def test_images():
#     """Maps size -> PIL image, loaded from test_images/ (generated on first run)."""
#     return {size: Image.open(p).convert("RGB") for size, p in generate_test_images().items()}


# # ---------------------------------------------------------------------------
# # Tests
# # ---------------------------------------------------------------------------

# # at least one tile loaded, color array in (N,3) shape
# def test_tiles_loaded():
#     assert len(lab1.tile_images_pil) > 0, "No tiles found in tiles/"
#     assert lab1.tile_avg_colors.shape == (len(lab1.tile_images_pil), 3)

# # each test image really is size x size
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# def test_generated_image_has_expected_size(test_images, size):
#     assert test_images[size].size == (size, size)

# # all output images have (size // tile) * tile
# # summary reports right grid
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# @pytest.mark.parametrize("tile_size", TILE_SIZES)
# def test_output_dimensions(test_images, size, tile_size):
#     cropped, segmented, mosaic, summary = lab1.mosaic_construction(test_images[size], tile_size)

#     expected = (size // tile_size) * tile_size
#     for out in (cropped, segmented, mosaic):
#         assert isinstance(out, Image.Image)
#         assert out.size == (expected, expected)
#     assert f"Grid Resolution: {size // tile_size} x {size // tile_size}" in summary

# # MSE >= 0, -1 <= SSIM <= 1, summary containts metric labels
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# @pytest.mark.parametrize("tile_size", TILE_SIZES)
# def test_quality_metrics_in_valid_range(test_images, size, tile_size):
#     cropped, _, mosaic, summary = lab1.mosaic_construction(test_images[size], tile_size)
#     a, b = np.array(cropped), np.array(mosaic)

#     mse = lab1.calculate_mse(a, b)
#     ssim = lab1.calculate_ssim(a, b)
#     assert mse >= 0
#     assert -1.0 <= ssim <= 1.0
#     assert "Mean Squared Error" in summary and "SSIM" in summary

# # both searches pick identical tiles, cell averages computes 
# # independently using reshape().mean(axis=1,3)
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# @pytest.mark.parametrize("tile_size", [16, 32])
# def test_vectorized_matches_looped(test_images, size, tile_size):
#     """The vectorized nearest-tile search must pick the same tiles as the loop."""
#     arr = np.array(test_images[size])
#     g = size // tile_size
#     crop = arr[: g * tile_size, : g * tile_size]
#     cell_avg = crop.reshape(g, tile_size, g, tile_size, 3).mean(axis=(1, 3))

#     vec = lab1.find_best_tile(cell_avg)
#     loop = lab1.find_best_tile_looped(cell_avg)
#     assert vec.shape == (g, g)
#     np.testing.assert_array_equal(vec, loop)

# # raw numpy array works as input
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# def test_numpy_array_input(test_images, size):
#     """mosaic_construction should also accept a raw numpy array."""
#     _, _, mosaic, _ = lab1.mosaic_construction(np.array(test_images[size]), 32)
#     assert mosaic.size == (size, size)

# # error message raised when tile > image
# @pytest.mark.parametrize("size", IMAGE_SIZES)
# def test_tile_larger_than_image(test_images, size):
#     *_, msg = lab1.mosaic_construction(test_images[size], size * 2)
#     assert msg == "Tile size is too large for this image."

# # None returns None
# def test_none_input():
#     assert lab1.mosaic_construction(None, 32) is None


# # ---------------------------------------------------------------------------
# # Benchmark (python test_lab1.py)
# # ---------------------------------------------------------------------------

# def _grab(pattern, text):
#     m = re.search(pattern, text)
#     return float(m.group(1)) if m else float("nan")

# # calls mosaic_construction for every image-size and tile
# # size combination, pulls numbers back out of summary
# # with regex and prints table
# def run_benchmark():
#     images = {s: Image.open(p).convert("RGB") for s, p in generate_test_images().items()}
#     header = f"{'Image':>11} {'Tile':>5} {'Grid':>9} {'Total ms':>10} {'Vec ms':>8} {'Loop ms':>9} {'Speedup':>8} {'MSE':>9} {'SSIM':>7}"
#     print(header)
#     print("-" * len(header))
#     for size in IMAGE_SIZES:
#         for tile in TILE_SIZES:
#             *_, s = lab1.mosaic_construction(images[size], tile)
#             g = size // tile
#             print(
#                 f"{size:>4}x{size:<6} {tile:>5} {f'{g}x{g}':>9} "
#                 f"{_grab(r'Total Processing Time: ([\d.]+)', s):>10.2f} "
#                 f"{_grab(r'Vectorized Time: ([\d.]+)', s):>8.2f} "
#                 f"{_grab(r'Looped Time: ([\d.]+)', s):>9.2f} "
#                 f"{_grab(r'Speedup: ([\d.]+)', s):>7.1f}x "
#                 f"{_grab(r'MSE\): ([\d.]+)', s):>9.2f} "
#                 f"{_grab(r'SSIM\): ([-\d.]+)', s):>7.4f}"
#             )


# if __name__ == "__main__":
#     run_benchmark()
