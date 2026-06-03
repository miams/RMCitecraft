#!/usr/bin/env python3
"""
Test script for draft registration image processing.

Tests the complete workflow:
1. Read RINs from ww2_draft_updated.xlsx
2. Select random RINs for test images
3. Process image pairs (b1/b2, c1/c2, d1/d2)
4. Generate proper filenames from RINs
5. Save to final storage location
6. Display before/after statistics
"""

import asyncio
import csv
import random
import sys
from pathlib import Path
from typing import List, Tuple

from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from rmcitecraft.config.settings import get_config
from rmcitecraft.services.draft_file_naming import get_filename_from_rin, get_unique_filename
from rmcitecraft.services.draft_image_processor import DraftImageProcessor


class ImageProcessingTester:
    """Test image processing with sample images and random RINs."""

    def __init__(self):
        """Initialize tester with config and paths."""
        self.config = get_config()
        self.processor = DraftImageProcessor()

        # Source images
        self.downloads_dir = Path("/Users/miams/Downloads")
        self.image_pairs = [
            ("image b1.jpg", "image b2.jpg", "Type B - Color separate cards"),
            ("image c1.jpg", "image c2.jpg", "Type C - B&W tilted cards"),
            ("image d1.jpg", "image d2.jpg", "Type D - B&W aligned cards"),
        ]

        # Single images (Type A and Type E)
        self.single_images = [
            ("image e.jpg", "Type E - Vertically stacked"),
        ]

        # Storage
        self.storage_dir = Path(self.config.draft_image_storage_dir)
        self.temp_dir = Path(self.config.draft_download_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Database
        self.rmtree_path = self.config.rm_database_path

        # Spreadsheet
        self.spreadsheet_path = project_root / "ww2_draft_updated.xlsx"

    def load_rins_from_spreadsheet(self) -> List[int]:
        """
        Load RINs from spreadsheet.

        Returns:
            List of RINs that have valid values
        """
        # Use CSV file
        csv_path = project_root / "ww2_draft_updated.csv"
        logger.info(f"Loading RINs from: {csv_path}")

        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return []

        rins = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # Find RIN column
            rin_column = None
            for col in reader.fieldnames:
                if col.lower() in ['rin', 'personid', 'person_id']:
                    rin_column = col
                    break

            if not rin_column:
                logger.error(f"RIN column not found. Available columns: {reader.fieldnames}")
                return []

            logger.info(f"Using RIN column: {rin_column}")

            # Read RINs
            for row in reader:
                rin_value = row.get(rin_column, '').strip()
                if rin_value and rin_value.isdigit():
                    rins.append(int(rin_value))

        logger.info(f"Found {len(rins)} valid RINs in spreadsheet")
        return rins

    def select_random_rins(self, rins: List[int], count: int = 3) -> List[int]:
        """
        Select random RINs from list.

        Args:
            rins: List of available RINs
            count: Number of RINs to select

        Returns:
            List of randomly selected RINs
        """
        if len(rins) < count:
            logger.warning(f"Not enough RINs ({len(rins)}), using all available")
            return rins[:count]

        selected = random.sample(rins, count)
        logger.info(f"Selected RINs: {selected}")
        return selected

    async def test_single_image(
        self, image_path: Path, rin: int, description: str
    ) -> Tuple[bool, Path]:
        """
        Test processing a single stacked or combined image (Type A or Type E).

        Args:
            image_path: Path to single image
            rin: RIN for filename generation
            description: Description of image type

        Returns:
            Tuple of (success, final_image_path)
        """
        logger.info("=" * 80)
        logger.info(f"Testing: {description}")
        logger.info(f"  Image: {image_path.name}")
        logger.info(f"  RIN:   {rin}")
        logger.info("=" * 80)

        try:
            # Step 1: Analyze image
            logger.info("\n1️⃣  Analyzing image...")
            analysis = await self.processor.analyze_image(image_path)

            logger.info(f"  Image: {analysis.width}x{analysis.height}, "
                       f"aspect={analysis.aspect_ratio:.2f}, "
                       f"type={analysis.estimated_type}")

            # Step 2: Process based on type
            logger.info("\n2️⃣  Processing image...")

            if analysis.estimated_type == "E":
                # Type E: Vertically stacked, needs splitting
                logger.info("  Type E detected: splitting and combining")
                combined_temp = self.temp_dir / "combined_temp.jpg"
                combined = await self.processor.process_stacked_card(
                    image_path, combined_temp
                )
            elif analysis.estimated_type == "A":
                # Type A: Already combined, just crop
                logger.info("  Type A detected: cropping only")
                combined_temp = self.temp_dir / "combined_temp.jpg"
                combined = await self.processor.process_combined_card(
                    image_path, combined_temp
                )
            else:
                raise ValueError(f"Unexpected type for single image: {analysis.estimated_type}")

            # Get final dimensions
            import subprocess
            result = subprocess.run(
                ["identify", "-format", "%wx%h", str(combined)],
                capture_output=True,
                text=True,
                check=True
            )
            final_dims = result.stdout.strip()
            logger.info(f"  Processed: {final_dims}")

            # Step 3: Generate filename from RIN
            logger.info("\n3️⃣  Generating filename from RIN...")
            filename = get_filename_from_rin(rin, self.rmtree_path)
            filename = get_unique_filename(filename, self.storage_dir)
            logger.info(f"  Filename: {filename}")

            # Step 4: Move to final location
            logger.info("\n4️⃣  Saving to final location...")
            final_path = self.storage_dir / filename
            import shutil
            shutil.move(str(combined), str(final_path))
            logger.info(f"  ✅ Saved: {final_path}")

            logger.info(f"\n✅ SUCCESS: {description}")
            logger.info(f"   Final image: {final_path}")
            logger.info(f"   Dimensions: {final_dims}\n")

            return True, final_path

        except Exception as e:
            logger.error(f"\n❌ FAILED: {description}")
            logger.error(f"   Error: {e}", exc_info=True)
            return False, None

    async def test_image_pair(
        self, front_path: Path, back_path: Path, rin: int, description: str
    ) -> Tuple[bool, Path]:
        """
        Test processing a single image pair.

        Args:
            front_path: Path to front card image
            back_path: Path to back card image
            rin: RIN for filename generation
            description: Description of image type

        Returns:
            Tuple of (success, final_image_path)
        """
        logger.info("=" * 80)
        logger.info(f"Testing: {description}")
        logger.info(f"  Front: {front_path.name}")
        logger.info(f"  Back:  {back_path.name}")
        logger.info(f"  RIN:   {rin}")
        logger.info("=" * 80)

        try:
            # Step 1: Analyze images
            logger.info("\n1️⃣  Analyzing images...")
            front_analysis = await self.processor.analyze_image(front_path)
            back_analysis = await self.processor.analyze_back_card(back_path)

            logger.info(f"  Front: {front_analysis.width}x{front_analysis.height}, "
                       f"aspect={front_analysis.aspect_ratio:.2f}, "
                       f"deskew={front_analysis.needs_deskew}, "
                       f"type={front_analysis.estimated_type}")
            logger.info(f"  Back:  {back_analysis.width}x{back_analysis.height}, "
                       f"aspect={back_analysis.aspect_ratio:.2f}, "
                       f"rotate={back_analysis.needs_rotation}, "
                       f"deskew={back_analysis.needs_deskew}")

            # Step 2: Process front card
            logger.info("\n2️⃣  Processing front card...")
            front_processed = await self.processor.process_front_card(
                front_path, self.temp_dir / "front_processed.jpg"
            )
            logger.info(f"  Processed: {front_processed}")

            # Step 3: Process back card
            logger.info("\n3️⃣  Processing back card...")
            back_processed = await self.processor.process_back_card(
                back_path, self.temp_dir / "back_processed.jpg"
            )
            logger.info(f"  Processed: {back_processed}")

            # Step 4: Combine cards
            logger.info("\n4️⃣  Combining cards...")
            combined_temp = self.temp_dir / "combined_temp.jpg"
            combined = await self.processor.combine_cards(
                front_processed, back_processed, combined_temp
            )

            # Get final dimensions
            import subprocess
            result = subprocess.run(
                ["identify", "-format", "%wx%h", str(combined)],
                capture_output=True,
                text=True,
                check=True
            )
            final_dims = result.stdout.strip()
            logger.info(f"  Combined: {final_dims}")

            # Step 5: Generate filename from RIN
            logger.info("\n5️⃣  Generating filename from RIN...")
            filename = get_filename_from_rin(rin, self.rmtree_path)
            filename = get_unique_filename(filename, self.storage_dir)
            logger.info(f"  Filename: {filename}")

            # Step 6: Move to final location
            logger.info("\n6️⃣  Saving to final location...")
            final_path = self.storage_dir / filename
            import shutil
            shutil.move(str(combined), str(final_path))
            logger.info(f"  ✅ Saved: {final_path}")

            # Step 7: Cleanup intermediate files
            logger.info("\n7️⃣  Cleaning up...")
            front_processed.unlink(missing_ok=True)
            back_processed.unlink(missing_ok=True)
            logger.info("  ✅ Cleanup complete")

            logger.info(f"\n✅ SUCCESS: {description}")
            logger.info(f"   Final image: {final_path}")
            logger.info(f"   Dimensions: {final_dims}\n")

            return True, final_path

        except Exception as e:
            logger.error(f"\n❌ FAILED: {description}")
            logger.error(f"   Error: {e}", exc_info=True)
            return False, None

    async def run_tests(self):
        """Run all image processing tests."""
        logger.info("🚀 Starting Draft Registration Image Processing Tests\n")

        # Load RINs
        logger.info("=" * 80)
        logger.info("Loading RINs from spreadsheet")
        logger.info("=" * 80)
        rins = self.load_rins_from_spreadsheet()

        if not rins:
            logger.error("No valid RINs found in spreadsheet")
            return

        # Select random RINs (need more for both pairs and single images)
        total_tests = len(self.image_pairs) + len(self.single_images)
        selected_rins = self.select_random_rins(rins, total_tests)

        # Test each image pair
        results = []
        rin_index = 0

        for i, (front_name, back_name, description) in enumerate(self.image_pairs):
            front_path = self.downloads_dir / front_name
            back_path = self.downloads_dir / back_name
            rin = selected_rins[rin_index] if rin_index < len(selected_rins) else selected_rins[0]
            rin_index += 1

            # Check files exist
            if not front_path.exists():
                logger.error(f"Front image not found: {front_path}")
                continue
            if not back_path.exists():
                logger.error(f"Back image not found: {back_path}")
                continue

            # Process pair
            success, final_path = await self.test_image_pair(
                front_path, back_path, rin, description
            )
            results.append((description, success, final_path))

        # Test each single image
        for i, (image_name, description) in enumerate(self.single_images):
            image_path = self.downloads_dir / image_name
            rin = selected_rins[rin_index] if rin_index < len(selected_rins) else selected_rins[0]
            rin_index += 1

            # Check file exists
            if not image_path.exists():
                logger.error(f"Image not found: {image_path}")
                continue

            # Process single image
            success, final_path = await self.test_single_image(
                image_path, rin, description
            )
            results.append((description, success, final_path))

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 80)

        successful = sum(1 for _, success, _ in results if success)
        total = len(results)

        logger.info(f"Total tests: {total}")
        logger.info(f"Successful:  {successful}")
        logger.info(f"Failed:      {total - successful}")

        logger.info("\nResults:")
        for description, success, final_path in results:
            status = "✅" if success else "❌"
            logger.info(f"  {status} {description}")
            if final_path:
                logger.info(f"      → {final_path}")

        logger.info("\n" + "=" * 80)
        logger.info(f"Storage directory: {self.storage_dir}")
        logger.info("=" * 80)

        if successful == total:
            logger.info("\n🎉 All tests passed!")
        else:
            logger.warning(f"\n⚠️  {total - successful} test(s) failed")


async def main():
    """Main entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # Run tests
    tester = ImageProcessingTester()
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())
