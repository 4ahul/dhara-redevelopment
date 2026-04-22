"""
MCGM Property Lookup — Visualization Engine
Generates professional geographic map renders using Cartopy and GeoPandas.
"""

import os
import uuid
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from shapely.geometry import Polygon

def generate_plot_map(rings: list, output_dir: str = "/tmp") -> str:
    """Generate a high-quality satellite map image centering the property plot.
    
    Args:
        rings: Coordinates in Web Mercator (EPSG:3857) from the ArcGIS query.
        output_dir: Location to save the image (defaults to /tmp).
        
    Returns:
        Absolute path to the generated PNG file.
    """
    if not rings:
        raise ValueError("Cannot draw map without geometry rings.")

    # 1. Create a Shapely Polygon from the ArcGIS rings
    outer_ring = rings[0]
    poly = Polygon(outer_ring)

    # Calculate bounding box for the map window
    minx, miny, maxx, maxy = poly.bounds
    
    # Add strong padding so we can see the neighborhood around the plot
    width = maxx - minx
    height = maxy - miny
    padding = max(width, height) * 2
    
    extent = [
        minx - padding,
        maxx + padding,
        miny - padding,
        maxy + padding
    ]

    # 2. Configure Cartopy Background
    # Using StadiaMaps / Stamen Terrain or a standard reliable satellite basemap
    # Here we use GoogleTiles as a highly effective open satellite imagery baseline
    request = cimgt.GoogleTiles(style='satellite')
    
    # Setup standard high-res Matplotlib figure
    fig = plt.figure(figsize=(10, 10), dpi=300)
    
    # The axis projection must match the Web Mercator we're plotting
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mercator.GOOGLE)
    ax.set_extent(extent, crs=ccrs.Mercator.GOOGLE)

    # Add the satellite background
    # Zoom level 19 for extremely high-fidelity local neighborhood view
    # (If API issues arise with GoogleTiles, OpenStreetMap is an instant fallback)
    try:
        ax.add_image(request, 19)
    except Exception as e:
        # Fallback to OSM if satellite request is blocked
        osm = cimgt.OSM()
        ax.add_image(osm, 19)

    # 3. Draw the Property Plot
    # We apply the user's requested strong solid RED boundary with a light red transparent fill
    ax.add_geometries(
        [poly], 
        crs=ccrs.Mercator.GOOGLE,
        facecolor='red', 
        edgecolor='#FF0000', 
        linewidth=3.0, 
        alpha=0.35
    )

    # 4. Save and Yield
    os.makedirs(output_dir, exist_ok=True)
    filename = f"property_map_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    
    # Save tightening bounding box so no ugly whitespace exists
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.0)
    plt.close(fig)

    return filepath
