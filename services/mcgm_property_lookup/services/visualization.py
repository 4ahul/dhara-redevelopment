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

def generate_plot_map(rings: list, output_dir: str = "maps", 
                      setback_polys: list = None,
                      max_road_polys: list = None,
                      abutting_lines: list = None,
                      setback_area_m2: float = None,
                      max_road_width_m: float = None,
                      abutting_length_m: float = None,
                      roads_touching: int = None,
                      carriageway_entrances: int = None) -> str:
    """Generate a high-fidelity satellite map for a property plot with advanced metrics."""
    if not rings:
        raise ValueError("Cannot generate map for empty rings.")

    # 1. Setup Cartopy with Satellite tiles
    imagery = cimgt.GoogleTiles(style='satellite')
    fig = plt.figure(figsize=(12, 12), dpi=300)
    ax = plt.axes(projection=imagery.crs)

    # 2. Extract plot geometry
    poly = Polygon(rings[0])
    minx, miny, maxx, maxy = poly.bounds
    
    # Add margin
    dx = maxx - minx
    dy = maxy - miny
    margin_x = dx * 0.8
    margin_y = dy * 0.8
    ax.set_extent([
        minx - margin_x, 
        maxx + margin_x, 
        miny - margin_y, 
        maxy + margin_y
    ], crs=ccrs.Mercator.GOOGLE)

    # Add imagery
    try:
        ax.add_image(imagery, 19)
    except:
        ax.add_image(imagery, 18)

    # Draw Max Road Polygons (Black / Transparent)
    if max_road_polys:
        ax.add_geometries(
            max_road_polys, crs=ccrs.Mercator.GOOGLE,
            facecolor='black', edgecolor='black', linewidth=1.5, alpha=0.3
        )

    # Draw the Property Plot
    ax.add_geometries(
        [poly], crs=ccrs.Mercator.GOOGLE,
        facecolor='red', edgecolor='#FF0000', linewidth=2.5, alpha=0.3
    )

    # Draw Setback boundary (dashed red line, MCGM style)
    if setback_polys:
        ax.add_geometries(
            setback_polys, crs=ccrs.Mercator.GOOGLE,
            facecolor='none', edgecolor='red', linewidth=3.0, alpha=1.0,
            linestyle='--'
        )

    # Draw Abutting Lines (Green)
    if abutting_lines:
        ax.add_geometries(
            abutting_lines, crs=ccrs.Mercator.GOOGLE,
            facecolor='none', edgecolor='green', linewidth=4.0, alpha=0.9
        )

    # Add metric labels
    metrics = []
    if setback_area_m2 is not None:
        metrics.append(f"Setback area: {setback_area_m2:.2f} m^2")
    if max_road_width_m is not None and max_road_width_m > 0:
        metrics.append(f"Max road width: {max_road_width_m:.2f} m")
    if abutting_length_m is not None and abutting_length_m > 0:
        metrics.append(f"Abutting length: {abutting_length_m:.2f} m")
    if roads_touching is not None:
        metrics.append(f"Roads touching: {roads_touching}")
    if carriageway_entrances is not None:
        metrics.append(f"Carriageway entrances: {carriageway_entrances}")
    if metrics:
        ax.text(
            0.02, 0.98, "\n".join(metrics),
            transform=ax.transAxes,
            ha='left', va='top', fontsize=10, color='white',
            bbox=dict(facecolor='black', alpha=0.6, boxstyle='round,pad=0.3')
        )

    # 4. Save and return
    os.makedirs(output_dir, exist_ok=True)
    filename = f"property_map_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.0)
    plt.close(fig)

    return filepath
