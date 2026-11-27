# """
# Baseline performance analysis for lab1.py (mosaic reconstruction).

#     python lab1_baseline.py timing     # Part 1: mean of N runs, all 9 configs, CSV + scaling plot
#     python lab1_baseline.py breakdown  # Part 1b: per-stage times (replaces 'everything else')
#     python lab1_baseline.py cprofile   # Part 2: function-level profile (cProfile)
#     python lab1_baseline.py lines      # Part 3: line-by-line profile (line_profiler)
#     python lab1_baseline.py all        # all three

# Options:
#     --runs 5                  timed runs per configuration (default 3)
#     --config 512 32           line_profiler: which image size / grid size to profile
#     --top 25                  cProfile: how many rows to show

# All output is also written to perf_results/.
# """

# import argparse
# import cProfile
# import csv
# import io
# import os
# import pstats
# import re
# import statistics
# import sys
# import time
# from pathlib import Path

# # lab1.py loads tiles/ with a relative path at import time, so chdir first.
# PROJECT_DIR = Path(__file__).resolve().parent
# os.chdir(PROJECT_DIR)
# sys.path.insert(0, str(PROJECT_DIR))

# import numpy as np
# from PIL import Image

# import lab1

# # ---------------------------------------------------------------------------
# # Configuration
# # ---------------------------------------------------------------------------

# IMAGE_SIZES = [256, 512, 1024]
# # "Grid size" = number of tiles per side, so tile_size = image_size // grid_size.
# # e.g. 256x256 with a 16x16 grid -> 16 px tiles; 1024x1024 with 64x64 -> 16 px tiles.
# GRID_SIZES = [16, 32, 64]
# REQUIRED_CONFIGS = [(256, 16), (512, 32), (1024, 64)]

# TEST_IMAGE_DIR = PROJECT_DIR / "test_images"
# SOURCE_IMAGE = PROJECT_DIR / "img" / "cake4.png"
# RESULTS_DIR = PROJECT_DIR / "perf_results"

# # Functions profiled line by line in Part 3.
# LINE_PROFILE_TARGETS = [
#     lab1.mosaic_construction,
#     lab1.find_best_tile,
#     lab1.find_best_tile_looped,
#     lab1.calculate_ssim,
#     lab1.calculate_mse,
# ]


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def load_test_images():
#     """Same images the test suite uses: test_images/test_<n>x<n>.png, made from img/cake4.png."""
#     TEST_IMAGE_DIR.mkdir(exist_ok=True)
#     images = {}
#     for size in IMAGE_SIZES:
#         path = TEST_IMAGE_DIR / f"test_{size}x{size}.png"
#         if not path.exists():
#             if not SOURCE_IMAGE.exists():
#                 raise FileNotFoundError(f"{SOURCE_IMAGE} not found and {path} does not exist")
#             (Image.open(SOURCE_IMAGE).convert("RGB")
#                   .resize((size, size), Image.Resampling.LANCZOS)
#                   .save(path))
#         images[size] = Image.open(path).convert("RGB")
#     return images


# def tile_size_for(image_size, grid_size):
#     return image_size // grid_size


# def grab(pattern, text):
#     m = re.search(pattern, text)
#     return float(m.group(1)) if m else float("nan")


# def banner(title):
#     line = "=" * 78
#     return f"\n{line}\n{title}\n{line}"


# def save_text(name, text):
#     RESULTS_DIR.mkdir(exist_ok=True)
#     path = RESULTS_DIR / name
#     path.write_text(text)
#     return path


# # ---------------------------------------------------------------------------
# # Part 1: baseline timing
# # ---------------------------------------------------------------------------

# # times the whole mosaic_construction call with time.time()
# # each of 9 configurations run once at warm-up, then 3 timed runs
# # for each configuration, 
# #   - mean, std of total times
# #   - breakdown of looped search vs vectorized search, everything else shown
# #   - * on the required configurations
# # returns the matplotlib figure for all 9 configurations as baseline_scaling.png

# def run_timing(images, runs, warmup=1):
#     """Time the full mosaic_construction call for every image/grid combination."""
#     rows = []
#     print(banner(f"PART 1: BASELINE TIMING (mean of {runs} runs, {warmup} warm-up run discarded)"))
#     header = (f"{'Image':>9} {'Grid':>7} {'Tile px':>7} {'Mean ms':>10} {'Std ms':>8} "
#               f"{'Loop ms':>10} {'Vec ms':>8} {'Other ms':>9} {'Loop %':>7}  Req")
#     print(header)
#     print("-" * len(header))

#     for size in IMAGE_SIZES:
#         for grid in GRID_SIZES:
#             tile = tile_size_for(size, grid)
#             img = images[size]

#             for _ in range(warmup):
#                 lab1.mosaic_construction(img, tile)

#             totals, loops, vecs = [], [], []
#             for _ in range(runs):
#                 t0 = time.time()
#                 *_, summary = lab1.mosaic_construction(img, tile)
#                 totals.append((time.time() - t0) * 1000)
#                 # Internal timings that lab1 already measures and reports.
#                 loops.append(grab(r"Looped Time: ([\d.]+)", summary))
#                 vecs.append(grab(r"Vectorized Time: ([\d.]+)", summary))

#             mean_total = statistics.mean(totals)
#             std_total = statistics.stdev(totals) if runs > 1 else 0.0
#             mean_loop = statistics.mean(loops)
#             mean_vec = statistics.mean(vecs)
#             other = mean_total - mean_loop - mean_vec   # cropping, resizing, pasting, metrics
#             required = (size, grid) in REQUIRED_CONFIGS

#             rows.append({
#                 "image_size": size, "grid_size": grid, "tile_px": tile,
#                 "cells": grid * grid, "runs": runs,
#                 "mean_total_ms": round(mean_total, 3), "std_total_ms": round(std_total, 3),
#                 "mean_looped_ms": round(mean_loop, 3), "mean_vectorized_ms": round(mean_vec, 3),
#                 "mean_other_ms": round(other, 3),
#                 "looped_pct": round(100 * mean_loop / mean_total, 1),
#                 "required": required,
#                 "all_runs_ms": " ".join(f"{t:.2f}" for t in totals),
#             })
#             print(f"{size:>4}x{size:<4} {f'{grid}x{grid}':>7} {tile:>7} {mean_total:>10.2f} "
#                   f"{std_total:>8.2f} {mean_loop:>10.2f} {mean_vec:>8.2f} {other:>9.2f} "
#                   f"{100 * mean_loop / mean_total:>6.1f}%  {'*' if required else ''}")

#     print("\n* = required configuration.  Other = total - looped - vectorized.")

#     RESULTS_DIR.mkdir(exist_ok=True)
#     csv_path = RESULTS_DIR / "baseline_timing.csv"
#     with open(csv_path, "w", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
#         writer.writeheader()
#         writer.writerows(rows)
#     print(f"Saved {csv_path}")

#     plot_scaling(rows)
#     return rows


# def plot_scaling(rows):
#     try:
#         import matplotlib
#         matplotlib.use("Agg")
#         import matplotlib.pyplot as plt
#     except ImportError:
#         print("matplotlib not installed; skipping plot (pip install matplotlib)")
#         return

#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

#     for size in IMAGE_SIZES:
#         r = [row for row in rows if row["image_size"] == size]
#         grids = [row["grid_size"] for row in r]
#         ax1.errorbar(grids, [row["mean_total_ms"] for row in r],
#                      yerr=[row["std_total_ms"] for row in r],
#                      marker="o", capsize=3, label=f"{size}x{size} image")
#     ax1.set_title("Total mosaic generation time (baseline)")
#     ax1.set_xlabel("Grid size (tiles per side)")
#     ax1.set_ylabel("Mean time (ms)")
#     ax1.set_xticks(GRID_SIZES, [f"{g}x{g}" for g in GRID_SIZES])
#     ax1.set_yscale("log")
#     ax1.grid(True, which="both", alpha=0.3)
#     ax1.legend()

#     # Stacked breakdown for the three required configurations.
#     req = [row for row in rows if row["required"]]
#     labels = [f"{row['image_size']}px\n{row['grid_size']}x{row['grid_size']}" for row in req]
#     loop = [row["mean_looped_ms"] for row in req]
#     vec = [row["mean_vectorized_ms"] for row in req]
#     other = [row["mean_other_ms"] for row in req]
#     ax2.bar(labels, loop, label="Looped tile search")
#     ax2.bar(labels, vec, bottom=loop, label="Vectorized tile search")
#     ax2.bar(labels, other, bottom=[a + b for a, b in zip(loop, vec)], label="Everything else")
#     ax2.set_title("Where the time goes (required configs)")
#     ax2.set_ylabel("Mean time (ms)")
#     ax2.legend()

#     fig.tight_layout()
#     path = RESULTS_DIR / "baseline_scaling.png"
#     fig.savefig(path, dpi=150)
#     plt.close(fig)
#     print(f"Saved {path}")


# # ---------------------------------------------------------------------------
# # Part 1b: per-stage breakdown of the baseline
# # ---------------------------------------------------------------------------

# # Every stage of mosaic_construction, in order: (key, label for tables/plots).
# STAGES = [
#     ("to_array",   "Convert to array"),
#     ("crop_grid",  "Crop + red grid"),
#     ("cell_avg",   "Cell averages"),
#     ("vectorized", "Vectorized search"),
#     ("looped",     "Looped search"),
#     ("resize",     "Resize tiles"),
#     ("paste",      "Paste tiles"),
#     ("to_pil",     "Convert to PIL"),
#     ("mse",        "MSE"),
#     ("ssim",       "SSIM"),
# ]


# def staged_mosaic(image, tile_size):
#     """Stage-by-stage copy of lab1.mosaic_construction with a timer around each stage.

#     The inline code is copied line for line from lab1.py, and the helper functions,
#     tile library and tile colors are lab1's own, so the work done is identical.
#     run_breakdown() checks that the mosaic it builds matches lab1's exactly.
#     Returns (mosaic array, {stage key: ms}).
#     """
#     clock = time.perf_counter
#     t = {}

#     s = clock()
#     img = np.array(image.convert("RGB"))
#     t["to_array"] = clock() - s

#     s = clock()
#     th = tw = int(tile_size)
#     h, w, ch = img.shape
#     g = min(h // th, w // tw)
#     valid = g * th
#     sh, sw = (h - valid) // 2, (w - valid) // 2
#     cropped = img[sh:sh + valid, sw:sw + valid, :]
#     segmented = cropped.copy()
#     for r in range(1, g):
#         segmented[r * th, :, :] = [255, 0, 0]
#     for c in range(1, g):
#         segmented[:, c * tw, :] = [255, 0, 0]
#     t["crop_grid"] = clock() - s

#     s = clock()
#     blocked = cropped.reshape(g, th, g, tw, ch).transpose(0, 2, 1, 3, 4)
#     cell_avg = np.mean(blocked, axis=(2, 3))
#     t["cell_avg"] = clock() - s

#     s = clock()
#     best = lab1.find_best_tile(cell_avg)
#     t["vectorized"] = clock() - s

#     s = clock()
#     lab1.find_best_tile_looped(cell_avg)
#     t["looped"] = clock() - s

#     s = clock()
#     resized = [np.array(tile.resize((tw, th), Image.Resampling.BILINEAR))
#                for tile in lab1.tile_images_pil]
#     t["resize"] = clock() - s

#     s = clock()
#     canvas = np.zeros((valid, valid, 3), dtype=np.uint8)
#     for r in range(g):
#         for c in range(g):
#             canvas[r * th:(r + 1) * th, c * tw:(c + 1) * tw, :] = resized[best[r, c]]
#     t["paste"] = clock() - s

#     s = clock()
#     Image.fromarray(canvas)
#     Image.fromarray(cropped)
#     Image.fromarray(segmented)
#     t["to_pil"] = clock() - s

#     s = clock()
#     lab1.calculate_mse(cropped, canvas)
#     t["mse"] = clock() - s

#     s = clock()
#     lab1.calculate_ssim(cropped, canvas)
#     t["ssim"] = clock() - s

#     return canvas, {k: v * 1000 for k, v in t.items()}


# def run_breakdown(images, runs, warmup=1):
#     """Mean time of every stage, for every image/grid combination."""
#     print(banner(f"PART 1b: PER-STAGE BREAKDOWN (mean of {runs} runs, times in ms)"))
#     short = ["Array", "Crop", "CellAvg", "Vec", "Loop", "Resize", "Paste", "ToPIL", "MSE", "SSIM"]
#     header = (f"{'Image':>9} {'Grid':>7} {'Real':>8} {'Staged':>8} | "
#               + " ".join(f"{name:>7}" for name in short) + " | Largest stage")
#     print(header)
#     print("-" * len(header))

#     rows = []
#     for size in IMAGE_SIZES:
#         for grid in GRID_SIZES:
#             tile = tile_size_for(size, grid)
#             img = images[size]

#             for _ in range(warmup):
#                 lab1.mosaic_construction(img, tile)
#                 staged_mosaic(img, tile)

#             real_totals, stage_runs = [], []
#             for _ in range(runs):
#                 t0 = time.perf_counter()
#                 _, _, real_mosaic, _ = lab1.mosaic_construction(img, tile)
#                 real_totals.append((time.perf_counter() - t0) * 1000)

#                 canvas, stage_ms = staged_mosaic(img, tile)
#                 stage_runs.append(stage_ms)

#             # Correctness check: the staged copy must build exactly the same mosaic.
#             if not np.array_equal(canvas, np.array(real_mosaic)):
#                 raise RuntimeError(f"staged_mosaic differs from lab1 at {size}px / {grid}x{grid}")

#             means = {k: statistics.mean(run[k] for run in stage_runs) for k, _ in STAGES}
#             staged_total = sum(means.values())
#             real_total = statistics.mean(real_totals)
#             top_key, top_label = max(STAGES, key=lambda st: means[st[0]])

#             row = {"image_size": size, "grid_size": grid, "tile_px": tile, "runs": runs,
#                    "real_total_ms": round(real_total, 3), "staged_total_ms": round(staged_total, 3)}
#             for key, _ in STAGES:
#                 row[f"{key}_ms"] = round(means[key], 3)
#             for key, _ in STAGES:
#                 row[f"{key}_pct"] = round(100 * means[key] / staged_total, 1)
#             row["required"] = (size, grid) in REQUIRED_CONFIGS
#             rows.append(row)

#             print(f"{size:>4}x{size:<4} {f'{grid}x{grid}':>7} {real_total:>8.2f} {staged_total:>8.2f} | "
#                   + " ".join(f"{means[k]:>7.2f}" for k, _ in STAGES)
#                   + f" | {top_label} ({100 * means[top_key] / staged_total:.0f}%)"
#                   + ("  *" if row["required"] else ""))

#     print("\nReal = lab1.mosaic_construction timed as a whole. Staged = sum of the stage means.")
#     print("Staged mosaics matched lab1's output exactly for every configuration.  * = required.")

#     RESULTS_DIR.mkdir(exist_ok=True)
#     csv_path = RESULTS_DIR / "baseline_breakdown.csv"
#     with open(csv_path, "w", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
#         writer.writeheader()
#         writer.writerows(rows)
#     print(f"Saved {csv_path}")

#     plot_breakdown(rows)
#     return rows


# def plot_breakdown(rows):
#     try:
#         import matplotlib
#         matplotlib.use("Agg")
#         import matplotlib.pyplot as plt
#     except ImportError:
#         print("matplotlib not installed; skipping plot (pip install matplotlib)")
#         return

#     labels = [f"{r['image_size']}px\n{r['grid_size']}x{r['grid_size']}"
#               + ("*" if r["required"] else "") for r in rows]
#     colors = plt.get_cmap("tab10").colors
#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

#     for ax, suffix, ylabel, title in (
#         (ax1, "_ms", "Mean time (ms)", "Time per stage (baseline)"),
#         (ax2, "_pct", "Share of total (%)", "Share of total time per stage (baseline)"),
#     ):
#         bottom = [0.0] * len(rows)
#         for (key, label), color in zip(STAGES, colors):
#             values = [r[key + suffix] for r in rows]
#             ax.bar(labels, values, bottom=bottom, label=label, color=color)
#             bottom = [b + v for b, v in zip(bottom, values)]
#         ax.set_title(title)
#         ax.set_ylabel(ylabel)
#         ax.tick_params(axis="x", labelsize=8)

#     ax2.set_ylim(0, 100)
#     ax2.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9)
#     fig.text(0.5, 0.01, "* = required configuration", ha="center", fontsize=9)
#     fig.tight_layout(rect=(0, 0.03, 1, 1))
#     path = RESULTS_DIR / "baseline_breakdown.png"
#     fig.savefig(path, dpi=150, bbox_inches="tight")
#     plt.close(fig)
#     print(f"Saved {path}")


# # ---------------------------------------------------------------------------
# # Part 2: cProfile (function level)
# # ---------------------------------------------------------------------------

# # profiles mosaic_construction for three required configurations
# # and prints top functions sorted three ways (cum_time, internal_time,
# # call_count)

# def run_cprofile(images, configs, top):
#     print(banner("PART 2: cProfile (function level)"))
#     for size, grid in configs:
#         tile = tile_size_for(size, grid)
#         profiler = cProfile.Profile()
#         profiler.runcall(lab1.mosaic_construction, images[size], tile)

#         stem = f"cprofile_{size}px_grid{grid}"
#         RESULTS_DIR.mkdir(exist_ok=True)
#         profiler.dump_stats(RESULTS_DIR / f"{stem}.prof")   # open with: snakeviz <file>

#         buf = io.StringIO()
#         stats = pstats.Stats(profiler, stream=buf).strip_dirs()
#         buf.write(f"\n### {size}x{size} image, {grid}x{grid} grid ({tile} px tiles)\n")
#         buf.write("\n--- sorted by cumulative time (time in function + everything it calls) ---\n")
#         stats.sort_stats("cumulative").print_stats(top)
#         buf.write("\n--- sorted by internal time (time in the function body itself) ---\n")
#         stats.sort_stats("tottime").print_stats(top)
#         buf.write("\n--- sorted by call count (look for things called far more than expected) ---\n")
#         stats.sort_stats("ncalls").print_stats(top)

#         text = buf.getvalue()
#         print(text)
#         print(f"Saved {save_text(stem + '.txt', text)} and {stem}.prof")


# # ---------------------------------------------------------------------------
# # Part 3: line_profiler (line level)
# # ---------------------------------------------------------------------------

# def run_line_profiler(images, size, grid):
#     try:
#         from line_profiler import LineProfiler
#     except ImportError:
#         print("line_profiler is not installed: pip install line_profiler")
#         return

#     tile = tile_size_for(size, grid)
#     print(banner(f"PART 3: line_profiler, {size}x{size} image, {grid}x{grid} grid ({tile} px tiles)"))
#     print("(The looped search runs much slower under line_profiler; this can take a while.)")

#     lp = LineProfiler(*LINE_PROFILE_TARGETS)
#     lp.runcall(lab1.mosaic_construction, images[size], tile)

#     buf = io.StringIO()
#     lp.print_stats(stream=buf, output_unit=1e-3)   # times in ms
#     text = buf.getvalue()
#     print(text)
#     print(f"Saved {save_text(f'line_profile_{size}px_grid{grid}.txt', text)}")


# # ---------------------------------------------------------------------------
# # Main
# # ---------------------------------------------------------------------------

# def main():
#     parser = argparse.ArgumentParser(description=__doc__,
#                                      formatter_class=argparse.RawDescriptionHelpFormatter)
#     parser.add_argument("part", choices=["timing", "breakdown", "cprofile", "lines", "all"])
#     parser.add_argument("--runs", type=int, default=3, help="timed runs per configuration")
#     parser.add_argument("--warmup", type=int, default=1, help="untimed warm-up runs per configuration")
#     parser.add_argument("--top", type=int, default=20, help="rows to show in cProfile tables")
#     parser.add_argument("--config", type=int, nargs=2, metavar=("IMAGE", "GRID"),
#                         default=[1024, 64], help="configuration for line_profiler")
#     args = parser.parse_args()

#     images = load_test_images()
#     print(f"Tile library: {len(lab1.tile_images_pil)} tiles")

#     if args.part in ("timing", "all"):
#         run_timing(images, args.runs, args.warmup)
#     if args.part in ("breakdown", "all"):
#         run_breakdown(images, args.runs, args.warmup)
#     if args.part in ("cprofile", "all"):
#         run_cprofile(images, REQUIRED_CONFIGS, args.top)
#     if args.part in ("lines", "all"):
#         run_line_profiler(images, *args.config)


# if __name__ == "__main__":
#     main()