from pathlib import Path

import numpy as np

# import cv2
from PIL import Image
import gradio as gr
import time
from skimage.metrics import structural_similarity as ssim
import glob
import streamlit as st

# For streamlit configuration
st.set_page_config(page_title="Mosaic Reconstruction Tool", layout="wide")

st.title("Mosaic Reconstruction Tool")
st.markdown("Upload an image and adjust the tile size slider to view dynamic square mosaic reconstruction.")

# Step 1: Preprocess tile library at startup
# globs every .png and .jpg in tiles/, opens each as RGB
# stores the PIL image and each tile's average color 
# st.cache_data computes this once only NOT on every slider move
# result = tile_avg_color(N, 3) array where N = number of tiles

@st.cache_data
def load_tile_files():
    tile_folder = "tiles"
    tile_paths = glob.glob(f"{tile_folder}/*.png") + glob.glob(f"{tile_folder}/*.jpg")

    tile_images_pil = []
    tile_avg_colors_list = []

    for p in tile_paths:
        try:
            img = Image.open(p).convert('RGB')
            arr = np.array(img)
            tile_images_pil.append(img)
            tile_avg_colors_list.append(arr.mean(axis=(0, 1)))
        except Exception as e:
            print(f"Error loading tile {p}: {e}")
        
    tile_avg_colors = np.array(tile_avg_colors_list)
    return tile_images_pil, tile_avg_colors

tile_images_pil, tile_avg_colors = load_tile_files()

# helper functions

# calculates mean squared pixel difference
def calculate_mse(img1, img2):
    """Calculates Mean Squared Error between two images."""
    return np.mean((img1.astype("float") - img2.astype("float")) ** 2)

# picks an odd window size of at most 7 BEC SSIM requires 
# an odd window no larger than image
def calculate_ssim(img1, img2):
    """Calculates SSIM between two RGB images."""
    min_dim = min(img1.shape[0], img1.shape[1])
    win_size = min(7, min_dim if min_dim % 2 != 0 else min_dim - 1)
    if win_size < 3: 
        return 0.0
    return ssim(img1, img2, channel_axis=2, win_size=win_size)

# uses broadcasting
# cell_avg_colors --> (rows, cols, 3)
# tile colors --> (1, 1, N, 3)
# subtracting them gives every cell to tile difference 
# --> (rows, cols, N, 3)
# squaring and summing over last axis gives squared euc distance
# argmin returns closest tile per cell
def find_best_tile(cell_avg_colors):
    """Finds the best tile in vectorized operations"""
    # reshape
    diff = cell_avg_colors[:, :, np.newaxis, :] - tile_avg_colors[np.newaxis, np.newaxis, :, :]
    distances = np.sum(diff**2, axis=-1)
    best_tile_indices = np.argmin(distances, axis=-1)
    return best_tile_indices

# for comparison with looped version
# does same thing with nested Python loops (rows, cols,tiles)
# Iterations = rows x cols x N --> SLOW
def find_best_tile_looped(cell_avg_colors):
    """Explicit nested loop distance calculation (Slow - for Step 6 analysis)."""
    rows, cols, _ = cell_avg_colors.shape
    best_indices = np.zeros((rows, cols), dtype=int)
    for r in range(rows):
        for c in range(cols):
            cell_rgb = cell_avg_colors[r, c]
            min_dist = float('inf')
            best_idx = 0
            for idx, tile_rgb in enumerate(tile_avg_colors):
                dist = np.sum((cell_rgb - tile_rgb) ** 2)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx
            best_indices[r, c] = best_idx
    return best_indices

# Step 2 - Mosaic Generation
# 1. converts input to numpy array
# 2. works out how many whole tiles fit, taking smaller of the row/col
#   so the mosaic is a square
# 3. center crops to grid_dim * tile_size square
# 4. makes copy with red lines for tile_size pixels for seg view
# 5. computes per-cell average color with a reshape
#   reshape(g, th, g, tw, C) = splits each axis into which cell,
#   which pixel, within cell
#   transpose regroups array into (cell_row, cell_col, pixel_row,
#   pixel_col, C)
#   averages over axis 2 and 3 to give one color per cell
# 6. runs both vectorized and looped search + times of each,
# 7. resizes every tile in library to tile_size x tile_size
#   pastes chosen tile into each cell of blank canvas with 
#   double loop
# 8. computes MSE and SSIM between cropped original vs mosaic
#   returns cropped, segmented, mosaic, summary

def mosaic_construction(image, tile_size):
    """
    Constructs a mosaic visualization from an input image and tile size.
    
    Parameters:
    - image: PIL Image or numpy array supplied by Gradio
    - tile_size: int, width and height of each tile in pixels
    """
    
    if image is None:return None
    
    start_time = time.time()
    
    if isinstance(image, Image.Image): img1_arr = np.array(image.convert('RGB'))
    else: img1_arr = image

    tile_h1, tile_w1 = int(tile_size), int(tile_size)
    img1_h, img1_w, channels_1 = img1_arr.shape

    grid_rows = img1_h // tile_h1
    grid_cols = img1_w // tile_w1
    grid_dim = min(grid_rows, grid_cols)
    
    # check if tile size is larger than image itself
    if grid_rows == 0: 
        return (
            Image.fromarray(img1_arr), 
            Image.fromarray(img1_arr), 
            Image.fromarray(img1_arr), 
            "Tile size is too large for this image."
        )

    # crop image to be squared
    valid_dim = grid_dim * tile_h1
    start_h = (img1_h - valid_dim) // 2
    start_w = (img1_w - valid_dim) // 2
    img1_arr_cropped = img1_arr[start_h : start_h + valid_dim, start_w : start_w + valid_dim, :]
    
    # draw the segments for red grid overlay
    img_segmented = img1_arr_cropped.copy()
    for r in range(1, grid_dim):
        img_segmented[r * tile_h1, :, :] = [255, 0, 0]
    for c in range(1, grid_dim):
        img_segmented[:, c * tile_w1, :] = [255, 0, 0]

    # reshape into 5D arr & cell average computation
    blocked_arr1 = img1_arr_cropped.reshape(grid_dim, tile_h1, grid_dim, tile_w1, channels_1)
    # groups into respective boundaries
    blocked_arr = blocked_arr1.transpose(0,2,1,3,4)

       
    cell_avg_colors = np.mean(blocked_arr, axis=(2,3))
    
    t0 = time.time()
    best_indices = find_best_tile(cell_avg_colors)
    vectorized_time = (time.time() - t0) * 1000
    
    t0 = time.time()
    best_indices_looped = find_best_tile_looped(cell_avg_colors)
    looped_time = (time.time() - t0) * 1000
    
    # resize tiles
    resized_tiles = [
        np.array(t.resize((tile_w1, tile_h1), Image.Resampling.BILINEAR)) 
        for t in tile_images_pil
    ]
    
    mosaic_canvas = np.zeros((valid_dim, valid_dim, 3), dtype=np.uint8)
    
    for r in range(grid_dim):
        for c in range(grid_dim):
            tile_idx = best_indices[r, c]
            r_start, r_end = r * tile_h1, (r + 1) * tile_h1
            c_start, c_end = c * tile_w1, (c + 1) * tile_w1
            mosaic_canvas[r_start:r_end, c_start:c_end, :] = resized_tiles[tile_idx]
    
    mosaic_img = Image.fromarray(mosaic_canvas)

    mse_val = calculate_mse(img1_arr_cropped, mosaic_canvas)
    ssim_val = calculate_ssim(img1_arr_cropped, mosaic_canvas)
    
    total_time = (time.time() - start_time) * 1000
    speedup = looped_time / max(vectorized_time, 0.0001)
        
    summary_text = (
        f"RECONSTRUCTION SUMMARY\n"
        f"----------------------\n"
        f"Total Processing Time: {total_time:.2f} ms\n"
        f"Tile Size: {tile_h1} x {tile_w1} px\n"
        f"Grid Resolution: {grid_dim} x {grid_dim} tiles ({valid_dim} x {valid_dim} px total)\n"
        f"Tile Library Size: {len(tile_images_pil)} tiles\n\n"
        f"VECTORIZATION PERFORMANCE (STEP 6)\n"
        f"----------------------------------\n"
        f"Vectorized Time: {vectorized_time:.2f} ms\n"
        f"Looped Time: {looped_time:.2f} ms\n"
        f"Vectorization Speedup: {speedup:.1f}x faster\n\n"
        f"QUALITY METRICS (STEP 5)\n"
        f"------------------------\n"
        f"Mean Squared Error (MSE): {mse_val:.2f}\n"
        f"Structural Similarity Index (SSIM): {ssim_val:.4f}"
    )
    
    return (
        # Image.fromarray(img1_arr),
        Image.fromarray(img1_arr_cropped),
        Image.fromarray(img_segmented),
        mosaic_img,
        summary_text
    )
        
col_left, col_right = st.columns([1, 2])

with col_left:
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    tile_size = st.slider("Tile Size (px)", min_value=8, max_value=128, value=32, step=8)

with col_right:
    if uploaded_file is not None:
        input_image = Image.open(uploaded_file)
        img_cropped, img_segmented, img_mosaic, summary = mosaic_construction(input_image, tile_size)
        
        if img_cropped is not None:
            img_col1, img_col2, img_col3 = st.columns(3)
            with img_col1:
                st.image(img_cropped, caption="Square Crop", use_container_width=True)
            with img_col2:
                st.image(img_segmented, caption="Segmented Grid Overlay", use_container_width=True)
            with img_col3:
                st.image(img_mosaic, caption="Final Mosaic", use_container_width=True)
                
            st.text_area("Performance & Quality Metrics", value=summary, height=280)
        else:
            st.warning(summary)
    else:
    # Notice this is purely Streamlit syntax
        st.info("Upload an image in the left panel to begin reconstruction.")