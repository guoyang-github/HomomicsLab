#!/usr/bin/env python3
"""
Image processing utility for LLM Native mode.

When an LLM generates an image directly, this script handles:
- Saving base64-encoded images to files
- Format conversion (PNG/JPEG/WebP)
- Resizing and basic adjustments

Usage:
    # Save base64 image data
    python process_image.py --base64 "data:image/png;base64,iVBORw0KGgo..." -o output.png

    # Convert format
    python process_image.py -i input.png -o output.jpg --format jpeg

    # Resize
    python process_image.py -i input.png -o output.png --resize 800x600
"""

import argparse
import base64
import re
import sys
from pathlib import Path


def save_base64(data: str, output_path: Path) -> bool:
    """Save base64-encoded image data to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Strip data URI prefix if present
    if "," in data:
        data = data.split(",", 1)[1]

    data = data.replace("\n", "").replace("\r", "").replace(" ", "")

    try:
        image_bytes = base64.b64decode(data)
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        return True
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return False


def convert_format(input_path: Path, output_path: Path, fmt: str) -> bool:
    """Convert image to specified format using Pillow."""
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow required for format conversion. Install: pip install Pillow")
        return False

    try:
        img = Image.open(input_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format=fmt.upper())
        return True
    except Exception as e:
        print(f"Error converting image: {e}")
        return False


def resize_image(input_path: Path, output_path: Path, width: int, height: int) -> bool:
    """Resize image to specified dimensions."""
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow required for resizing. Install: pip install Pillow")
        return False

    try:
        img = Image.open(input_path)
        # Pillow 10+ compatibility: LANCZOS moved to Image.Resampling
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        img = img.resize((width, height), resample)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return True
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Process images for scientific illustration workflow")
    parser.add_argument("-i", "--input", help="Input image path")
    parser.add_argument("-o", "--output", required=True, help="Output image path")
    parser.add_argument("--base64", help="Base64-encoded image data")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], help="Output format")
    parser.add_argument("--resize", help="Resize to WIDTHxHEIGHT (e.g., 800x600)")

    args = parser.parse_args()
    output_path = Path(args.output)

    if args.base64:
        if save_base64(args.base64, output_path):
            print(f"Saved image to: {output_path}")
            sys.exit(0)
        sys.exit(1)

    if not args.input:
        print("Error: Either --input or --base64 is required")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    if args.resize:
        match = re.match(r"(\d+)x(\d+)", args.resize)
        if not match:
            print("Error: --resize must be in format WIDTHxHEIGHT (e.g., 800x600)")
            sys.exit(1)
        width, height = int(match.group(1)), int(match.group(2))
        if resize_image(input_path, output_path, width, height):
            print(f"Resized image saved to: {output_path}")
            sys.exit(0)
        sys.exit(1)

    if args.format:
        if convert_format(input_path, output_path, args.format):
            print(f"Converted image saved to: {output_path}")
            sys.exit(0)
        sys.exit(1)

    # Default: just copy
    import shutil
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(input_path, output_path)
    print(f"Copied image to: {output_path}")


if __name__ == "__main__":
    main()
