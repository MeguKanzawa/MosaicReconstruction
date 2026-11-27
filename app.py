"""Streamlit web interface for the mosaic generator.

Run from the project folder:

    streamlit run app.py
"""

from pathlib import Path

import streamlit as st
from mosaic_generator import MosaicBuilder, MosaicError, TileManager, config
from mosaic_generator.utils import format_summary, stage_label

APP_DIR = Path(__file__).resolve().parent
TILE_DIR = APP_DIR / config.TILE_DIRECTORY     # works whatever folder streamlit is started from
EXAMPLE_DIR = APP_DIR / config.EXAMPLE_DIRECTORY

st.set_page_config(page_title=config.APP_TITLE, layout="wide")


def list_examples(directory):
    """Example images bundled with the app, sorted by file name.

    Parameters
    ----------
    directory : pathlib.Path
        Folder of example images.

    Returns
    -------
    list of pathlib.Path
        Image files with an extension in ``config.EXAMPLE_EXTENSIONS``; empty if
        the folder does not exist.
    """
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() in config.EXAMPLE_EXTENSIONS)


def choose_image():
    """Let the user pick a bundled example image or upload their own.

    Returns
    -------
    pathlib.Path or streamlit.runtime.uploaded_file_manager.UploadedFile or None
        The chosen image, or None if the user picked "Upload your own" but has
        not uploaded a file yet.
    """
    examples = list_examples(EXAMPLE_DIR)
    sources = ["Example image", "Upload your own"] if examples else ["Upload your own"]
    source = st.radio("Image source", sources, horizontal=True)

    if source == "Upload your own":
        return st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])

    names = [p.name for p in examples]
    default = names.index(config.DEFAULT_EXAMPLE) if config.DEFAULT_EXAMPLE in names else 0
    choice = st.selectbox("Example image", names, index=default)
    return examples[names.index(choice)]


@st.cache_resource(show_spinner="Loading tile library...")
def load_tiles(directory):
    """Load the tile library once and share it across reruns and sessions.

    Parameters
    ----------
    directory : str
        Folder of tile images.

    Returns
    -------
    TileManager
    """
    return TileManager(tile_directory=directory)


def show_performance(result, looped=None):
    """Display processing times: headline numbers and a per-stage table.

    Parameters
    ----------
    result : MosaicResult
        Result of ``MosaicBuilder.build``.
    looped : tuple of (float, bool), optional
        Looped search time in ms and whether it agreed with the k-d tree.

    Returns
    -------
    None
    """
    metrics_ms = result.total_ms - result.generation_ms
    cols = st.columns(4 if looped else 3)
    cols[0].metric("Total processing time", f"{result.total_ms:.1f} ms")
    cols[1].metric("Mosaic generation", f"{result.generation_ms:.1f} ms")
    cols[2].metric("Quality metrics", f"{metrics_ms:.1f} ms" if result.mse is not None else "off")
    if looped:
        looped_ms, same = looped
        speedup = looped_ms / max(result.timings["search"], 1e-4)
        cols[3].metric("k-d tree vs looped search", f"{speedup:.0f}x faster",
                       help=f"Looped search: {looped_ms:.1f} ms. "
                            f"Same tiles chosen: {'yes' if same else 'NO'}.")

    with st.expander("Time per stage"):
        st.table({"Stage": [stage_label(k) for k in result.timings],
                  "Time (ms)": [f"{v:.2f}" for v in result.timings.values()]})


def main():
    """Build the page: controls on the left, results on the right.

    Returns
    -------
    None
    """
    st.title(config.APP_TITLE)
    st.markdown("Pick an example image or upload your own, then adjust the slider to view "
                "dynamic mosaic reconstruction.")

    try:
        tiles = load_tiles(str(TILE_DIR))
    except MosaicError as e:
        st.error(f"Could not load the tile library: {e}")
        st.stop()
    if tiles.skipped:
        names = ", ".join(p.name for p, _ in tiles.skipped[:5])
        st.warning(f"{len(tiles.skipped)} tile file(s) could not be read and were skipped: {names}")

    builder = MosaicBuilder(tiles)
    col_left, col_right = st.columns([1, 2])

    with col_left:
        image = choose_image()
        mode = st.radio("Size the mosaic by", ["Tile size", "Grid size"], horizontal=True)
        if mode == "Tile size":
            value = st.slider("Tile Size (px)", config.SLIDER_MIN, config.SLIDER_MAX,
                              config.DEFAULT_TILE_SIZE, config.SLIDER_STEP)
            size = {"tile_size": value}
        else:
            value = st.slider("Grid Size (tiles per side)", config.SLIDER_MIN, config.SLIDER_MAX,
                              config.DEFAULT_GRID_SIZE[0], config.SLIDER_STEP)
            size = {"grid_size": value}
        compute_metrics = st.checkbox("Compute quality metrics (MSE, SSIM)", value=True)
        compare_looped = st.checkbox("Compare with looped tile search", value=False)
        st.caption(f"Tile library: {len(tiles)} tiles")

    with col_right:
        if image is None:
            st.info("Upload an image in the left panel to begin reconstruction.")
            return

        try:
            result = builder.build(image, compute_metrics=compute_metrics, **size)
        except MosaicError as e:
            st.warning(str(e))
            return
        looped = builder.compare_with_looped(result) if compare_looped else None

        show_performance(result, looped)

        img_col1, img_col2, img_col3 = st.columns(3)
        with img_col1:
            st.image(result.cropped, caption="Square Crop", width="stretch")
        with img_col2:
            st.image(result.segmented, caption="Segmented Grid Overlay", width="stretch")
        with img_col3:
            st.image(result.mosaic, caption="Final Mosaic", width="stretch")

        st.text_area("Performance & Quality Metrics",
                     value=format_summary(result, len(tiles), looped), height=320)


if __name__ == "__main__":
    main()
