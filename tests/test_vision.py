"""
ASTRA-AI Vision Module - Multi Image Test

Purpose:
- Automatically process all available sample images (up to 10).
- No target-text input and no user interaction.
- Analyze the complete image using OCR + YOLO object detection.
- Produce a human-readable description similar to a vision response.
- Include object/text locations, centers and bounding boxes.
- Keep terminal output short and write the detailed report to:
      tests/vision_output.txt

ASTRA-AI V1
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

SAMPLE_IMAGE_DIR = PROJECT_ROOT / "tests" / "vision_samples"
OUTPUT_FILE = PROJECT_ROOT / "tests" / "vision_output.txt"
MAX_IMAGES = 10
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


# ============================================================
# OUTPUT WRITER
# ============================================================

class OutputWriter:
    """Write the detailed Vision report to a text file."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(output_path, "w", encoding="utf-8")

    def write(self, text: str = "") -> None:
        self.file.write(str(text) + "\n")

    def separator(self, char: str = "=", length: int = 78) -> None:
        self.write(char * length)

    def close(self) -> None:
        try:
            self.file.flush()
            self.file.close()
        except Exception:
            pass


# ============================================================
# ENVIRONMENT
# ============================================================

def load_environment() -> None:
    """Load the project .env file when python-dotenv is available."""

    try:
        from dotenv import load_dotenv

        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
        else:
            load_dotenv(override=False)
    except ImportError:
        pass
    except Exception as error:
        print(f"[WARNING] .env loading failed: {error}")


# ============================================================
# SAMPLE IMAGE DISCOVERY
# ============================================================

def find_sample_images() -> list[Path]:
    """Find up to MAX_IMAGES supported image files."""

    if not SAMPLE_IMAGE_DIR.exists() or not SAMPLE_IMAGE_DIR.is_dir():
        print(f"[FAIL] Sample image directory not found: {SAMPLE_IMAGE_DIR}")
        return []

    images = [
        path
        for path in sorted(
            SAMPLE_IMAGE_DIR.iterdir(),
            key=lambda item: item.name.lower(),
        )
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]

    return images[:MAX_IMAGES]


# ============================================================
# IMAGE LOADING
# ============================================================

def load_image(image_path: Path):
    """Load an image with Pillow."""

    try:
        from PIL import Image

        image = Image.open(image_path)
        image.load()
        return image.convert("RGB")
    except Exception as error:
        print(f"[FAIL] Could not load {image_path.name}: {error}")
        return None


# ============================================================
# SAFE FORMATTERS
# ============================================================

def safe_float(value: Any, default: float = -1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_box(box: Any) -> str:
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        try:
            return (
                f"[x1={int(float(box[0]))}, "
                f"y1={int(float(box[1]))}, "
                f"x2={int(float(box[2]))}, "
                f"y2={int(float(box[3]))}]"
            )
        except (TypeError, ValueError):
            pass
    return str(box)


def position_name(center: Any, width: int, height: int) -> str:
    """Convert pixel center to a simple human-readable location."""

    try:
        x, y = int(center[0]), int(center[1])
    except (TypeError, ValueError, IndexError):
        return "unknown position"

    horizontal = "left" if x < width / 3 else "right" if x > width * 2 / 3 else "center"
    vertical = "top" if y < height / 3 else "bottom" if y > height * 2 / 3 else "middle"

    if horizontal == "center" and vertical == "middle":
        return "center"
    return f"{vertical}-{horizontal}"


# ============================================================
# NATURAL LANGUAGE DESCRIPTION
# ============================================================

def build_description(analysis: dict[str, Any]) -> str:
    """Create a natural-language description from VisionEngine results."""

    width = int(analysis.get("image_width", 0) or 0)
    height = int(analysis.get("image_height", 0) or 0)
    objects = analysis.get("objects", []) or []
    words = analysis.get("ocr_words", []) or []
    text = str(analysis.get("text", "") or "").strip()

    sentences: list[str] = []

    if objects:
        counts: dict[str, int] = {}
        for obj in objects:
            label = str(obj.get("label", "object")).strip()
            counts[label] = counts.get(label, 0) + 1

        parts = [
            f"{count} {label}" if count == 1 else f"{count} {label}s"
            for label, count in counts.items()
        ]

        if len(parts) == 1:
            sentences.append(f"I can see {parts[0]} in the image.")
        else:
            sentences.append(
                "I can see " + ", ".join(parts[:-1]) + " and " + parts[-1] + " in the image."
            )

        locations = []
        for obj in objects:
            label = str(obj.get("label", "object"))
            center = obj.get("center", (0, 0))
            locations.append(
                f"{label} is at {position_name(center, width, height)} "
                f"with center ({center[0]}, {center[1]}) and bounding box {format_box(obj.get('box'))}"
            )
        sentences.append("Object locations: " + "; ".join(locations) + ".")
    else:
        sentences.append("No supported objects were detected by YOLO.")

    if words:
        readable = []
        for word in words:
            word_text = str(word.get("text", "")).strip()
            if not word_text:
                continue
            center = word.get("center", (0, 0))
            readable.append(
                f"'{word_text}' is at {position_name(center, width, height)} "
                f"with center ({center[0]}, {center[1]}) and bounding box {format_box(word.get('box'))}"
            )

        if readable:
            sentences.append("Readable text locations: " + "; ".join(readable) + ".")
    elif text:
        compact = " ".join(text.split())
        sentences.append(f"Readable text: {compact[:1000]}")
    else:
        sentences.append("No readable text was detected by OCR.")

    return " ".join(sentences)


# ============================================================
# DETAILED IMAGE REPORT
# ============================================================

def write_image_report(
    writer: OutputWriter,
    vision,
    image_path: Path,
    index: int,
    image,
) -> dict[str, Any]:
    """Analyze one image and write all useful Vision information."""

    writer.separator()
    writer.write(f"IMAGE {index}: {image_path.name}")
    writer.separator("-")
    writer.write(f"Image size: {image.width} x {image.height}")
    writer.write()

    started = time.perf_counter()

    try:
        analysis = vision.analyze_image(image, preprocess_ocr=True)
    except Exception as error:
        writer.write(f"ANALYSIS ERROR: {error}")
        return {
            "loaded": True,
            "analysis": False,
            "ocr": False,
            "objects": False,
            "object_count": 0,
            "text_count": 0,
            "time": time.perf_counter() - started,
        }

    elapsed = time.perf_counter() - started

    text = str(analysis.get("text", "") or "")
    words = analysis.get("ocr_words", []) or []
    blocks = analysis.get("ocr_blocks", []) or []
    objects = analysis.get("objects", []) or []

    # --------------------------------------------------------
    # Human-readable response
    # --------------------------------------------------------

    writer.write("WHAT IS IN THE IMAGE?")
    writer.write(build_description(analysis))
    writer.write()

    # --------------------------------------------------------
    # OCR text
    # --------------------------------------------------------

    writer.write("OCR TEXT")
    if text:
        writer.write(text)
    else:
        writer.write("[NO READABLE TEXT]")
    writer.write()

    # --------------------------------------------------------
    # OCR words + coordinates
    # --------------------------------------------------------

    writer.write(f"OCR WORDS / TEXT COORDINATES ({len(words)})")
    if words:
        for number, word in enumerate(words, start=1):
            writer.write(
                f"[{number}] {word.get('text', '')} | "
                f"confidence={safe_float(word.get('confidence'), -1):.1f} | "
                f"position={position_name(word.get('center', (0, 0)), image.width, image.height)} | "
                f"center={word.get('center')} | "
                f"box={format_box(word.get('box'))}"
            )
    else:
        writer.write("[NONE]")
    writer.write()

    # --------------------------------------------------------
    # OCR blocks
    # --------------------------------------------------------

    writer.write(f"OCR BLOCKS ({len(blocks)})")
    if blocks:
        for number, block in enumerate(blocks, start=1):
            writer.write(
                f"[{number}] {block.get('text', '')} | "
                f"confidence={safe_float(block.get('confidence'), -1):.1f} | "
                f"box={format_box(block.get('box'))} | "
                f"center={block.get('center')}"
            )
    else:
        writer.write("[NONE]")
    writer.write()

    # --------------------------------------------------------
    # YOLO objects
    # --------------------------------------------------------

    writer.write(f"OBJECTS DETECTED ({len(objects)})")
    if objects:
        for number, obj in enumerate(objects, start=1):
            writer.write(
                f"[{number}] {obj.get('label', 'object')} | "
                f"confidence={safe_float(obj.get('confidence'), -1):.3f} | "
                f"position={position_name(obj.get('center', (0, 0)), image.width, image.height)} | "
                f"center={obj.get('center')} | "
                f"box={format_box(obj.get('box'))} | "
                f"size={obj.get('width', 0)} x {obj.get('height', 0)}"
            )
    else:
        writer.write("[NONE]")
    writer.write()

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    writer.write("TIMING")
    writer.write(f"OCR time: {analysis.get('ocr_time', 0):.3f} seconds")
    writer.write(
        f"Object detection time: "
        f"{analysis.get('object_detection_time', 0):.3f} seconds"
    )
    writer.write(f"Total analysis time: {elapsed:.3f} seconds")
    writer.write()

    writer.write("STATUS")
    writer.write(f"OCR available: {analysis.get('ocr_available', False)}")
    writer.write(
        f"Object detection available: "
        f"{analysis.get('object_detection_available', False)}"
    )
    writer.write(f"OCR success: {bool(text)}")
    writer.write(f"Objects found: {bool(objects)}")

    return {
        "loaded": True,
        "analysis": True,
        "ocr": bool(text),
        "objects": bool(objects),
        "object_count": len(objects),
        "text_count": len(words),
        "time": elapsed,
    }


# ============================================================
# MAIN
# ============================================================

def main() -> bool:
    """Run the complete automatic multi-image Vision test."""

    print("=" * 64)
    print("ASTRA-AI VISION TEST")
    print("=" * 64)

    load_environment()

    # --------------------------------------------------------
    # [1/8] Import
    # --------------------------------------------------------

    print("[1/8] Importing VisionEngine...")
    try:
        from vision.vision_engine import VisionEngine
        print("[OK] VisionEngine imported.")
    except Exception as error:
        print(f"[FAIL] VisionEngine import failed: {error}")
        return False

    # --------------------------------------------------------
    # [2/8] OCR environment
    # --------------------------------------------------------

    print("[2/8] Checking OCR environment...")
    api_key = os.getenv("OCR_SPACE_API_KEY", "").strip()
    if api_key:
        print("[OK] OCR environment ready.")
    else:
        print("[WARNING] OCR_SPACE_API_KEY is not configured.")
        print("         Object detection will still be tested.")

    # --------------------------------------------------------
    # [3/8] Images
    # --------------------------------------------------------

    print("[3/8] Checking sample images...")
    image_paths = find_sample_images()
    if not image_paths:
        return False
    print(f"[OK] {len(image_paths)} sample image(s) ready.")

    # --------------------------------------------------------
    # [4/8] Initialize
    # --------------------------------------------------------

    print("[4/8] Initializing VisionEngine...")
    try:
        vision = VisionEngine(ocr_language="eng")
        print("[OK] VisionEngine initialized.")
    except Exception as error:
        print(f"[FAIL] VisionEngine initialization failed: {error}")
        return False

    # --------------------------------------------------------
    # [5/8] Engine status
    # --------------------------------------------------------

    print("[5/8] Checking Vision engines...")
    print(f"[OK] OCR.space available: {vision.is_available()}")
    print(
        f"[OK] YOLO object detection available: "
        f"{vision.is_object_detection_available()}"
    )

    writer = OutputWriter(OUTPUT_FILE)
    writer.write("ASTRA-AI VISION TEST OUTPUT")
    writer.write("Automatic full-image OCR + object detection analysis")
    writer.write(f"Images tested: {len(image_paths)}")
    writer.write(f"Sample directory: {SAMPLE_IMAGE_DIR}")
    writer.write()

    # --------------------------------------------------------
    # [6/8] Process every image
    # --------------------------------------------------------

    print("[6/8] Starting multi-image Vision processing...")
    results: list[dict[str, Any]] = []
    total_start = time.perf_counter()

    for index, image_path in enumerate(image_paths, start=1):
        print(f"[{index}/{len(image_paths)}] Processing image: {image_path.name}")
        print(f"[{index}/{len(image_paths)}]   -> Full Vision analysis (OCR + objects)...")

        image = load_image(image_path)

        if image is None:
            writer.separator()
            writer.write(f"IMAGE {index}: {image_path.name}")
            writer.write("Image load failed.")
            results.append({
                "loaded": False,
                "analysis": False,
                "ocr": False,
                "objects": False,
                "object_count": 0,
                "text_count": 0,
                "time": 0.0,
            })
            print(f"[{index}/{len(image_paths)}]   -> FAILED (image load)")
            continue

        result = write_image_report(
            writer,
            vision,
            image_path,
            index,
            image,
        )
        results.append(result)

        ocr_status = "PASS" if result["ocr"] else "NONE"
        object_status = "FOUND" if result["objects"] else "NONE"

        print(
            f"[{index}/{len(image_paths)}]   -> Complete | "
            f"OCR={ocr_status} | "
            f"Objects={object_status} ({result['object_count']})"
        )

    total_elapsed = time.perf_counter() - total_start

    # --------------------------------------------------------
    # [7/8] Cached result
    # --------------------------------------------------------

    print("[7/8] Checking cached Vision results...")
    try:
        cached_analysis = vision.get_last_analysis()
        cached_ok = bool(cached_analysis)
        print(
            "[OK] Last combined Vision analysis available."
            if cached_ok
            else "[WARNING] Last combined Vision analysis is empty."
        )
    except Exception as error:
        cached_ok = False
        print(f"[WARNING] Cached analysis check failed: {error}")

    # --------------------------------------------------------
    # [8/8] Final report
    # --------------------------------------------------------

    print("[8/8] Generating final report...")

    total_images = len(results)
    analyzed = sum(1 for r in results if r.get("analysis"))
    ocr_count = sum(1 for r in results if r.get("ocr"))
    object_images = sum(1 for r in results if r.get("objects"))
    total_objects = sum(int(r.get("object_count", 0)) for r in results)
    total_text_items = sum(int(r.get("text_count", 0)) for r in results)

    writer.write()
    writer.separator()
    writer.write("FINAL VISION SUMMARY")
    writer.separator("-")
    writer.write(f"Images tested: {total_images}")
    writer.write(f"Images fully analyzed: {analyzed}/{total_images}")
    writer.write(f"Images with readable OCR text: {ocr_count}/{total_images}")
    writer.write(f"Images with detected objects: {object_images}/{total_images}")
    writer.write(f"Total OCR text items: {total_text_items}")
    writer.write(f"Total YOLO objects: {total_objects}")
    writer.write(f"Cached combined analysis: {'PASS' if cached_ok else 'FAIL'}")
    writer.write(f"Total processing time: {total_elapsed:.2f} seconds")
    writer.write()
    writer.write("The detailed report above describes what was detected, where it was detected, and the pixel coordinates.")
    writer.separator()
    writer.close()

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    print("Cleaning up VisionEngine...")
    try:
        vision.close()
        print("[OK] VisionEngine closed.")
    except Exception as error:
        print(f"[WARNING] Cleanup error: {error}")

    print()
    print("=" * 64)
    if analyzed == total_images and cached_ok:
        print("[SUCCESS] Vision test completed.")
    else:
        print("[WARNING] Vision test completed with partial failures.")
    print(f"Images processed : {analyzed}/{total_images}")
    print(f"Objects detected : {total_objects}")
    print(f"Text items       : {total_text_items}")
    print(f"Detailed output  : {OUTPUT_FILE}")
    print("=" * 64)
    print("No user input required.")
    print("All available images were processed automatically.")

    return analyzed == total_images


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
