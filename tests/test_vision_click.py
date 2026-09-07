"""
ASTRA-AI Vision Click Test - Blue "Sign In" Button

Test image:
    tests/vision_samples/sample_screen_3.png

Target:
    The filled blue "Sign In" button in the left login panel.

Workflow:
    Image -> OCR -> "Sign In" text -> blue-region matching ->
    button coordinates -> MouseController -> click
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

IMAGE_PATH = PROJECT_ROOT / "tests" / "vision_samples" / "sample_screen_3.png"
TARGET_TEXT = "Sign In"
OUTPUT_PATH = PROJECT_ROOT / "tests" / "vision_click_output.txt"


class TestLogger:
    """Console + text-file test logger."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.lines: list[str] = []
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str = ""):
        self.lines.append(message)
        print(message)

    def save(self):
        try:
            self.output_path.write_text(
                "\n".join(self.lines),
                encoding="utf-8",
            )
        except Exception as error:
            print(f"[WARNING] Could not save test output: {error}")


def load_environment():
    """Load the project .env when python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
        else:
            load_dotenv(override=False)

    except ImportError:
        pass
    except Exception as error:
        print(f"[WARNING] Environment loading failed: {error}")


def print_header(logger: TestLogger):
    logger.write()
    logger.write("=" * 64)
    logger.write("ASTRA-AI VISION + BLUE SIGN IN BUTTON TEST")
    logger.write("=" * 64)


def load_image(logger: TestLogger):
    logger.write()
    logger.write("[1/8] Loading sample image...")
    logger.write(f"[INFO] Image: {IMAGE_PATH}")

    if not IMAGE_PATH.exists():
        logger.write("[FAIL] Test image was not found.")
        return None

    try:
        from PIL import Image

        image = Image.open(IMAGE_PATH)
        image.load()

        logger.write("[OK] Image loaded successfully.")
        logger.write(f"[INFO] Size: {image.width} x {image.height}")
        logger.write(f"[INFO] Mode: {image.mode}")
        return image

    except Exception as error:
        logger.write(f"[FAIL] Image loading failed: {error}")
        return None


def normalize_text(value: str) -> str:
    """Normalize OCR text for tolerant matching."""
    if not value:
        return ""
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("\t", "")
    )


def find_target_in_blocks(blocks, target: str):
    """Find OCR blocks whose normalized text equals the target."""
    wanted = normalize_text(target)
    return [
        block
        for block in (blocks or [])
        if normalize_text(str(block.get("text", ""))) == wanted
    ]


def extract_coordinates(match):
    """Extract an OCR bounding box and center."""
    if not match:
        return None

    try:
        left = int(float(match.get("left", 0)))
        top = int(float(match.get("top", 0)))
        width = int(float(match.get("width", 0)))
        height = int(float(match.get("height", 0)))
        box = match.get("box")

        if (width <= 0 or height <= 0) and isinstance(box, (list, tuple)):
            if len(box) >= 4:
                left = int(float(box[0]))
                top = int(float(box[1]))
                width = int(float(box[2]))
                height = int(float(box[3]))

        if width <= 0 or height <= 0:
            return None

        return {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "right": left + width,
            "bottom": top + height,
            "center_x": left + width // 2,
            "center_y": top + height // 2,
            "box": box,
        }

    except Exception:
        return None


def run_ocr(logger: TestLogger, vision, image):
    logger.write()
    logger.write("[2/8] Running OCR...")

    try:
        start = time.perf_counter()
        text = vision.read_image(image, preprocess=True)
        elapsed = time.perf_counter() - start

        if text:
            logger.write(f"[OK] OCR completed in {elapsed:.2f}s.")
        else:
            logger.write(f"[WARNING] OCR returned no text ({elapsed:.2f}s).")

        try:
            blocks = vision.get_last_ocr_blocks()
        except Exception as error:
            logger.write(f"[WARNING] Could not read OCR blocks: {error}")
            blocks = []

        logger.write(f"[INFO] OCR blocks: {len(blocks)}")
        return text or "", blocks

    except Exception as error:
        logger.write(f"[FAIL] OCR failed: {error}")
        return "", []


def search_target(logger: TestLogger, vision, image, target: str, blocks):
    """
    Search with VisionEngine first, then use the OCR blocks already
    produced by read_image().
    """
    logger.write()
    logger.write(f"[3/8] Searching for target text: {target!r}")

    try:
        start = time.perf_counter()
        matches = vision.find_text_in_image(
            image,
            target,
            preprocess=True,
        )
        elapsed = time.perf_counter() - start

        if matches:
            logger.write(
                f"[OK] VisionEngine found {len(matches)} "
                f"text match(es) in {elapsed:.2f}s."
            )
            return matches

        logger.write(
            f"[INFO] Direct search found no exact "
            f"{target!r} match ({elapsed:.2f}s)."
        )

    except Exception as error:
        logger.write(f"[WARNING] Direct target search failed: {error}")

    matches = find_target_in_blocks(blocks, target)
    if matches:
        logger.write(
            f"[OK] OCR block matching found {len(matches)} "
            f"text match(es)."
        )
        return matches

    logger.write(f"[FAIL] Target text {target!r} was not detected.")
    return []


def detect_blue_regions(logger: TestLogger, image):
    """
    Detect connected blue UI regions.

    The color detector is intentionally separate from OCR:
    OCR finds the words, while this step identifies the filled
    blue button around the words.
    """
    logger.write()
    logger.write("[4/8] Detecting blue button regions...")

    try:
        import numpy as np
        from PIL import Image

        pixels = np.asarray(image.convert("RGB"))
        red = pixels[:, :, 0].astype(np.float32)
        green = pixels[:, :, 1].astype(np.float32)
        blue = pixels[:, :, 2].astype(np.float32)

        # Tuned to detect the bright blue UI used in sample_screen_3.png.
        mask = (
            (blue >= 120)
            & (blue > red * 1.45)
            & (blue > green * 1.15)
            & (red < 120)
        ).astype("uint8")

        regions = []

        try:
            import cv2

            mask = cv2.morphologyEx(
                mask * 255,
                cv2.MORPH_CLOSE,
                np.ones((3, 3), dtype=np.uint8),
            )

            count, _, stats, _ = cv2.connectedComponentsWithStats(
                mask,
                8,
            )

            for index in range(1, count):
                left = int(stats[index, cv2.CC_STAT_LEFT])
                top = int(stats[index, cv2.CC_STAT_TOP])
                width = int(stats[index, cv2.CC_STAT_WIDTH])
                height = int(stats[index, cv2.CC_STAT_HEIGHT])
                area = int(stats[index, cv2.CC_STAT_AREA])

                if area < 300 or width < 30 or height < 15:
                    continue

                regions.append({
                    "left": left,
                    "top": top,
                    "right": left + width,
                    "bottom": top + height,
                    "width": width,
                    "height": height,
                    "area": area,
                })

        except ImportError:
            # Fallback: use the overall blue bounding box if OpenCV
            # is not installed. In the sample this is sufficient for
            # the subsequent OCR-position matching.
            ys, xs = np.where(mask > 0)
            if len(xs):
                regions.append({
                    "left": int(xs.min()),
                    "top": int(ys.min()),
                    "right": int(xs.max()) + 1,
                    "bottom": int(ys.max()) + 1,
                    "width": int(xs.max() - xs.min() + 1),
                    "height": int(ys.max() - ys.min() + 1),
                    "area": int(len(xs)),
                })

        logger.write(f"[INFO] Blue regions detected: {len(regions)}")

        for index, region in enumerate(
            sorted(regions, key=lambda item: item["area"], reverse=True)[:10],
            start=1,
        ):
            logger.write(
                f"[INFO] Blue region #{index}: "
                f"box=({region['left']}, {region['top']}, "
                f"{region['right']}, {region['bottom']}), "
                f"size={region['width']}x{region['height']}, "
                f"area={region['area']}"
            )

        return regions

    except Exception as error:
        logger.write(f"[FAIL] Blue region detection failed: {error}")
        return []


def match_text_to_blue_button(logger: TestLogger, text_matches, blue_regions):
    """
    Select the blue region containing an OCR "Sign In" text center.

    This is important because sample_screen_3.png contains more than
    one "Sign In" text occurrence. The filled blue button is selected
    instead of the outlined top navigation button.
    """
    logger.write()
    logger.write("[5/8] Matching 'Sign In' text with blue button...")

    candidates = []

    for text_match in text_matches:
        text_box = extract_coordinates(text_match)
        if text_box is None:
            continue

        tx = text_box["center_x"]
        ty = text_box["center_y"]

        for region in blue_regions:
            inside = (
                region["left"] <= tx <= region["right"]
                and region["top"] <= ty <= region["bottom"]
            )
            if not inside:
                continue

            aspect = region["width"] / max(region["height"], 1)

            # Strongly prefer horizontal button-like regions.
            score = float(region["area"])
            if aspect >= 3.0:
                score += 100000
            if region["width"] >= 200:
                score += 50000
            if 30 <= region["height"] <= 100:
                score += 25000

            candidates.append({
                "text_match": text_match,
                "text_box": text_box,
                "region": region,
                "score": score,
            })

    if not candidates:
        logger.write(
            "[FAIL] Could not match OCR 'Sign In' "
            "to a blue button region."
        )
        return None

    selected = max(candidates, key=lambda item: item["score"])
    region = selected["region"]

    target = {
        "text_match": selected["text_match"],
        "text_box": selected["text_box"],
        "left": region["left"],
        "top": region["top"],
        "width": region["width"],
        "height": region["height"],
        "right": region["right"],
        "bottom": region["bottom"],
        "center_x": region["left"] + region["width"] // 2,
        "center_y": region["top"] + region["height"] // 2,
        "box": [
            region["left"],
            region["top"],
            region["right"],
            region["bottom"],
        ],
        "area": region["area"],
    }

    logger.write("[OK] OCR target matched with blue button.")
    logger.write(
        f"[INFO] Selected button box: "
        f"({target['left']}, {target['top']}, "
        f"{target['right']}, {target['bottom']})"
    )
    logger.write(
        f"[INFO] Button center: "
        f"({target['center_x']}, {target['center_y']})"
    )

    return target


def display_ocr_preview(logger: TestLogger, text: str, max_lines: int = 25):
    logger.write()
    logger.write("---------- OCR PREVIEW ----------")

    if not text:
        logger.write("[NO OCR TEXT]")
        logger.write("--------------------------------")
        return

    lines = text.splitlines()
    for line in lines[:max_lines]:
        logger.write(line)

    if len(lines) > max_lines:
        logger.write(f"... {len(lines) - max_lines} more line(s)")

    logger.write("--------------------------------")


def display_target(logger: TestLogger, target):
    match = target["text_match"]

    try:
        confidence = float(match.get("confidence", -1))
    except Exception:
        confidence = -1.0

    logger.write()
    logger.write("---------- BLUE BUTTON DETECTION ----------")
    logger.write(f"Detected text : {match.get('text', '')!r}")
    logger.write(f"Confidence    : {confidence:.1f}")
    logger.write(f"Left          : {target['left']}")
    logger.write(f"Top           : {target['top']}")
    logger.write(f"Width         : {target['width']}")
    logger.write(f"Height        : {target['height']}")
    logger.write(f"Right         : {target['right']}")
    logger.write(f"Bottom        : {target['bottom']}")
    logger.write(f"Bounding box  : {target['box']}")
    logger.write(
        f"Center        : "
        f"({target['center_x']}, {target['center_y']})"
    )
    logger.write(f"Blue area     : {target['area']}")
    logger.write("-------------------------------------------")


def load_mouse_controller(logger: TestLogger):
    """Import the project's MouseController."""
    logger.write()
    logger.write("[6/8] Loading MouseController...")

    try:
        from automation.mouse_controller import MouseController

        logger.write("[OK] MouseController imported.")
        return MouseController

    except ImportError as error:
        logger.write("[FAIL] MouseController import failed.")
        logger.write(f"Error: {error}")
        logger.write(
            f"Expected file: "
            f"{PROJECT_ROOT / 'automation' / 'mouse_controller.py'}"
        )
        return None


def click_target(logger: TestLogger, target):
    """Move to the button center and perform a left click."""
    MouseController = load_mouse_controller(logger)
    if MouseController is None:
        return False

    x = target["center_x"]
    y = target["center_y"]

    try:
        import pyautogui

        current = pyautogui.position()
        logger.write(
            f"[INFO] Current mouse position: "
            f"({current.x}, {current.y})"
        )
    except Exception:
        pass

    try:
        mouse = MouseController()
    except Exception as error:
        logger.write(
            f"[FAIL] MouseController initialization failed: {error}"
        )
        return False

    logger.write(f"[INFO] Target center: ({x}, {y})")
    logger.write()
    logger.write("Moving mouse to detected blue Sign In button...")

    try:
        moved = mouse.move_to(
            x,
            y,
            duration=0.4,
        )
    except Exception as error:
        logger.write(f"[FAIL] Mouse move failed: {error}")
        return False

    if not moved:
        logger.write(
            "[FAIL] MouseController.move_to() returned False."
        )
        return False

    logger.write("[OK] Mouse moved to blue button center.")
    logger.write()
    logger.write("[7/8] Clicking detected blue Sign In button...")

    try:
        clicked = mouse.left_click()
    except Exception as error:
        logger.write(f"[FAIL] Mouse click failed: {error}")
        return False

    if clicked:
        logger.write("[OK] Left click completed successfully.")
        return True

    logger.write(
        "[FAIL] MouseController.left_click() returned False."
    )
    return False


def main():
    logger = TestLogger(OUTPUT_PATH)
    print_header(logger)

    logger.write("Target image : sample_screen_3.png")
    logger.write(f"Target text  : {TARGET_TEXT!r}")
    logger.write("Target type  : Filled blue Sign In button")
    logger.write("Mode         : Automatic / No user input")

    load_environment()

    # --------------------------------------------------------
    # VisionEngine
    # --------------------------------------------------------

    logger.write()
    logger.write("[0/8] Importing VisionEngine...")

    try:
        from vision.vision_engine import VisionEngine
        logger.write("[OK] VisionEngine imported.")
    except Exception as error:
        logger.write(f"[FAIL] VisionEngine import failed: {error}")
        logger.save()
        return False

    logger.write()
    logger.write("[0/8] Initializing VisionEngine...")

    vision = None

    try:
        vision = VisionEngine(ocr_language="eng")
        logger.write("[OK] VisionEngine initialized.")
    except Exception as error:
        logger.write(
            f"[FAIL] VisionEngine initialization failed: {error}"
        )
        logger.save()
        return False

    try:
        available = bool(vision.is_available())
        logger.write(f"[INFO] OCR.space available: {available}")

        if not available:
            logger.write("[FAIL] OCR.space is not available.")
            vision.close()
            logger.save()
            return False

    except Exception as error:
        logger.write(
            f"[WARNING] OCR availability check failed: {error}"
        )

    # --------------------------------------------------------
    # Image
    # --------------------------------------------------------

    image = load_image(logger)
    if image is None:
        try:
            vision.close()
        except Exception:
            pass
        logger.save()
        return False

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    text, blocks = run_ocr(
        logger,
        vision,
        image,
    )
    display_ocr_preview(logger, text)

    # --------------------------------------------------------
    # Text target
    # --------------------------------------------------------

    text_matches = search_target(
        logger,
        vision,
        image,
        TARGET_TEXT,
        blocks,
    )

    if not text_matches:
        logger.write()
        logger.write(
            "[FAIL] Cannot continue because "
            "'Sign In' text was not detected."
        )
        try:
            vision.close()
        except Exception:
            pass
        logger.save()
        return False

    # --------------------------------------------------------
    # Blue target
    # --------------------------------------------------------

    blue_regions = detect_blue_regions(
        logger,
        image,
    )

    if not blue_regions:
        logger.write(
            "[FAIL] Cannot continue because "
            "no blue UI region was detected."
        )
        try:
            vision.close()
        except Exception:
            pass
        logger.save()
        return False

    target = match_text_to_blue_button(
        logger,
        text_matches,
        blue_regions,
    )

    if target is None:
        try:
            vision.close()
        except Exception:
            pass
        logger.save()
        return False

    display_target(logger, target)

    # --------------------------------------------------------
    # Mouse
    # --------------------------------------------------------

    click_passed = click_target(
        logger,
        target,
    )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    logger.write()
    logger.write("[8/8] Cleaning up VisionEngine...")

    try:
        vision.close()
        logger.write("[OK] VisionEngine closed.")
    except Exception as error:
        logger.write(
            f"[WARNING] VisionEngine cleanup error: {error}"
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    logger.write()
    logger.write("=" * 64)
    logger.write("VISION + BLUE SIGN IN TEST RESULT")
    logger.write("=" * 64)
    logger.write(f"Image              : {IMAGE_PATH.name}")
    logger.write(f"Target             : {TARGET_TEXT!r}")
    logger.write("Target detected    : PASS")
    logger.write("Blue button        : PASS")
    logger.write(
        f"Coordinates        : PASS "
        f"({target['center_x']}, {target['center_y']})"
    )
    logger.write(f"Bounding box       : {target['box']}")
    logger.write(
        f"Mouse click        : {'PASS' if click_passed else 'FAIL'}"
    )
    logger.write()

    if click_passed:
        logger.write(
            "[SUCCESS] Blue Sign In button was "
            "detected and clicked."
        )
    else:
        logger.write(
            "[FAIL] Vision detected the blue "
            "Sign In button, but mouse click failed."
        )

    logger.write()
    logger.write(f"Detailed output: {OUTPUT_PATH}")
    logger.write("=" * 64)

    logger.save()
    return click_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
