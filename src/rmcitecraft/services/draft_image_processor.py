"""
Draft Registration Card Image Processor.

Analyzes and processes draft registration card images to create standardized
combined images (front + back cards) with consistent formatting.

Handles multiple image types:
- Type 1: Pre-combined horizontal (both cards side-by-side, ready to use)
- Type 2: Separate Young Men cards (both landscape, need combination)
- Type 3: Old Men with portrait back (back card rotated, needs rotation + combination)
- Type 4: Old Men raw with borders (full processing pipeline)
- Type 5: Pre-combined vertical (cards stacked top/bottom)

Legacy types (deprecated):
- Type A: Already combined (use Type 1 instead)
- Type B/C/D: Separate cards (use Type 2/3/4 instead)
- Type E: Vertical stacked (use Type 5 instead)

Uses ImageMagick for:
- Connected component analysis (detect card structure)
- Image manipulation (deskew, rotate, trim, combine)
"""

import asyncio
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from loguru import logger

from rmcitecraft.config.settings import get_config


@dataclass
class ImageRegion:
    """Represents a detected card region from connected component analysis."""

    width: int
    height: int
    x: int
    y: int
    area: int

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio of this region."""
        return self.width / self.height if self.height > 0 else 0.0

    @property
    def x_end(self) -> int:
        """Calculate ending x-coordinate."""
        return self.x + self.width

    @property
    def y_end(self) -> int:
        """Calculate ending y-coordinate."""
        return self.y + self.height


@dataclass
class ImageTypeResult:
    """Result of image type detection using connected component analysis."""

    type: str  # "Type 1", "Type 5", "Unknown", or legacy "A", "E"
    confidence: str  # "high", "medium", "low"
    needs_processing: bool
    regions: List[ImageRegion]
    detection_method: str  # "connected_components", "aspect_ratio"


@dataclass
class ImageAnalysis:
    """Results of image analysis."""

    width: int
    height: int
    aspect_ratio: float
    colorspace: str
    needs_second_image: bool
    needs_deskew: bool
    needs_rotation: bool
    estimated_type: str  # Type 1-5, or legacy A-E
    skew_angle: Optional[float] = None
    type_result: Optional[ImageTypeResult] = None  # Detailed detection results


class DraftImageProcessor:
    """Analyze and process draft registration card images."""

    # Image analysis thresholds
    LARGE_REGION_THRESHOLD = 800_000  # Minimum pixels for a card region (0.8M)
    REGION_GAP_TOLERANCE = 50  # Max pixels between adjacent cards to merge
    DESKEW_THRESHOLD = "40%"  # Threshold for separating paper (white) from background (black)
    TYPE_5_HEIGHT_THRESHOLD = 1800  # Minimum height in pixels for Type 5 (vertical combined cards)

    def __init__(self, keep_originals: Optional[bool] = None):
        """
        Initialize image processor.

        Args:
            keep_originals: If True, keep original downloaded images
                          If False, delete after successful processing
                          If None, use value from config (default)
        """
        config = get_config()

        # Load settings from config or use provided value
        self.keep_originals = (
            keep_originals if keep_originals is not None else config.draft_image_keep_originals
        )

        # Load processing parameters from config
        self.COMBINED_THRESHOLD = config.draft_image_combined_threshold
        self.SINGLE_CARD_MIN = config.draft_image_single_card_min
        self.SKEW_TOLERANCE = config.draft_image_skew_tolerance
        self.DESKEW_THRESHOLD = config.draft_image_deskew_threshold
        self.TRIM_FUZZ = config.draft_image_trim_fuzz
        self.TARGET_ASPECT = 1.66  # Target aspect ratio for combined images

    async def detect_image_type(self, image_path: Path) -> ImageTypeResult:
        """
        Detect draft card image type using connected component analysis.

        Uses ImageMagick to identify distinct card regions and determine arrangement:
        - Type 1: 2 regions side-by-side (horizontal)
        - Type 5: 2 regions stacked (vertical)
        - Unknown: Fallback to aspect ratio method

        Args:
            image_path: Path to image file

        Returns:
            ImageTypeResult with type classification and detected regions
        """
        logger.debug(f"Detecting image type via connected components: {image_path.name}")

        try:
            # Run connected component analysis
            regions = await self._analyze_connected_components(image_path)

            # Filter to large regions (actual cards, not noise)
            large_regions = [
                r for r in regions if r.area > self.LARGE_REGION_THRESHOLD
            ]

            logger.debug(
                f"  Found {len(regions)} total regions, {len(large_regions)} large regions"
            )

            # Type 1: Two cards side-by-side (horizontal arrangement)
            if len(large_regions) == 2 and self._is_horizontal_arrangement(
                large_regions
            ):
                logger.info(
                    f"✓ Image Type: Type 1 (Pre-combined horizontal) - Ready to use, no processing needed"
                )
                return ImageTypeResult(
                    type="Type 1",
                    confidence="high",
                    needs_processing=False,
                    regions=large_regions,
                    detection_method="connected_components",
                )

            # Type 5: Two cards stacked vertically
            if len(large_regions) == 2 and self._is_vertical_arrangement(
                large_regions
            ):
                logger.info(
                    f"✓ Image Type: Type 5 (Pre-combined vertical) - Stacked cards, ready to use"
                )
                return ImageTypeResult(
                    type="Type 5",
                    confidence="high",
                    needs_processing=False,  # or True if we want to rotate/recombine
                    regions=large_regions,
                    detection_method="connected_components",
                )

            # Fallback: Unknown structure, use aspect ratio method
            logger.debug(
                f"  Connected components inconclusive ({len(large_regions)} large regions), "
                "falling back to aspect ratio"
            )
            return await self._detect_by_aspect_ratio(image_path)

        except Exception as e:
            logger.warning(
                f"Connected component analysis failed: {e}, falling back to aspect ratio"
            )
            return await self._detect_by_aspect_ratio(image_path)

    async def _analyze_connected_components(
        self, image_path: Path
    ) -> List[ImageRegion]:
        """
        Run ImageMagick connected component analysis to detect card regions.

        Process:
        1. Convert to grayscale
        2. Threshold to separate paper (white) from background (black)
        3. Find connected components (distinct white regions)
        4. Filter to regions > 50K pixels (ignore noise)

        Args:
            image_path: Path to image file

        Returns:
            List of detected regions (white/paper areas)
        """
        # Create temp output path for analysis result
        temp_output = image_path.parent / f"{image_path.stem}_cc_temp.png"

        cmd = [
            "magick",
            str(image_path),
            "-colorspace",
            "Gray",
            "-threshold",
            self.DESKEW_THRESHOLD,
            "-define",
            "connected-components:verbose=true",
            "-define",
            "connected-components:area-threshold=50000",  # Ignore small noise
            "-connected-components",
            "8",  # 8-way connectivity
            str(temp_output),
        ]

        result = await self._run_command(cmd)

        # Parse the stderr output (ImageMagick writes verbose info to stderr)
        regions = self._parse_connected_components_output(result)

        # Cleanup temp file
        temp_output.unlink(missing_ok=True)

        return regions

    def _parse_connected_components_output(self, output: str) -> List[ImageRegion]:
        """
        Parse ImageMagick connected components output into region objects.

        Output format:
        "227: 1804x1208+1+298 904.7,904.3 2.15338e+06 gray(255)"

        Args:
            output: stderr output from ImageMagick

        Returns:
            List of ImageRegion objects (only white regions - gray(255))
        """
        regions = []

        for line in output.split("\n"):
            # Only parse white regions (paper cards)
            if "gray(255)" not in line:
                continue

            # Parse: "id: WIDTHxHEIGHT+X+Y centroid area color"
            match = re.match(
                r"\s*\d+:\s*(\d+)x(\d+)\+(\d+)\+(\d+)\s+[\d.]+,[\d.]+\s+([\d.e+]+)",
                line,
            )
            if match:
                width, height, x, y, area = match.groups()
                region = ImageRegion(
                    width=int(width),
                    height=int(height),
                    x=int(x),
                    y=int(y),
                    area=int(float(area)),
                )
                regions.append(region)
                logger.debug(
                    f"    Region: {region.width}x{region.height}+{region.x}+{region.y} "
                    f"({region.area / 1e6:.2f}M pixels)"
                )

        return regions

    def _is_horizontal_arrangement(self, regions: List[ImageRegion]) -> bool:
        """
        Check if two regions are arranged side-by-side (Type 1).

        Detection criteria:
        - Exactly 2 regions
        - Right card starts where left card ends (±tolerance)
        - Cards are adjacent horizontally

        Args:
            regions: List of detected regions

        Returns:
            True if regions are side-by-side
        """
        if len(regions) != 2:
            return False

        # Sort by x-coordinate (left to right)
        left, right = sorted(regions, key=lambda r: r.x)

        # Check: right card starts where left card ends (±50 pixel tolerance)
        left_end = left.x_end
        gap = abs(right.x - left_end)

        logger.debug(
            f"    Horizontal check: left ends at x={left_end}, "
            f"right starts at x={right.x}, gap={gap}px"
        )

        return gap < self.REGION_GAP_TOLERANCE

    def _is_vertical_arrangement(self, regions: List[ImageRegion]) -> bool:
        """
        Check if two regions are stacked vertically (Type 5).

        Detection criteria:
        - Exactly 2 regions
        - Bottom card starts where top card ends (±tolerance)
        - Cards are adjacent vertically

        Args:
            regions: List of detected regions

        Returns:
            True if regions are stacked vertically
        """
        if len(regions) != 2:
            return False

        # Sort by y-coordinate (top to bottom)
        top, bottom = sorted(regions, key=lambda r: r.y)

        # Check: bottom card starts where top card ends (±50 pixel tolerance)
        top_end = top.y_end
        gap = abs(bottom.y - top_end)

        logger.debug(
            f"    Vertical check: top ends at y={top_end}, "
            f"bottom starts at y={bottom.y}, gap={gap}px"
        )

        return gap < self.REGION_GAP_TOLERANCE

    async def _detect_by_aspect_ratio(self, image_path: Path) -> ImageTypeResult:
        """
        Fallback detection method using aspect ratio (legacy approach).

        Args:
            image_path: Path to image file

        Returns:
            ImageTypeResult based on aspect ratio heuristics
        """
        width, height, _ = await self._get_image_properties(image_path)
        aspect_ratio = width / height

        if aspect_ratio >= self.COMBINED_THRESHOLD:
            # Likely Type 1 (or legacy Type A)
            logger.debug(
                f"    Aspect ratio {aspect_ratio:.2f} >= {self.COMBINED_THRESHOLD} "
                "→ Type 1 (combined horizontal)"
            )
            return ImageTypeResult(
                type="Type 1",
                confidence="medium",  # Lower confidence without component analysis
                needs_processing=False,
                regions=[],
                detection_method="aspect_ratio",
            )
        elif aspect_ratio < 1.0 and height >= self.TYPE_5_HEIGHT_THRESHOLD:
            # Likely Type 5 (or legacy Type E)
            logger.debug(
                f"    Aspect ratio {aspect_ratio:.2f} < 1.0 and height {height} >= {self.TYPE_5_HEIGHT_THRESHOLD} "
                "→ Type 5 (combined vertical)"
            )
            return ImageTypeResult(
                type="Type 5",
                confidence="medium",
                needs_processing=False,
                regions=[],
                detection_method="aspect_ratio",
            )
        else:
            # Unknown - likely needs second image
            logger.debug(f"    Aspect ratio {aspect_ratio:.2f} → Unknown (needs analysis)")
            return ImageTypeResult(
                type="Unknown",
                confidence="low",
                needs_processing=True,
                regions=[],
                detection_method="aspect_ratio",
            )

    async def analyze_image(self, image_path: Path) -> ImageAnalysis:
        """
        Analyze image to determine type and processing needs.

        Uses connected component analysis (preferred) with aspect ratio fallback.

        Args:
            image_path: Path to image file

        Returns:
            ImageAnalysis with detected properties and processing requirements
        """
        logger.info(f"Analyzing image: {image_path.name}")

        # Get basic dimensions and colorspace
        width, height, colorspace = await self._get_image_properties(image_path)
        aspect_ratio = width / height

        logger.debug(
            f"  Dimensions: {width}x{height}, Aspect: {aspect_ratio:.2f}, "
            f"Colorspace: {colorspace}"
        )

        # NEW: Use connected component analysis for type detection
        type_result = await self.detect_image_type(image_path)

        # Map type result to processing needs
        if type_result.type == "Type 1":
            # Pre-combined horizontal - ready to use
            needs_second_image = False
            estimated_type = "Type 1"
            needs_rotation = False
            needs_deskew = False
            skew_angle = None
        elif type_result.type == "Type 5":
            # Pre-combined vertical - needs splitting/recombining
            needs_second_image = False
            estimated_type = "Type 5"
            needs_rotation = False  # Will split and process separately
            needs_deskew = False
            skew_angle = None
        elif self.SINGLE_CARD_MIN <= aspect_ratio < self.COMBINED_THRESHOLD:
            # Type 2, 3, or 4: Single front card needing back card
            needs_second_image = True
            estimated_type = "Type 2/3/4"

            # Check if deskewing is needed
            skew_angle = await self._detect_skew_angle(image_path)
            needs_deskew = (
                abs(skew_angle) > self.SKEW_TOLERANCE if skew_angle else False
            )
            needs_rotation = False  # Front cards don't need rotation
        elif aspect_ratio < 1.0:
            # Vertical image - shouldn't be first image (likely a back card)
            needs_second_image = False
            estimated_type = "Unknown-Vertical"
            needs_rotation = True  # Might need rotation
            skew_angle = await self._detect_skew_angle(image_path)
            needs_deskew = (
                abs(skew_angle) > self.SKEW_TOLERANCE if skew_angle else False
            )
        else:
            # Edge case: aspect not matching any pattern
            needs_second_image = True
            estimated_type = type_result.type  # Use detected type
            skew_angle = await self._detect_skew_angle(image_path)
            needs_deskew = (
                abs(skew_angle) > self.SKEW_TOLERANCE if skew_angle else False
            )
            needs_rotation = False

        # Clear, simple summary message
        if estimated_type in ["Type 1", "Type 5"]:
            logger.info(f"✓ Image ready: {estimated_type} - No additional processing required")
        elif needs_second_image:
            logger.info(f"⚠ Image incomplete: {estimated_type} - Requires back card for combination")
        else:
            logger.info(
                f"⚠ Image needs processing: Type={estimated_type}, "
                f"Deskew={'Yes' if needs_deskew else 'No'}, Rotate={'Yes' if needs_rotation else 'No'}"
            )

        return ImageAnalysis(
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            colorspace=colorspace,
            needs_second_image=needs_second_image,
            needs_deskew=needs_deskew,
            needs_rotation=needs_rotation,
            estimated_type=estimated_type,
            skew_angle=skew_angle,
            type_result=type_result,  # Include detailed detection results
        )

    async def analyze_back_card(self, image_path: Path) -> ImageAnalysis:
        """
        Analyze back card image to determine processing needs.

        Args:
            image_path: Path to back card image file

        Returns:
            ImageAnalysis with processing requirements for back card
        """
        logger.info(f"Analyzing back card: {image_path.name}")

        width, height, colorspace = await self._get_image_properties(image_path)
        aspect_ratio = width / height

        logger.debug(
            f"  Back card dimensions: {width}x{height}, Aspect: {aspect_ratio:.2f}"
        )

        # Determine if rotation is needed
        if aspect_ratio < 1.0:
            # Already vertical (Type B)
            needs_rotation = False
            estimated_type = "B-back"
        elif 1.0 <= aspect_ratio < self.COMBINED_THRESHOLD:
            # Horizontal, needs 90° rotation (Type C, D)
            needs_rotation = True
            estimated_type = "C/D-back"
        else:
            # Unexpected aspect ratio
            logger.warning(
                f"  Unexpected back card aspect ratio: {aspect_ratio:.2f} "
                f"(expected < {self.COMBINED_THRESHOLD})"
            )
            needs_rotation = True
            estimated_type = "Unknown-back"

        # Check if deskewing is needed
        skew_angle = await self._detect_skew_angle(image_path)
        needs_deskew = abs(skew_angle) > self.SKEW_TOLERANCE if skew_angle else False

        logger.info(
            f"  Back card: Type={estimated_type}, Rotate={needs_rotation}, "
            f"Deskew={needs_deskew}"
        )

        return ImageAnalysis(
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            colorspace=colorspace,
            needs_second_image=False,
            needs_deskew=needs_deskew,
            needs_rotation=needs_rotation,
            estimated_type=estimated_type,
            skew_angle=skew_angle,
        )

    async def process_front_card(
        self, image_path: Path, output_path: Optional[Path] = None
    ) -> Path:
        """
        Process front card: deskew if needed, then content-aware crop, final trim.

        Process:
        1. Deskew if angle > tolerance (MUST be first - straightens tilted image)
        2. Detect and crop to content boundaries (on straightened image)
        3. Final trim to remove any remaining borders

        Args:
            image_path: Path to front card image
            output_path: Optional output path (default: temp file)

        Returns:
            Path to processed image
        """
        if output_path is None:
            output_path = image_path.parent / f"{image_path.stem}_processed.jpg"

        logger.info(f"Processing front card: {image_path.name}")

        # Analyze to determine processing needs
        analysis = await self.analyze_image(image_path)

        commands = ["magick", str(image_path)]

        # STEP 1: Deskew FIRST if needed (straighten before cropping!)
        if analysis.needs_deskew:
            logger.info(f"  Deskewing first (angle: {analysis.skew_angle:.2f}°)")
            commands.extend(["-deskew", f"{self.DESKEW_THRESHOLD}%"])
            # Trim borders added by deskew rotation
            commands.extend(["-fuzz", "25%", "-trim", "+repage"])

            # Save to temp file, then re-analyze for content crop
            temp_path = image_path.parent / f"{image_path.stem}_deskewed.jpg"
            commands.append(str(temp_path))
            await self._run_imagemagick(commands)

            # Now do content-aware crop on straightened image
            left, top, width, height = await self._detect_content_crop(temp_path)

            commands = [
                "magick",
                str(temp_path),
                "-crop",
                f"{width}x{height}+{left}+{top}",
                "+repage",
                str(output_path),
            ]
            await self._run_imagemagick(commands)

            # Cleanup temp file
            temp_path.unlink(missing_ok=True)
        else:
            # No deskew needed, just do content-aware crop
            left, top, width, height = await self._detect_content_crop(image_path)

            commands.extend([
                "-crop",
                f"{width}x{height}+{left}+{top}",
                "+repage",
                str(output_path),
            ])
            await self._run_imagemagick(commands)

        logger.info(f"  Front card processed: {output_path.name}")
        return output_path

    async def process_back_card(
        self, image_path: Path, output_path: Optional[Path] = None
    ) -> Path:
        """
        Process back card: rotate if needed, deskew if needed, then content-aware crop.

        Process:
        1. Rotate 90° clockwise if needed
        2. Deskew if angle > tolerance (MUST be before crop - straightens tilted image)
        3. Detect and crop to content boundaries (on straightened image)
        4. Final trim to remove any remaining borders

        Args:
            image_path: Path to back card image
            output_path: Optional output path (default: temp file)

        Returns:
            Path to processed image
        """
        if output_path is None:
            output_path = image_path.parent / f"{image_path.stem}_processed.jpg"

        logger.info(f"Processing back card: {image_path.name}")

        # Analyze back card
        analysis = await self.analyze_back_card(image_path)

        commands = ["magick", str(image_path)]

        # STEP 1: Rotate if needed
        if analysis.needs_rotation:
            logger.info("  Rotating 90° clockwise")
            commands.extend(["-rotate", "90"])

        # STEP 2: Deskew if needed (AFTER rotation, BEFORE crop!)
        needs_deskew_after_rotation = False
        if analysis.needs_rotation:
            # After rotation, check if deskew is needed
            # For Type C, back card needs deskew after rotation
            temp_rotated = image_path.parent / f"{image_path.stem}_rotated.jpg"
            commands.extend(["-fuzz", "25%", "-trim", "+repage"])
            commands.append(str(temp_rotated))
            await self._run_imagemagick(commands)

            # Check skew on rotated image
            skew_angle = await self._detect_skew_angle(temp_rotated)
            if skew_angle and abs(skew_angle) > self.SKEW_TOLERANCE:
                logger.info(f"  Deskewing after rotation (angle: {skew_angle:.2f}°)")
                commands = [
                    "magick",
                    str(temp_rotated),
                    "-deskew", f"{self.DESKEW_THRESHOLD}%",
                    "-fuzz", "25%", "-trim", "+repage",
                    str(temp_rotated),
                ]
                await self._run_imagemagick(commands)

            # Now do content-aware crop on rotated (and possibly deskewed) image
            left, top, width, height = await self._detect_content_crop(temp_rotated)

            commands = [
                "magick",
                str(temp_rotated),
                "-crop",
                f"{width}x{height}+{left}+{top}",
                "+repage",
                str(output_path),
            ]
            await self._run_imagemagick(commands)

            # Cleanup temp file
            temp_rotated.unlink(missing_ok=True)

        elif analysis.needs_deskew:
            # No rotation, but needs deskew
            logger.info(f"  Deskewing (angle: {analysis.skew_angle:.2f}°)")
            commands.extend(["-deskew", f"{self.DESKEW_THRESHOLD}%"])
            commands.extend(["-fuzz", "25%", "-trim", "+repage"])

            # Save to temp, then content-aware crop
            temp_path = image_path.parent / f"{image_path.stem}_deskewed.jpg"
            commands.append(str(temp_path))
            await self._run_imagemagick(commands)

            left, top, width, height = await self._detect_content_crop(temp_path)

            commands = [
                "magick",
                str(temp_path),
                "-crop",
                f"{width}x{height}+{left}+{top}",
                "+repage",
                str(output_path),
            ]
            await self._run_imagemagick(commands)

            temp_path.unlink(missing_ok=True)

        else:
            # No rotation, no deskew - just content-aware crop
            left, top, width, height = await self._detect_content_crop(image_path)

            commands.extend([
                "-crop",
                f"{width}x{height}+{left}+{top}",
                "+repage",
                str(output_path),
            ])
            await self._run_imagemagick(commands)

        logger.info(f"  Back card processed: {output_path.name}")
        return output_path

    async def combine_cards(
        self, front_path: Path, back_path: Path, output_path: Path
    ) -> Path:
        """
        Combine front and back cards horizontally with proper vertical centering.

        Process:
        1. Get dimensions of both images
        2. Determine max height for vertical centering
        3. Extend front image to max height (centered) with black background
        4. Append back image horizontally
        5. Trim outer black borders from combined result

        Args:
            front_path: Path to processed front card
            back_path: Path to processed back card
            output_path: Path for combined output image

        Returns:
            Path to combined image
        """
        logger.info(f"Combining cards: {front_path.name} + {back_path.name}")

        # Get dimensions of both images
        width1, height1, _ = await self._get_image_properties(front_path)
        width2, height2, _ = await self._get_image_properties(back_path)

        logger.debug(f"  Front: {width1}x{height1}")
        logger.debug(f"  Back: {width2}x{height2}")

        # Determine max height for vertical centering
        max_height = max(height1, height2)

        # Combine: extend front image to max height (centered with black background),
        # then append back image, then trim outer borders
        commands = [
            "magick",
            str(front_path),
            "-gravity",
            "center",
            "-background",
            "black",
            "-extent",
            f"{width1}x{max_height}",
            str(back_path),
            "+append",  # Horizontal append
            "-fuzz",
            "25%",  # Use 25% fuzz for aggressive outer border trimming
            "-trim",
            "+repage",
            str(output_path),
        ]

        await self._run_imagemagick(commands)

        # Log final dimensions
        width, height, _ = await self._get_image_properties(output_path)
        aspect = width / height
        logger.info(
            f"  Combined: {output_path.name} ({width}x{height}, aspect={aspect:.2f})"
        )

        return output_path

    async def combine_raw_images(
        self, image1_path: Path, image2_path: Path, output_path: Path, temp_dir: Optional[Path] = None
    ) -> Path:
        """
        Combine two raw images horizontally with pre-trimming and vertical centering.

        This method is designed for raw downloaded images that need trimming before combining.
        Process:
        1. Trim black borders from both images (25% fuzz for aggressive trimming)
        2. Get dimensions of trimmed images
        3. Determine max height for vertical centering
        4. Extend first image to max height (centered) with black background
        5. Append second image horizontally
        6. Trim outer black borders from combined result

        Args:
            image1_path: Path to first image (left side)
            image2_path: Path to second image (right side)
            output_path: Path for combined output image
            temp_dir: Optional directory for temporary files (default: same as image1_path)

        Returns:
            Path to combined image
        """
        logger.info(f"Combining raw images: {image1_path.name} + {image2_path.name}")

        # Use provided temp_dir or default to image1's parent directory
        temp_location = temp_dir or image1_path.parent
        trimmed1_path = temp_location / "1_trimmed.jpg"
        trimmed2_path = temp_location / "2_trimmed.jpg"

        try:
            # Step 1: Trim black borders from both images (25% fuzz for aggressive trimming)
            logger.debug("  Trimming black borders from both images...")
            await self._run_imagemagick([
                "magick",
                str(image1_path),
                "-fuzz", "25%",
                "-trim",
                "+repage",
                str(trimmed1_path),
            ])

            await self._run_imagemagick([
                "magick",
                str(image2_path),
                "-fuzz", "25%",
                "-trim",
                "+repage",
                str(trimmed2_path),
            ])

            # Step 2: Get dimensions of trimmed images
            width1, height1, _ = await self._get_image_properties(trimmed1_path)
            width2, height2, _ = await self._get_image_properties(trimmed2_path)

            logger.debug(f"  Trimmed Image 1: {width1}×{height1}")
            logger.debug(f"  Trimmed Image 2: {width2}×{height2}")

            # Step 3: Determine max height for vertical centering
            max_height = max(height1, height2)

            # Step 4-6: Combine with vertical centering and trim outer borders
            await self._run_imagemagick([
                "magick",
                str(trimmed1_path),
                "-gravity", "center",
                "-background", "black",
                "-extent", f"{width1}x{max_height}",
                str(trimmed2_path),
                "+append",  # Horizontal append
                "-fuzz", "25%",
                "-trim",
                "+repage",
                str(output_path),
            ])

            # Log final dimensions
            width, height, _ = await self._get_image_properties(output_path)
            logger.info(f"  Combined: {output_path.name} ({width}×{height})")

            return output_path

        finally:
            # Clean up temporary trimmed files
            trimmed1_path.unlink(missing_ok=True)
            trimmed2_path.unlink(missing_ok=True)

    async def process_combined_card(
        self, image_path: Path, output_path: Path
    ) -> Path:
        """
        Process already-combined card (Type A): content-aware cropping.

        Args:
            image_path: Path to combined card image
            output_path: Path for output image

        Returns:
            Path to processed image
        """
        logger.info(f"Processing combined card (Type A): {image_path.name}")

        # Use content-aware crop to remove white background and dark borders
        left, top, width, height = await self._detect_content_crop(image_path)

        commands = [
            "magick",
            str(image_path),
            "-crop",
            f"{width}x{height}+{left}+{top}",
            "+repage",
            str(output_path),
        ]

        await self._run_imagemagick(commands)
        logger.info(f"  Processed: {output_path.name}")

        return output_path

    async def process_stacked_card(
        self, image_path: Path, output_path: Path
    ) -> Path:
        """
        Process vertically stacked card (Type E): split, rotate back, combine.

        Type E has front card on top and back card on bottom in a single image.
        Need to split them, rotate the back card 90° CW, then combine horizontally.

        Args:
            image_path: Path to stacked card image
            output_path: Path for combined output image

        Returns:
            Path to processed combined image
        """
        logger.info(f"Processing stacked card (Type E): {image_path.name}")

        # Split into top (front) and bottom (back) halves
        temp_dir = image_path.parent
        front_temp = temp_dir / f"{image_path.stem}_front_temp.jpg"
        back_temp = temp_dir / f"{image_path.stem}_back_temp.jpg"

        front_path, back_path = await self._split_stacked_image(
            image_path, front_temp, back_temp
        )

        logger.info("  Split into front (top) and back (bottom) cards")

        # Process front card (top half)
        front_processed = await self.process_front_card(
            front_path, temp_dir / f"{image_path.stem}_front_processed.jpg"
        )

        # Process back card (bottom half) - will rotate 90° CW
        back_processed = await self.process_back_card(
            back_path, temp_dir / f"{image_path.stem}_back_processed.jpg"
        )

        # Combine horizontally
        combined = await self.combine_cards(
            front_processed, back_processed, output_path
        )

        # Cleanup temp files
        front_temp.unlink(missing_ok=True)
        back_temp.unlink(missing_ok=True)
        front_processed.unlink(missing_ok=True)
        back_processed.unlink(missing_ok=True)

        logger.info(f"  Stacked card processed: {output_path.name}")

        return combined

    async def _split_stacked_image(
        self, image_path: Path, front_output: Path, back_output: Path
    ) -> tuple[Path, Path]:
        """
        Split vertically stacked image into top (front) and bottom (back) halves.

        Uses statistical analysis to find the separator between cards, or falls
        back to simple 50/50 split if no clear separator is found.

        Args:
            image_path: Path to stacked image
            front_output: Path for top half (front card)
            back_output: Path for bottom half (back card)

        Returns:
            Tuple of (front_path, back_path)
        """
        # Get image dimensions
        width, height, _ = await self._get_image_properties(image_path)

        # Find split point (separator between cards)
        split_y = await self._find_vertical_split(image_path, width, height)

        logger.debug(f"  Splitting at y={split_y} (height={height})")

        # Extract top half (front card)
        front_height = split_y
        commands = [
            "magick",
            str(image_path),
            "-crop",
            f"{width}x{front_height}+0+0",
            "+repage",
            str(front_output),
        ]
        await self._run_imagemagick(commands)

        # Extract bottom half (back card)
        back_height = height - split_y
        commands = [
            "magick",
            str(image_path),
            "-crop",
            f"{width}x{back_height}+0+{split_y}",
            "+repage",
            str(back_output),
        ]
        await self._run_imagemagick(commands)

        logger.debug(
            f"  Front: {width}x{front_height}, Back: {width}x{back_height}"
        )

        return front_output, back_output

    async def _find_vertical_split(
        self, image_path: Path, width: int, height: int
    ) -> int:
        """
        Find the split point between vertically stacked cards.

        Scans the middle region of the image (40-60% of height) looking for
        a dark separator line between cards. Falls back to 50/50 split if no
        clear separator is found.

        Args:
            image_path: Path to image
            width: Image width
            height: Image height

        Returns:
            Y coordinate of split point
        """
        # Scan middle region (40-60% of height) for dark separator
        start_y = int(height * 0.4)
        end_y = int(height * 0.6)

        darkest_y = height // 2  # Default to middle
        darkest_mean = 255

        for y in range(start_y, end_y, 2):  # Sample every 2 pixels
            mean = await self._get_row_mean(image_path, y, width // 2, 200)

            # Look for dark separator (mean < 50)
            if mean < darkest_mean and mean < 50:
                darkest_y = y
                darkest_mean = mean

        if darkest_mean < 50:
            logger.debug(
                f"  Found dark separator at y={darkest_y} (mean={darkest_mean:.1f})"
            )
            return darkest_y
        else:
            # No clear separator, use 50/50 split
            logger.debug("  No separator found, using 50/50 split")
            return height // 2

    async def cleanup_originals(self, *image_paths: Path) -> None:
        """
        Delete original images if keep_originals=False.

        Args:
            *image_paths: Paths to images to potentially delete
        """
        if self.keep_originals:
            logger.debug("Keeping original images (keep_originals=True)")
            return

        for path in image_paths:
            if path and path.exists():
                logger.debug(f"Deleting original: {path.name}")
                path.unlink()

    # Private helper methods

    async def _detect_content_crop(
        self, image_path: Path
    ) -> tuple[int, int, int, int]:
        """
        Detect content boundaries by sampling and finding transitions from border to content.

        Uses statistical analysis to find where the actual card content starts/ends,
        removing both white background and dark card borders.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (left_x, top_y, width, height) for crop geometry
        """
        # Get image dimensions
        width, height, _ = await self._get_image_properties(image_path)

        # Find boundaries
        top = await self._find_top_content(image_path, width, height)
        left = await self._find_left_content(image_path, width, height)
        right = await self._find_right_content(image_path, width, height)
        bottom = await self._find_bottom_content(image_path, width, height)

        crop_width = right - left + 1
        crop_height = bottom - top + 1

        logger.debug(
            f"  Content boundaries: {crop_width}x{crop_height}+{left}+{top}"
        )

        return (left, top, crop_width, crop_height)

    async def _find_top_content(
        self, image_path: Path, width: int, height: int
    ) -> int:
        """Find top content boundary (skip white background and dark border)."""
        # First, check if image starts with content (no background to remove)
        first_mean = await self._get_row_mean(image_path, 0, width // 2)
        if 80 < first_mean < 230:
            # Image starts with content, no cropping needed
            logger.debug(f"  Top: starts with content (mean={first_mean:.1f}), no crop")
            return 0

        # Image has background/border, use state machine
        in_dark_border = False
        for y in range(height):
            mean = await self._get_row_mean(image_path, y, width // 2)

            # State machine: white -> dark border -> content
            if mean < 50:
                in_dark_border = True
            elif in_dark_border and 100 < mean < 220:
                logger.debug(f"  Top: found content at y={y} after dark border")
                return y

        return 0

    async def _find_left_content(
        self, image_path: Path, width: int, height: int
    ) -> int:
        """Find left content boundary (skip dark border)."""
        # First, check if image starts with content (no border to remove)
        first_mean = await self._get_column_mean(image_path, 0, height // 2)
        if 80 < first_mean < 230:
            # Image starts with content, no cropping needed
            logger.debug(f"  Left: starts with content (mean={first_mean:.1f}), no crop")
            return 0

        # Image has border, find content boundary
        for x in range(width):
            mean = await self._get_column_mean(image_path, x, height // 2)
            if mean > 150:  # Found lighter content area
                logger.debug(f"  Left: found content at x={x}")
                return x
        return 0

    async def _find_right_content(
        self, image_path: Path, width: int, height: int
    ) -> int:
        """Find right content boundary (skip dark border)."""
        # First, check if image ends with content (no border to remove)
        last_mean = await self._get_column_mean(image_path, width - 1, height // 2)
        if 80 < last_mean < 230:
            # Image ends with content, no cropping needed
            logger.debug(f"  Right: ends with content (mean={last_mean:.1f}), no crop")
            return width - 1

        # Image has border, find content boundary
        for x in range(width - 1, -1, -1):
            mean = await self._get_column_mean(image_path, x, height // 2)
            if mean > 150:  # Found lighter content area
                logger.debug(f"  Right: found content at x={x}")
                return x
        return width - 1

    async def _find_bottom_content(
        self, image_path: Path, width: int, height: int
    ) -> int:
        """Find bottom content boundary (skip dark border)."""
        # First, check if image ends with content (no border to remove)
        last_mean = await self._get_row_mean(image_path, height - 1, width // 2)
        if 80 < last_mean < 230:
            # Image ends with content, no cropping needed
            logger.debug(f"  Bottom: ends with content (mean={last_mean:.1f}), no crop")
            return height - 1

        # Image has border, use state machine
        in_dark_border = False
        for y in range(height - 1, -1, -1):
            mean = await self._get_row_mean(image_path, y, width // 2)

            if mean < 50:
                in_dark_border = True
            elif in_dark_border and 100 < mean < 220:
                logger.debug(f"  Bottom: found content at y={y} before dark border")
                return y

        return height - 1

    async def _get_row_mean(
        self, image_path: Path, y: int, x_center: int, sample_width: int = 100
    ) -> float:
        """Get mean pixel intensity of a horizontal strip."""
        x_start = max(0, x_center - sample_width // 2)
        cmd = [
            "magick",
            str(image_path),
            "-crop",
            f"{sample_width}x1+{x_start}+{y}",
            "-scale",
            "1x1!",
            "-format",
            "%[fx:mean*255]",
            "info:",
        ]
        result = await self._run_command(cmd)
        return float(result.strip())

    async def _get_column_mean(
        self, image_path: Path, x: int, y_center: int, sample_height: int = 100
    ) -> float:
        """Get mean pixel intensity of a vertical strip."""
        y_start = max(0, y_center - sample_height // 2)
        cmd = [
            "magick",
            str(image_path),
            "-crop",
            f"1x{sample_height}+{x}+{y_start}",
            "-scale",
            "1x1!",
            "-format",
            "%[fx:mean*255]",
            "info:",
        ]
        result = await self._run_command(cmd)
        return float(result.strip())

    async def _get_image_properties(self, image_path: Path) -> tuple[int, int, str]:
        """
        Get image width, height, and colorspace.

        Args:
            image_path: Path to image

        Returns:
            Tuple of (width, height, colorspace)
        """
        cmd = [
            "identify",
            "-format",
            "%w %h %[colorspace]",
            str(image_path),
        ]

        result = await self._run_command(cmd)
        parts = result.strip().split()

        if len(parts) != 3:
            raise ValueError(f"Unexpected identify output: {result}")

        width = int(parts[0])
        height = int(parts[1])
        colorspace = parts[2]

        return width, height, colorspace

    async def _detect_skew_angle(self, image_path: Path) -> Optional[float]:
        """
        Detect skew angle using ImageMagick.

        Args:
            image_path: Path to image

        Returns:
            Detected skew angle in degrees, or None if detection fails
        """
        try:
            # Use -deskew with verbose output to detect angle
            # We'll do a dry run to a null file to get the angle
            cmd = [
                "magick",
                str(image_path),
                "-deskew",
                f"{self.DESKEW_THRESHOLD}%",
                "-format",
                "%[deskew:angle]",
                "info:",
            ]

            result = await self._run_command(cmd)
            angle_str = result.strip()

            if angle_str and angle_str != "":
                angle = float(angle_str)
                logger.debug(f"  Detected skew angle: {angle:.2f}°")
                return angle
            else:
                logger.debug("  No skew angle detected")
                return 0.0

        except Exception as e:
            logger.warning(f"Failed to detect skew angle: {e}")
            return None

    async def _run_imagemagick(self, commands: List[str]) -> str:
        """
        Run ImageMagick command.

        Args:
            commands: Command and arguments

        Returns:
            Command output
        """
        return await self._run_command(commands)

    async def _run_command(self, commands: List[str]) -> str:
        """
        Run shell command asynchronously.

        Args:
            commands: Command and arguments

        Returns:
            Command stdout

        Raises:
            RuntimeError: If command fails
        """
        logger.debug(f"Running: {' '.join(commands)}")

        process = await asyncio.create_subprocess_exec(
            *commands, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Command failed: {' '.join(commands)}\n{error_msg}")

        return stdout.decode()


async def main():
    """Test the image processor with sample images."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python draft_image_processor.py <image_path> [<back_image_path>]")
        sys.exit(1)

    processor = DraftImageProcessor(keep_originals=True)

    front_path = Path(sys.argv[1])
    back_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    # Analyze first image
    analysis = await processor.analyze_image(front_path)
    print(f"\nAnalysis: {analysis}")

    if back_path:
        # Process both and combine
        front_processed = await processor.process_front_card(
            front_path, Path("/tmp/front_processed.jpg")
        )
        back_processed = await processor.process_back_card(
            back_path, Path("/tmp/back_processed.jpg")
        )
        combined = await processor.combine_cards(
            front_processed, back_processed, Path("/tmp/combined.jpg")
        )
        print(f"\nCombined image: {combined}")
    elif analysis.needs_second_image:
        print("\nSecond image needed but not provided")
    else:
        # Process as combined card
        output = await processor.process_combined_card(
            front_path, Path("/tmp/processed.jpg")
        )
        print(f"\nProcessed image: {output}")


if __name__ == "__main__":
    asyncio.run(main())
