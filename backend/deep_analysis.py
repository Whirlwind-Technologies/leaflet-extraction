"""
Deep analysis of leaflet extraction issues.
Run inside Docker: docker-compose exec backend python deep_analysis.py
"""
import os
import sys
import time
import json
from pathlib import Path
from io import BytesIO

# Set environment variables before importing paddle
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'
os.environ['FLAGS_pir_apply_inplace_pass'] = '0'
os.environ['FLAGS_allocator_strategy'] = 'naive_best_fit'
os.environ['FLAGS_cpu_deterministic'] = 'true'
os.environ['FLAGS_inner_op_parallelism'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'

import numpy as np
from PIL import Image
from pdf2image import convert_from_path

from app.core.image_processing.paddle_ocr_detector import PaddleOCRDetector
from app.core.image_processing.visual_boundary_detector import VisualBoundaryDetector


def analyze_pdf(pdf_path: str, max_pages: int = 3):
    """Analyze a PDF file and report on detection results."""
    print(f"\n{'='*70}")
    print(f"ANALYZING: {Path(pdf_path).name}")
    print(f"{'='*70}")

    # Get file info
    file_size = os.path.getsize(pdf_path)
    print(f"File size: {file_size / 1024 / 1024:.2f} MB")

    # Convert PDF to images
    print(f"\nConverting PDF to images (first {max_pages} pages)...")
    start = time.time()
    try:
        images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=max_pages)
        print(f"Converted {len(images)} pages in {time.time() - start:.1f}s")
    except Exception as e:
        print(f"ERROR converting PDF: {e}")
        return

    # Initialize detectors
    ocr_detector = PaddleOCRDetector()
    visual_detector = VisualBoundaryDetector()

    results = []

    for page_num, img in enumerate(images, 1):
        print(f"\n--- Page {page_num} ---")
        img_array = np.array(img)
        width, height = img.size
        print(f"Image size: {width}x{height}")

        # Save to bytes for testing
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_bytes = img_buffer.getvalue()
        print(f"Image bytes: {len(img_bytes) / 1024 / 1024:.2f} MB")

        # Step 1: Visual detection (fast)
        print("\n[Visual Detection]")
        start = time.time()
        try:
            visual_regions = visual_detector.detect_product_regions(img_array, width, height)
            visual_time = time.time() - start
            print(f"  Found {len(visual_regions)} regions in {visual_time:.2f}s")

            if visual_regions:
                areas = [r['bbox']['width'] * r['bbox']['height'] for r in visual_regions]
                avg_area = sum(areas) / len(areas)
                image_area = width * height
                print(f"  Avg region area: {avg_area:.0f} px² ({avg_area/image_area*100:.1f}% of image)")

                # Count oversized regions
                oversized = [a for a in areas if a > image_area * 0.2]
                if oversized:
                    print(f"  WARNING: {len(oversized)} oversized regions (>20% of image)")
        except Exception as e:
            print(f"  ERROR: {e}")
            visual_regions = []
            visual_time = 0

        # Step 2: OCR detection
        print("\n[OCR Detection]")
        start = time.time()
        try:
            text_boxes = ocr_detector.detect_text_boxes(img_bytes)
            ocr_time = time.time() - start
            print(f"  Found {len(text_boxes)} text boxes in {ocr_time:.2f}s")

            if text_boxes:
                # Classify text boxes
                prices = [b for b in text_boxes if ocr_detector._is_price_text(b.get('text', ''))]
                names = [b for b in text_boxes if ocr_detector._is_product_name_text(b.get('text', ''))]
                discounts = [b for b in text_boxes if ocr_detector._is_discount_text(b.get('text', ''))]
                print(f"  Classified: {len(prices)} prices, {len(names)} names, {len(discounts)} discounts")
        except Exception as e:
            print(f"  ERROR: {e}")
            text_boxes = []
            ocr_time = 0

        # Step 3: Full region detection (hybrid)
        print("\n[Hybrid Detection]")
        start = time.time()
        try:
            regions = ocr_detector.detect_product_regions(img_bytes, width, height)
            hybrid_time = time.time() - start
            print(f"  Found {len(regions)} regions in {hybrid_time:.2f}s")

            # Analyze sources
            sources = {}
            for r in regions:
                src = r.get('source', 'unknown')
                sources[src] = sources.get(src, 0) + 1
            print(f"  Sources: {sources}")

            # Show sample regions
            if regions:
                print(f"  Sample regions:")
                for i, r in enumerate(regions[:5]):
                    bbox = r['bbox']
                    text = r.get('combined_text', '')[:40]
                    src = r.get('source', 'unknown')
                    print(f"    {i}: {bbox['width']}x{bbox['height']} @ ({bbox['x']},{bbox['y']}) [{src}] \"{text}\"")
        except Exception as e:
            print(f"  ERROR: {e}")
            regions = []
            hybrid_time = 0

        results.append({
            'page': page_num,
            'size': f"{width}x{height}",
            'visual_regions': len(visual_regions),
            'text_boxes': len(text_boxes),
            'hybrid_regions': len(regions),
            'visual_time': visual_time,
            'ocr_time': ocr_time,
            'hybrid_time': hybrid_time,
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        print(f"  Page {r['page']}: {r['visual_regions']} visual, {r['text_boxes']} text, {r['hybrid_regions']} hybrid")
        print(f"           Times: visual={r['visual_time']:.1f}s, ocr={r['ocr_time']:.1f}s, hybrid={r['hybrid_time']:.1f}s")

    return results


def main():
    # Find not-good PDFs
    leaflets_dir = Path("/app/../leaflets/not good")
    if not leaflets_dir.exists():
        leaflets_dir = Path("/app/leaflets/not good")
    if not leaflets_dir.exists():
        print(f"Leaflets directory not found!")
        # Try relative path
        leaflets_dir = Path("../leaflets/not good")

    print(f"Looking for PDFs in: {leaflets_dir.absolute()}")

    pdfs = list(leaflets_dir.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDF files")

    for pdf in sorted(pdfs):
        analyze_pdf(str(pdf), max_pages=2)


if __name__ == "__main__":
    main()
