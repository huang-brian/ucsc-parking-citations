#!/usr/bin/env python3
"""
Match canonical parking ticket locations to parking_lots.csv
"""

import sys
from pathlib import Path
import pandas as pd
from difflib import SequenceMatcher

def load_parking_lots(lots_csv):
    """Load parking lots CSV and create lookup by lot number and name"""
    df = pd.read_csv(lots_csv)
    
    # Find relevant columns (by name, with preferences)
    lot_number_col = None
    lot_name_col = None
    objectid_col = None
    
    # Prefer "Lot #" over other number columns
    for col in df.columns:
        if col.strip() == 'Lot #':
            lot_number_col = col
            break
    
    if not lot_number_col:
        for col in df.columns:
            col_lower = col.lower()
            if 'number' in col_lower or 'num' in col_lower:
                lot_number_col = col
                break
    
    # Find name column
    for col in df.columns:
        col_lower = col.lower()
        if 'name' in col_lower:
            lot_name_col = col
            break
    
    # Find OBJECTID column
    for col in df.columns:
        col_lower = col.lower()
        if 'objectid' in col_lower:
            objectid_col = col
            break
    
    if not lot_number_col or not lot_name_col:
        print(f"Error: Could not find lot number or name columns")
        print(f"Available columns: {list(df.columns)}")
        exit(1)
    
    print(f"Using columns: LOT_NUMBER='{lot_number_col}', NAME='{lot_name_col}'")
    if objectid_col:
        print(f"               OBJECTID='{objectid_col}'")
    else:
        print(f"               OBJECTID: not found")
    print()
    
    # Create lookup dictionary
    lots = {}
    for _, row in df.iterrows():
        lot_num = str(row[lot_number_col]).strip()
        lot_name = str(row[lot_name_col]).strip()
        objectid = row[objectid_col] if objectid_col and pd.notna(row[objectid_col]) else None
        
        if lot_num and lot_num != 'nan':
            lots[lot_num] = {
                'name': lot_name,
                'objectid': objectid,
                'row': row.to_dict()
            }
    
    return lots, lot_number_col, lot_name_col, objectid_col

def similarity_score(str1, str2):
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()

def match_location_to_lot(location_name, lots):
    """
    Match a canonical location name to a parking lot.
    Returns: (lot_number, lot_name, confidence) or (None, None, 0)
    """
    
    location_upper = location_name.upper()
    
    # Extract lot number from location name (e.g., "118" from "118 GRANARY")
    location_parts = location_upper.split()
    location_lot_number = None
    
    if location_parts and location_parts[0].isdigit():
        location_lot_number = location_parts[0]
    
    # Strategy 1: Direct lot number match
    if location_lot_number and location_lot_number in lots:
        return (location_lot_number, lots[location_lot_number]['name'], 1.0)
    
    # Strategy 2: Fuzzy match on name
    best_match = None
    best_score = 0.6  # Minimum threshold
    
    for lot_number, lot_info in lots.items():
        lot_name = lot_info['name']
        score = similarity_score(location_name, lot_name)
        
        if score > best_score:
            best_score = score
            best_match = (lot_number, lot_name, score)
    
    if best_match:
        return best_match
    
    return (None, None, 0)

def process_matches(lots_csv, tickets_csv, output_matches, output_unmatched):
    """Match ticket locations to parking lots"""
    
    print(f"Loading parking lots from: {lots_csv}")
    lots, lot_number_col, lot_name_col, objectid_col = load_parking_lots(lots_csv)
    print(f"Loaded {len(lots)} parking lots\n")
    
    print(f"Reading ticket locations from: {tickets_csv}")
    tickets_df = pd.read_csv(tickets_csv)
    
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
    
    unique_locations = sorted(tickets_df[location_col].unique())
    print(f"Found {len(unique_locations)} unique locations\n")
    
    # Match each location
    matches = []
    unmatched = []
    
    print(f"{'Location':<50} {'Lot #':<8} {'Lot Name':<30} {'Confidence':<12}")
    print("-" * 100)
    
    for location in unique_locations:
        lot_number, lot_name, confidence = match_location_to_lot(location, lots)
        
        if lot_number:
            objectid = lots[lot_number]['objectid']
            matches.append({
                'canonical_location': location,
                'lot_number': lot_number,
                'lot_name': lot_name,
                'objectid': objectid,
                'confidence': confidence
            })
            status = "✓ MATCHED"
            print(f"{location:<50} {lot_number:<8} {lot_name:<30} {confidence:<12.2%} {status}")
        else:
            unmatched.append({
                'canonical_location': location,
                'match_attempted': True
            })
            status = "✗ NO MATCH"
            print(f"{location:<50} {'N/A':<8} {'N/A':<30} {'0.00':<12} {status}")
    
    # Write matches
    matches_df = pd.DataFrame(matches)
    matches_df.to_csv(output_matches, index=False)
    
    # Write unmatched
    unmatched_df = pd.DataFrame(unmatched)
    unmatched_df.to_csv(output_unmatched, index=False)
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}\n")
    print(f"Total unique locations: {len(unique_locations)}")
    print(f"Matched to parking lots: {len(matches)} ({len(matches)/len(unique_locations)*100:.1f}%)")
    print(f"Unmatched: {len(unmatched)} ({len(unmatched)/len(unique_locations)*100:.1f}%)")
    print(f"\n✓ Matches saved to: {output_matches}")
    print(f"✓ Unmatched saved to: {output_unmatched}\n")
    
    # Show low confidence matches for review
    low_confidence = [m for m in matches if m['confidence'] < 0.95]
    if low_confidence:
        print(f"⚠ Low confidence matches ({len(low_confidence)}) - review these:")
        for match in low_confidence:
            print(f"  {match['canonical_location']} → {match['lot_number']} {match['lot_name']} ({match['confidence']:.0%})")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 match_locations.py <parking_lots_csv> <tickets_csv> [output_matches] [output_unmatched]")
        print("\nExample:")
        print("  python3 match_locations.py parking_lots.csv tickets_cleaned.csv location_matches.csv location_unmatched.csv")
        exit(1)
    
    lots_csv = sys.argv[1]
    tickets_csv = sys.argv[2]
    output_matches = sys.argv[3] if len(sys.argv) > 3 else "location_matches.csv"
    output_unmatched = sys.argv[4] if len(sys.argv) > 4 else "location_unmatched.csv"
    
    if not Path(lots_csv).exists():
        print(f"Error: Parking lots CSV not found at '{lots_csv}'")
        exit(1)
    
    if not Path(tickets_csv).exists():
        print(f"Error: Tickets CSV not found at '{tickets_csv}'")
        exit(1)
    
    process_matches(lots_csv, tickets_csv, output_matches, output_unmatched)