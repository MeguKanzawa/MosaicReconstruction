# from line_profiler import LineProfiler
# from PIL import Image
# import test_lab8  # does the chdir + imports lab1
# import lab1

# lp = LineProfiler(lab1.mosaic_construction, lab1.find_best_tile,
#                   lab1.find_best_tile_looped, lab1.calculate_ssim)
# img = Image.open(test_lab8.generate_test_images()[1024]).convert("RGB")
# lp.runcall(lab1.mosaic_construction, img, 16)
# lp.print_stats(output_unit=1e-3)  # times in ms