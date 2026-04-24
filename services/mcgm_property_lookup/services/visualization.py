"""
MCGM Property Lookup — Visualization Utilities
Generates high-resolution satellite maps with plot boundaries.
"""

import os
import uuid
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from shapely.geometry import Polygon

def generate_plot_map(rings: list, output_dir: str = "maps") -> str:
    """Generate a high-fidelity satellite map for a property plot.
    
    Args:
        rings: List of ArcGIS rings in Web Mercator (EPSG:3857).
        output_dir: Directory to save the generated PNG.
        
    Returns:
        Absolute path to the generated map image.
    """
    if not rings:
        raise ValueError("Cannot generate map for empty rings.")

    # 1. Setup Cartopy with Satellite tiles
    imagery = cimgt.GoogleTiles(style='satellite')
    fig = plt.figure(figsize=(10, 10), dpi=150)
    ax = plt.axes(projection=imagery.crs)

    # 2. Extract plot geometry
    poly = Polygon(rings[0])
    minx, miny, maxx, maxy = poly.bounds
    
    # Add margin
    dx = maxx - minx
    dy = maxy - miny
    ax.set_extent([
        minx - dx * 0.4, 
        maxx + dx * 0.4, 
        miny - dy * 0.4, 
        maxy + dy * 0.4
    ], crs=ccrs.Mercator.GOOGLE)

    # Add imagery
    try:
        ax.add_image(imagery, 19)
    except:
        ax.add_image(imagery, 18)

    # 3. Draw the Property Plot
    ax.add_geometries(
        [poly], 
        crs=ccrs.Mercator.GOOGLE,
        facecolor='red', 
        edgecolor='#FF0000', 
        linewidth=2.5, 
        alpha=0.3
    )

    # 4. Save and return
    os.makedirs(output_dir, exist_ok=True)
    filename = f"property_map_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.0)
    plt.close(fig)

    return filepath
