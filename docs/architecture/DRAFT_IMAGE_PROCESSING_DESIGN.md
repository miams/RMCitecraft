---
priority: high
topics: [draft-registration, image-processing, imagemagick, automation]
status: active
created: 2026-02-08
---

# Draft Registration Card Image Processing Design

## Overview

Automated analysis and processing of WW2 draft registration card images to create standardized combined images (front + back cards) with consistent formatting and quality.

## Image Types & Processing Requirements

### Type A: Already Combined (Target Format)
**Source**: FamilySearch
**Characteristics**:
- Dimensions: ~2,972 x 1,795 pixels
- Aspect ratio: ~1.66:1
- Color: sRGB
- Layout: Front card (horizontal) on left, back card (vertical) on right
- Both cards centered vertically

**Processing**: None needed - already in target format

### Type B: Separate Color Images
**Source**: Ancestry
**Characteristics**:
- Front (b1): 1,790 x 1,179 (aspect 1.52), horizontal, color
- Back (b2): 1,179 x 1,790 (aspect 0.66), vertical, color
- Both properly aligned, no tilt correction needed

**Processing**:
1. Download both images
2. Horizontal append (+append): front | back
3. Trim borders (-fuzz 10% -trim)
4. Result: ~2,969 x 1,790 (aspect 1.66)

### Type C: B&W with Tilt (Needs Correction)
**Source**: FamilySearch
**Characteristics**:
- Front (c1): 1,288 x 936 (aspect 1.38), horizontal, tilted, grayscale
- Back (c2): 1,288 x 984 (aspect 1.31), horizontal (needs 90° rotation), tilted, grayscale

**Processing**:
1. Download both images
2. Front: Deskew (-deskew 40%), trim
3. Back: Rotate 90° CW (-rotate 90), deskew, trim
4. Horizontal append
5. Result: ~2,349 x 1,318 (aspect 1.78)

### Type D: B&W Properly Aligned
**Source**: FamilySearch
**Characteristics**:
- Front (d1): 1,448 x 1,032 (aspect 1.40), horizontal, grayscale
- Back (d2): 1,448 x 1,032 (aspect 1.40), horizontal (needs 90° rotation), grayscale
- No tilt correction needed

**Processing**:
1. Download both images
2. Front: Trim only
3. Back: Rotate 90° CW, trim
4. Horizontal append
5. Result: ~2,479 x 1,448 (aspect 1.71)

### Type E: Vertically Stacked (Needs Splitting & Rotation)
**Source**: FamilySearch/Ancestry
**Characteristics**:
- Single image: 1,304 x 1,832 (aspect ~0.71), vertical, grayscale
- Layout: Front card on top, back card on bottom (vertically stacked)
- Back card needs 90° rotation to match orientation
- May have separator border between cards

**Processing**:
1. Download single image
2. Split into top half (front) and bottom half (back)
3. Front: Content-aware crop
4. Back: Rotate 90° CW, content-aware crop
5. Horizontal append (front on left, back on right)
6. Result: Target aspect ~1.66

**Detection**: Vertical aspect ratio (< 1.0), but tall enough to contain two cards (~1,800+ pixels height)

## Detection Logic

### Phase 1: Initial Image Analysis
After downloading the first image, analyze to determine processing path:

```python
aspect_ratio = width / height

if aspect_ratio >= 1.60:
    # Type A: Already combined (horizontal)
    action = "use_as_is"
    download_second = False

elif 1.30 <= aspect_ratio < 1.60:
    # Type B, C, or D front card
    action = "needs_combining"
    download_second = True

elif aspect_ratio < 1.0 and height >= 1800:
    # Type E: Vertically stacked (front on top, back on bottom)
    action = "split_and_combine"
    download_second = False

elif aspect_ratio < 1.0:
    # Back card (vertical) - shouldn't happen as first image
    action = "error_unexpected_back_card"
    download_second = False

else:
    # Edge case: 1.0 <= aspect < 1.3 (square-ish)
    action = "manual_review"
    download_second = True  # Try anyway
```

### Phase 2: Front Card Processing Detection
For single front cards (aspect 1.30-1.60), determine if deskewing is needed:

```python
# Use ImageMagick to detect skew angle
# -deskew 40% will return angle detected
needs_deskew = detect_skew_angle(image) > 1.0  # degrees

if needs_deskew:
    processing = ["deskew", "trim"]
else:
    processing = ["trim"]
```

### Phase 3: Back Card Analysis (After Second Download)
Analyze the second image to determine orientation and processing:

```python
back_aspect = width / height

if back_aspect < 1.0:
    # Already vertical (Type B)
    rotation_needed = False

elif 1.0 <= back_aspect < 1.60:
    # Horizontal, needs 90° rotation (Type C, D)
    rotation_needed = True

else:
    # Unexpected aspect ratio
    rotation_needed = True  # Try anyway

needs_deskew = detect_skew_angle(back_image) > 1.0

if rotation_needed and needs_deskew:
    processing = ["rotate_90_cw", "deskew", "trim"]
elif rotation_needed:
    processing = ["rotate_90_cw", "trim"]
elif needs_deskew:
    processing = ["deskew", "trim"]
else:
    processing = ["trim"]
```

### Phase 4: Combination
Combine processed front and back images:

```python
# Horizontal append: front (left) | back (right)
magick front.jpg back.jpg +append -fuzz 10% -trim +repage combined.jpg
```

## ImageMagick Command Reference

### Deskew
```bash
magick input.jpg -deskew 40% output.jpg
```
- `40%` is the threshold for automatic skew detection
- Corrects images tilted up to ~40 degrees
- Works best with clear edges (card against dark background)

### Rotate
```bash
magick input.jpg -rotate 90 output.jpg
```
- Positive values: clockwise rotation
- Negative values: counter-clockwise rotation

### Trim
```bash
magick input.jpg -fuzz 10% -trim +repage output.jpg
```
- `-fuzz 10%`: Allow 10% color variance when detecting borders
- `-trim`: Remove uniform-color borders
- `+repage`: Reset page geometry to actual image size

### Horizontal Append
```bash
magick front.jpg back.jpg +append output.jpg
```
- `+append`: Horizontal combination (left to right)
- `-append`: Vertical combination (top to bottom)

### Analysis
```bash
# Get dimensions and aspect ratio
identify -format "%wx%h, aspect=%[fx:w/h]\n" input.jpg

# Detect colorspace
identify -format "%[colorspace]\n" input.jpg

# Get detailed info
identify -verbose input.jpg
```

## File Naming

### Final Image Name Format
```
surname, givenname (birth-death).jpg
```

**Example**: `Iams, Alexander Murdoch (1917-1984).jpg`

### Lookup Logic
```python
def get_filename_from_rin(rin: int, rmtree_path: str) -> str:
    """
    Query RootsMagic database to get person details for file naming.

    Args:
        rin: RootsMagic person ID
        rmtree_path: Path to .rmtree database

    Returns:
        Formatted filename: "surname, givenname (birth-death).jpg"
    """
    # Query PersonTable and NameTable for primary name
    # Query birth/death events for years
    # Format: "surname, givenname (birth-death).jpg"

    # If birth/death missing, use:
    # - "surname, givenname (birth-).jpg" if only death missing
    # - "surname, givenname (-death).jpg" if only birth missing
    # - "surname, givenname.jpg" if both missing
```

### Storage Location
```
/Users/miams/Genealogy/RootsMagic/Files/Records - Military/WW II - Draft Registration/
```

**No state-based subdirectories** - all images in single directory.

## Implementation Architecture

### New Service: `DraftImageProcessor`

```python
class DraftImageProcessor:
    """Analyze and process draft registration card images."""

    def __init__(self, keep_originals: bool = False):
        """
        Args:
            keep_originals: If True, keep original downloaded images
                          If False, delete after successful processing
        """
        self.keep_originals = keep_originals

    async def analyze_image(self, image_path: Path) -> ImageAnalysis:
        """
        Analyze image to determine type and processing needs.

        Returns:
            ImageAnalysis with:
            - aspect_ratio: float
            - colorspace: str (Gray, sRGB, etc.)
            - needs_second_image: bool
            - needs_deskew: bool
            - needs_rotation: bool
            - estimated_type: str (A, B, C, D, Unknown)
        """

    async def process_front_card(self, image_path: Path) -> Path:
        """Process front card: deskew if needed, trim."""

    async def process_back_card(self, image_path: Path) -> Path:
        """Process back card: rotate if needed, deskew if needed, trim."""

    async def combine_cards(self, front_path: Path, back_path: Path,
                           output_path: Path) -> Path:
        """Combine front and back cards horizontally."""

    async def cleanup_originals(self, *image_paths: Path) -> None:
        """Delete original images if keep_originals=False."""
```

### Integration Points

#### FamilySearchDraftScraper
```python
async def scrape_and_download(self, url: str, rin: Optional[int] = None):
    # 1. Download first image
    first_image = await self._download_image()

    # 2. Analyze
    processor = DraftImageProcessor(keep_originals=TESTING_MODE)
    analysis = await processor.analyze_image(first_image)

    # 3. Download second image if needed
    if analysis.needs_second_image:
        second_image = await self._download_second_image()
    else:
        second_image = None

    # 4. Process and combine
    if second_image:
        front = await processor.process_front_card(first_image)
        back = await processor.process_back_card(second_image)
        final = await processor.combine_cards(front, back, output_path)
    else:
        # Already combined, minimal processing
        final = await processor.process_combined_card(first_image, output_path)

    # 5. Generate final filename from RIN
    if rin:
        final_name = get_filename_from_rin(rin, rmtree_path)
        final_path = STORAGE_DIR / final_name
        shutil.move(final, final_path)

    # 6. Cleanup
    await processor.cleanup_originals(first_image, second_image)

    return final_path
```

#### AncestryLibraryDraftScraper
Similar integration - replace existing combine logic with `DraftImageProcessor`.

## Testing Strategy

### Unit Tests
- `test_analyze_image()` - Verify aspect ratio detection
- `test_process_front_card()` - Deskew + trim
- `test_process_back_card()` - Rotate + deskew + trim
- `test_combine_cards()` - Horizontal append
- `test_get_filename_from_rin()` - RootsMagic lookup

### Integration Tests
- Test with sample images a, b1/b2, c1/c2, d1/d2
- Verify final dimensions and aspect ratios
- Verify file naming with real RINs
- Verify cleanup (originals deleted vs kept)

### Acceptance Criteria
1. Type A images pass through unchanged
2. Type B images combine to ~2,969 x 1,790
3. Type C images deskew and combine to ~2,349 x 1,318
4. Type D images rotate and combine to ~2,479 x 1,448
5. All final images have aspect ratio 1.6-1.8
6. File names follow "surname, givenname (birth-death).jpg" format
7. Images stored in correct directory
8. Original images deleted after processing (when not in testing mode)

## Configuration

### Settings
```python
# config/settings.py
DRAFT_IMAGE_PROCESSING = {
    'keep_originals': False,  # Set True during testing
    'deskew_threshold': 40,   # Percentage for -deskew
    'trim_fuzz': 10,          # Percentage for -fuzz
    'target_aspect_ratio': 1.66,
    'combined_threshold': 1.60,  # Aspect >= this = already combined
    'single_card_min': 1.30,     # Aspect >= this = front card
    'skew_tolerance': 1.0,       # Degrees - below this, skip deskew
}

DRAFT_STORAGE_DIR = Path(
    "/Users/miams/Genealogy/RootsMagic/Files/Records - Military/WW II - Draft Registration"
)
```

## Error Handling

### Scenarios
1. **ImageMagick not available**: Fail gracefully with clear error message
2. **Skew detection fails**: Fall back to no deskew, log warning
3. **Second image download fails**: Keep first image, log error, mark for manual review
4. **RIN not found in database**: Use default naming with RIN: `Draft_RIN_{rin}.jpg`
5. **Birth/death years missing**: Use partial format: `surname, givenname.jpg`
6. **File already exists**: Append counter: `surname, givenname (birth-death)_2.jpg`

## Future Enhancements

1. **ML-based skew detection**: Use computer vision for more accurate tilt detection
2. **OCR verification**: Extract text from cards to verify orientation is correct
3. **Quality assessment**: Score image quality, flag low-quality scans
4. **Automatic cropping**: Detect card boundaries more precisely
5. **Batch processing**: Process multiple images in parallel
6. **Preview generation**: Create thumbnail previews for UI display

---

**Status**: ✅ Design Complete
**Next**: Implementation
**Updated**: 2026-02-08
