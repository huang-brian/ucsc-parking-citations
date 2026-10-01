#!/usr/bin/env python3
"""
Generate violation color mapping with shades for letter suffixes
"""

import json
from pathlib import Path

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color"""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def shade_color(hex_color, factor):
    """
    Shade a color lighter (factor > 1) or darker (factor < 1)
    factor=1.3 makes it 30% lighter
    factor=0.7 makes it 30% darker
    """
    r, g, b = hex_to_rgb(hex_color)
    
    if factor > 1:  # Lighten
        r = min(255, int(r + (255 - r) * (factor - 1)))
        g = min(255, int(g + (255 - g) * (factor - 1)))
        b = min(255, int(b + (255 - b) * (factor - 1)))
    else:  # Darken
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
    
    return rgb_to_hex((r, g, b))

def generate_violation_colors():
    """
    Generate color mapping for all violations
    Groups by base number/code, assigns base color, then shades for letter suffixes
    """
    
    violations = [
        "21",
        "22507.8",
        "22507.8 (B) CVC",
        "22507.8 (C) CVC",
        "22514",
        "28",
        "35 (A) INV",
        "35 (A) UC",
        "35 (B) INV",
        "35B",
        "35C",
        "36",
        "36 INV",
        "36 UC",
        "38",
        "40",
        "40 INV",
        "41",
        "41(B)",
        "42",
        "42(A)",
        "42(A)UC",
        "43 UC",
        "43A",
        "44",
        "44 (A)UC",
        "45",
        "49",
        "54",
        "56",
        "W21",
        "W22507.8",
        "W22514",
        "W35A",
        "W35B",
        "W35C",
        "W36",
        "W40",
        "W41",
        "W41(B)",
        "W42",
        "W42(A)",
        "W43",
        "W44"
    ]
    
    # Base colors for different violation groups
    base_colors = {
        '21': '#FF6B6B',      # Red
        '22': '#E74C3C',      # Dark red
        '28': '#C0392B',      # Very dark red
        '35': '#3498DB',      # Bright blue
        '36': '#2ECC71',      # Green
        '38': '#27AE60',      # Dark green
        '40': '#9B59B6',      # Dark purple
        '41': '#E67E22',      # Dark orange
        '42': '#F39C12',      # Orange
        '43': '#4ECDC4',      # Teal
        '44': '#45B7D1',      # Sky blue
        '45': '#FFA07A',      # Light salmon
        '49': '#98D8C8',      # Mint
        '54': '#F7DC6F',      # Yellow
        '56': '#BB8FCE',      # Purple
        'W21': '#FF8C42',     # Burnt orange
        'W22': '#DC143C',     # Crimson
        'W35': '#1E90FF',     # Dodger blue
        'W36': '#32CD32',     # Lime green
        'W40': '#8A2BE2',     # Blue violet
        'W41': '#FF7F50',     # Coral
        'W42': '#20B2AA',     # Light sea green
        'W43': '#696969',     # Dim gray
        'W44': '#B22222'      # Firebrick
    }
    
    color_map = {}
    shade_factors = {
        'A': 1.2,   # A = 20% lighter
        'B': 1.0,   # B = base color
        'C': 0.8    # C = 20% darker
    }
    
    for violation in violations:
        # Determine base color by extracting base code
        base_code = violation
        
        # Handle W codes (W21, W22507.8, W35A, etc.)
        if violation.startswith('W'):
            # Extract W + following digits and dots
            i = 1
            while i < len(violation) and (violation[i].isdigit() or violation[i] == '.'):
                i += 1
            base_code = violation[:i]
        else:
            # For numeric codes, extract leading digits and dots
            i = 0
            while i < len(violation) and (violation[i].isdigit() or violation[i] == '.'):
                i += 1
            base_code = violation[:i] if i > 0 else violation
        
        base_color = base_colors.get(base_code, '#95A5A6')  # Default gray
        
        # Determine shade factor based on letter suffix
        shade_factor = 1.0
        for letter, factor in shade_factors.items():
            if letter in violation.upper():
                shade_factor = factor
                break
        
        # Apply shade
        final_color = shade_color(base_color, shade_factor)
        color_map[violation] = final_color
    
    return color_map, violations

def generate_legend(color_map, violations):
    """Generate a legend grouping violations by base code"""
    
    legend = {}
    
    for violation in sorted(violations):
        # Extract base code
        base_code = violation
        
        if violation.startswith('W'):
            i = 1
            while i < len(violation) and (violation[i].isdigit() or violation[i] == '.'):
                i += 1
            base_code = violation[:i]
        else:
            i = 0
            while i < len(violation) and (violation[i].isdigit() or violation[i] == '.'):
                i += 1
            base_code = violation[:i] if i > 0 else violation
        
        if base_code not in legend:
            legend[base_code] = []
        
        legend[base_code].append({
            'code': violation,
            'color': color_map[violation]
        })
    
    return legend

if __name__ == "__main__":
    print("Generating violation color mapping...\n")
    
    color_map, violations = generate_violation_colors()
    legend = generate_legend(color_map, violations)
    
    # Prepare output
    output = {
        'colors': color_map,
        'legend': legend
    }
    
    # Write to JSON
    output_file = "violation_colors.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Generated colors for {len(violations)} violation types")
    print(f"\nViolation groups and colors:")
    print("-" * 60)
    
    for base_code in sorted(legend.keys()):
        violations_in_group = legend[base_code]
        print(f"\n{base_code}:")
        for v in violations_in_group:
            print(f"  {v['code']:<15} {v['color']}")
    
    print(f"\n✓ Saved to: {output_file}")