#!/usr/bin/env python3
"""
Generic figure validation script — customize per-journal rules.

Checks: resolution (DPI), color mode, file size.

Usage:
    python validate_figure.py figure.png
    python validate_figure.py figure.png --min-dpi 450 --max-mb 5 --mode CMYK
"""

import argparse
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    raise SystemExit(1)


def validate_figure(image_path, min_dpi=300, max_mb=10, required_mode='RGB'):
    """Validate a figure image against publication standards.

    Args:
        image_path: Path to the image file
        min_dpi: Minimum required DPI (default 300)
        max_mb: Maximum file size in MB (default 10)
        required_mode: Required color mode, e.g. 'RGB', 'CMYK', or None to skip

    Returns:
        bool: True if all checks pass, False otherwise
    """
    img = Image.open(image_path)
    issues = []

    dpi = img.info.get('dpi', (72, 72))
    if dpi[0] < min_dpi or dpi[1] < min_dpi:
        issues.append(f"Resolution {dpi[0]}x{dpi[1]} DPI below {min_dpi}")

    if required_mode and img.mode != required_mode:
        issues.append(f"Color mode {img.mode}; {required_mode} recommended")

    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > max_mb:
        issues.append(f"File size {size_mb:.1f} MB exceeds {max_mb} MB")

    print(f"=== Validation: {os.path.basename(image_path)} ===")
    print(f"Dimensions: {img.size[0]} x {img.size[1]} px | DPI: {dpi[0]} x {dpi[1]} | Mode: {img.mode}")
    if issues:
        print(f"ISSUES ({len(issues)}):", *issues, sep="\n  - ")
    else:
        print("All checks PASSED")

    return len(issues) == 0


def main():
    parser = argparse.ArgumentParser(description="Validate figure images for publication")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--min-dpi", type=int, default=300, help="Minimum DPI (default: 300)")
    parser.add_argument("--max-mb", type=float, default=10, help="Maximum file size in MB (default: 10)")
    parser.add_argument("--mode", default="RGB", help="Required color mode, e.g. RGB, CMYK (default: RGB)")
    args = parser.parse_args()

    success = validate_figure(
        args.image,
        min_dpi=args.min_dpi,
        max_mb=args.max_mb,
        required_mode=args.mode
    )
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
