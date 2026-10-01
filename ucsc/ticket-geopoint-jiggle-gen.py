#!/usr/bin/env python3
"""
Add polygon-aware jiggle to parking tickets and create GeoJSON output
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
import hashlib
from shapely.geometry import Point, Polygon, shape
from shapely.ops import unary_union

def load_geojson_polygons(geojson_file):
    """Load parking lot polygons from GeoJSON"""
    with open(geojson_file, 'r') as f:
        geojson_data = json.load(f)
    
    polygons = {}
    skipped_features = []
    
    for idx, feature in enumerate(geojson_data['features']):
        try:
            props = feature.get('properties', {})
            objectid = props.get('OBJECTID', 'unknown')
            lot_name = props.get('NAME', 'unknown')
            
            # Check if geometry exists and is valid
            if not feature.get('geometry'):
                skipped_features.append({
                    'index': idx,
                    'objectid': objectid,
                    'name': lot_name,
                    'reason': 'Missing geometry'
                })
                continue
            
            if not objectid:
                skipped_features.append({
                    'index': idx,
                    'objectid': 'N/A',
                    'name': lot_name,
                    'reason': 'Missing OBJECTID'
                })
                continue
            
            geom = shape(feature['geometry'])
            
            # Validate geometry
            if geom.is_empty:
                skipped_features.append({
                    'index': idx,
                    'objectid': objectid,
                    'name': lot_name,
                    'reason': 'Empty geometry'
                })
                continue
            
            polygons[str(objectid)] = {
                'geometry': geom,
                'properties': props,
                'area': geom.area if hasattr(geom, 'area') else 0
            }
        except Exception as e:
            skipped_features.append({
                'index': idx,
                'objectid': props.get('OBJECTID', 'unknown'),
                'name': props.get('NAME', 'unknown'),
                'reason': f'Error: {str(e)}'
            })
            continue
    
    if skipped_features:
        print(f"\n⚠ Skipped {len(skipped_features)} invalid features:")
        print(f"{'Index':<8} {'OBJECTID':<12} {'Name':<30} {'Reason'}")
        print("-" * 80)
        for feature in skipped_features:
            name = feature['name'] if feature['name'] else 'N/A'
            print(f"{feature['index']:<8} {str(feature['objectid']):<12} {name:<30} {feature['reason']}")
        print()
    
    return polygons

def calculate_jiggle_radius(polygon_geom):
    """Calculate jiggle radius based on polygon area"""
    if not hasattr(polygon_geom, 'area'):
        return 0.0001  # Default: ~10 meters
    
    area = polygon_geom.area
    # jiggle_radius = sqrt(area) * 0.05
    # For degrees (lat/lon): ~0.00001 degrees ≈ 1 meter
    radius_degrees = np.sqrt(area) * 0.05
    return max(radius_degrees, 0.00001)  # Minimum 1 meter

def deterministic_random_point_in_polygon(polygon, ticket_id, max_attempts=50):
    """
    Generate a deterministic random point within polygon using ticket_id as seed
    Returns: (longitude, latitude) or None if fails
    """
    
    # Use ticket_id to seed random number generator deterministically
    hash_obj = hashlib.md5(str(ticket_id).encode())
    seed = int(hash_obj.hexdigest(), 16) % (2**32)
    rng = np.random.RandomState(seed)
    
    # Get bounding box
    minx, miny, maxx, maxy = polygon.bounds
    
    # Try to generate point within polygon
    for _ in range(max_attempts):
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        point = Point(x, y)
        
        if polygon.contains(point):
            return (x, y)
    
    # Fallback: return polygon centroid
    centroid = polygon.centroid
    return (centroid.x, centroid.y)

def apply_jiggle(point_coords, polygon_geom, ticket_id, jiggle_radius):
    """
    Apply jiggle to a point within polygon bounds
    Returns: (longitude, latitude)
    """
    
    # Start with deterministic point in polygon
    base_lon, base_lat = deterministic_random_point_in_polygon(polygon_geom, ticket_id)
    
    # Apply small random jiggle
    hash_obj = hashlib.md5(f"{ticket_id}_jiggle".encode())
    seed = int(hash_obj.hexdigest(), 16) % (2**32)
    rng = np.random.RandomState(seed)
    
    jiggle_lon = base_lon + rng.uniform(-jiggle_radius, jiggle_radius)
    jiggle_lat = base_lat + rng.uniform(-jiggle_radius, jiggle_radius)
    
    # Verify point is still in polygon
    jiggled_point = Point(jiggle_lon, jiggle_lat)
    if polygon_geom.contains(jiggled_point):
        return (jiggle_lon, jiggle_lat)
    else:
        # Fallback to base point
        return (base_lon, base_lat)

def process_tickets(tickets_csv, matches_csv, parking_lots_geojson, output_geojson):
    """Process tickets and add jiggled coordinates"""
    
    print(f"Loading parking lot polygons from: {parking_lots_geojson}")
    polygons = load_geojson_polygons(parking_lots_geojson)
    print(f"Loaded {len(polygons)} parking lot polygons\n")
    
    print(f"Reading matches from: {matches_csv}")
    matches_df = pd.read_csv(matches_csv)
    matches_dict = dict(zip(matches_df['canonical_location'], 
                            zip(matches_df['lot_number'], 
                                matches_df['objectid'])))
    print(f"Loaded {len(matches_dict)} location matches\n")
    
    print(f"Reading tickets from: {tickets_csv}")
    tickets_df = pd.read_csv(tickets_csv)
    print(f"Loaded {len(tickets_df)} tickets\n")
    
    # Parse datetime
    tickets_df['Issue Date / Time'] = pd.to_datetime(
        tickets_df['Issue Date / Time'], 
        format='%m/%d/%Y %I:%M %p'
    )
    
    # Find location column
    location_col = None
    for col in tickets_df.columns:
        if col.lower() == 'location':
            location_col = col
            break
    
    if not location_col:
        print(f"Error: Could not find 'Location' column")
        print(f"Available columns: {list(tickets_df.columns)}")
        exit(1)
    
    # Process tickets
    features = []
    matched_count = 0
    unmatched_count = 0
    
    print("Processing tickets with jiggle...")
    for idx, row in tickets_df.iterrows():
        location = row[location_col]
        
        # Check if location matches a parking lot
        if location not in matches_dict:
            unmatched_count += 1
            continue
        
        lot_number, objectid = matches_dict[location]
        objectid_str = str(objectid)
        
        if objectid_str not in polygons:
            unmatched_count += 1
            continue
        
        polygon_info = polygons[objectid_str]
        polygon_geom = polygon_info['geometry']
        
        # Calculate jiggle radius
        jiggle_radius = calculate_jiggle_radius(polygon_geom)
        
        # Apply jiggle
        lon, lat = apply_jiggle(None, polygon_geom, row['Ticket #'], jiggle_radius)
        
        # Create GeoJSON feature
        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [lon, lat]
            },
            'properties': {
                'ticket_id': str(row['Ticket #']),
                'date': row['Issue Date / Time'].strftime('%Y-%m-%d'),
                'time': row['Issue Date / Time'].strftime('%H:%M'),
                'datetime': row['Issue Date / Time'].isoformat(),
                'location': location,
                'lot_number': lot_number,
                'lot_name': polygon_info['properties'].get('NAME', ''),
                'violation_code': str(row['Viol Code']) if pd.notna(row['Viol Code']) else '',
                'violation': str(row['Violation']) if pd.notna(row['Violation']) else '',
                'make': str(row['Make']) if pd.notna(row['Make']) else '',
                'color': str(row['Color']) if pd.notna(row['Color']) else '',
                'status': str(row['Status']) if pd.notna(row['Status']) else '',
                'amount': str(row['Amount']) if pd.notna(row['Amount']) else '',
                'objectid': objectid
            }
        }
        
        features.append(feature)
        matched_count += 1
        
        if (matched_count + unmatched_count) % 5000 == 0:
            print(f"  Processed {matched_count + unmatched_count} tickets...")
    
    # Create GeoJSON
    geojson_output = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    # Write output
    with open(output_geojson, 'w') as f:
        json.dump(geojson_output, f)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print(f"Total tickets processed: {matched_count + unmatched_count}")
    print(f"Tickets with jiggled coordinates: {matched_count}")
    print(f"Tickets unmatched or missing polygon: {unmatched_count}")
    print(f"Match rate: {matched_count/(matched_count + unmatched_count)*100:.1f}%")
    print(f"\n✓ GeoJSON saved to: {output_geojson}")
    print(f"  File size: {Path(output_geojson).stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 jiggle_tickets.py <tickets_csv> <matches_csv> <parking_lots_geojson> [output_geojson]")
        print("\nExample:")
        print("  python3 jiggle_tickets.py tickets_cleaned.csv location_matches.csv parking_lots.geojson tickets_with_coordinates.geojson")
        exit(1)
    
    tickets_csv = sys.argv[1]
    matches_csv = sys.argv[2]
    parking_lots_geojson = sys.argv[3]
    output_geojson = sys.argv[4] if len(sys.argv) > 4 else "tickets_with_coordinates.geojson"
    
    for file in [tickets_csv, matches_csv, parking_lots_geojson]:
        if not Path(file).exists():
            print(f"Error: File not found at '{file}'")
            exit(1)
    
    process_tickets(tickets_csv, matches_csv, parking_lots_geojson, output_geojson)