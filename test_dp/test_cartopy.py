import os
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from shapely.geometry import Polygon

xm, ym = 8109000, 2163000
size = 200
rings = [[[xm, ym], [xm+size, ym], [xm+size, ym+size], [xm, ym+size], [xm, ym]]]
poly = Polygon(rings[0])

minx, miny, maxx, maxy = poly.bounds
width, height = maxx - minx, maxy - miny
padding = max(width, height) * 2
extent = [minx - padding, maxx + padding, miny - padding, maxy + padding]

request = cimgt.GoogleTiles(style='satellite')
fig = plt.figure(figsize=(8, 8), dpi=150)
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mercator.GOOGLE)
ax.set_extent(extent, crs=ccrs.Mercator.GOOGLE)

try:
    ax.add_image(request, 17)
except Exception as e:
    import traceback
    traceback.print_exc()

ax.add_geometries([poly], crs=ccrs.Mercator.GOOGLE,
                  facecolor='red', edgecolor='#FF0000', linewidth=3.0, alpha=0.35)

output_dir = "/Users/somu/.gemini/antigravity/brain/064555bc-0b66-4770-8ce2-60ef6c477a22/artifacts"
filepath = os.path.join(output_dir, "test_cartopy_direct.png")
plt.savefig(filepath, bbox_inches='tight', pad_inches=0.0)
plt.close(fig)

print(f"SUCCESS: {filepath}")

