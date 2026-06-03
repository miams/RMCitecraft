---
priority: high
topics: [draft-registration, images, image-processing, documentation]
status: reference
date: 2026-02-08
---

# Draft Registration Card Image Types - Reference Guide

**Purpose**: Document the various image formats encountered when downloading WWII draft registration cards and how RMCitecraft processes them.

## Overview

Draft registration cards appear in several different formats depending on:
- **Source**: FamilySearch vs AncestryLibrary
- **Registration Type**: Young Men (1940-1947) vs Old Men (1942)
- **Card Format**: Pre-combined vs separate front/back
- **Orientation**: Horizontal vs vertical, rotated vs not rotated

This document catalogs each type with example images and processing requirements.

## Image Type Categories

### Type 1: Pre-Combined Horizontal (Young Men)

**Description**: Both front and back sides already combined horizontally (side-by-side).

**Characteristics**:
- Single image file
- Front (Registration Card) on left
- Back (Registrar's Report) on right
- Landscape orientation
- Both sides properly aligned

**Example**: `type1_precombined_horizontal.jpg`

**Person**: Clifford Heath Imes, Serial U 103 6, California (San Bernardino County)
**Collection**: U.S., World War II Draft Cards Young Men, 1940-1947
**Size**: 669 KB (original)

**Processing Required**: ✅ None - ready to store as-is

**Source**: Typically FamilySearch 3:1 image ARKs or some AncestryLibrary downloads

---

### Type 2: Separate Young Men Cards

**Description**: Front and back cards as separate image files that need horizontal combination.

#### Type 2A: Front Card
**Example**: `type2_young_men_front.jpg`

**Characteristics**:
- Registration Card (left side only)
- Contains: Name, serial number, place of residence, birth date, employer, contact person
- Form: D.S.S. Form 1 (various revisions)
- Landscape orientation

**Person**: Clifford Heath Imes (same person as Type 1)
**Size**: 329 KB

#### Type 2B: Back Card
**Example**: `type2_young_men_back.jpg`

**Characteristics**:
- Registrar's Report (right side only)
- Contains: Physical description (race, height, weight, eyes, hair, complexion)
- Local board information
- Registration date and location
- Landscape orientation

**Size**: 287 KB

**Processing Required**:
1. ✅ Trim black borders from both cards (25% fuzz)
2. ✅ Ensure both have same height
3. ✅ Combine horizontally (front + back)
4. ✅ Final trim of outer edges

**Source**: FamilySearch 3:1 image ARKs, AncestryLibrary

**Implementation**:
- `familysearch_draft_scraper.py` - Downloads both images
- `ancestrylibrary_automation.py` - `combine_images()` method

---

### Type 3: Old Men Card (Portrait Back)

**Description**: Old Men registration cards where the back side is rotated 90° (portrait orientation).

#### Type 3A: Front Card
**Example**: `type3_old_men_front.jpg`

**Characteristics**:
- Registration Card for men born April 28, 1877 - February 16, 1897
- Different form layout than Young Men
- Landscape orientation
- Contains basic registration info

**Person**: Charles Edgar Imes, Serial U 40, Virginia (Pocahontas)
**Size**: 171 KB

#### Type 3B: Back Card (Rotated)
**Example**: `type3_old_men_back_rotated.jpg`

**Characteristics**:
- Registrar's Report
- **⚠️ ROTATED 90° - Portrait orientation**
- Physical description checkboxes
- Needs rotation before combining

**Size**: 166 KB

**Processing Required**:
1. ✅ Trim black borders from both cards
2. ✅ **Rotate back card 90° counterclockwise to landscape**
3. ✅ Ensure both have same height
4. ✅ Combine horizontally
5. ✅ Final trim

**Source**: FamilySearch 3:1 image ARKs (Old Men collection)

**Implementation Notes**:
- Must detect portrait orientation and rotate
- Check image dimensions: if height > width, likely needs rotation
- `DraftImageProcessor.process_back_card()` handles rotation detection

---

### Type 4: Old Men Card with Processing Stages

**Description**: Demonstrates the image processing pipeline from raw download to final processed card.

#### Type 4A: Raw Front Card
**Example**: `type4_old_men_front_raw.jpg`

**Characteristics**:
- As downloaded from source
- Large black borders on all sides
- D.S.S. Form 1 (Revised 4-1-42)
- May be slightly skewed

**Person**: Chass B. Imes, Serial U 1567, Indiana (LaPorte County)
**Size**: 106 KB (raw)

#### Type 4B: Raw Back Card
**Example**: `type4_old_men_back_raw.jpg`

**Characteristics**:
- As downloaded from source
- Large black borders
- Portrait orientation (rotated 90°)
- Registrar's Report format

**Size**: 89 KB (raw)

#### Type 4C: Processed Front Card
**Example**: `type4_old_men_front_processed.jpg`

**Characteristics**:
- Black borders trimmed
- Better contrast
- Deskewed if needed
- Clean edges

**Size**: 646 KB (after processing - higher quality)

#### Type 4D: Processed Back Card
**Example**: `type4_old_men_back_processed.jpg`

**Characteristics**:
- Black borders trimmed
- **Rotated to landscape orientation**
- Better contrast
- Deskewed if needed
- Ready to combine with front

**Size**: 573 KB (after processing)

**Processing Pipeline**:
```
Raw Download → Trim Borders → Deskew (if needed) → Rotate Back (if portrait) → Combine → Final Trim
```

**Implementation**:
- `DraftImageProcessor.process_front_card()` - Trim, deskew
- `DraftImageProcessor.process_back_card()` - Trim, rotate, deskew
- `DraftImageProcessor.combine_cards()` - Horizontal combination

---

### Type 5: Pre-Combined Vertical (Old Men)

**Description**: Both front and back sides already combined vertically (stacked).

**Example**: `type5_precombined_vertical.jpg`

**Characteristics**:
- Single image file
- Front (Registration Card) on top
- Back (Registrar's Report) on bottom
- **Portrait orientation**
- Both sides stacked vertically

**Person**: Daniel W. Imes, Serial U 1814, Maryland (Cumberland)
**Collection**: Old Men registration
**Size**: 184 KB

**Processing Required**:
- Option 1: ✅ Store as-is (vertical format)
- Option 2: ✅ Split into front/back, rotate/process, recombine horizontally

**Source**: Some FamilySearch 3:1 image ARKs (less common)

**Implementation Notes**:
- Currently stored as-is
- Future enhancement: Could split and recombine to match standard horizontal format
- Detection: If height >> width, likely vertically combined

---

## Processing Requirements Summary

| Type | Trim | Rotate | Deskew | Combine | Notes |
|------|------|--------|--------|---------|-------|
| **Type 1** (Pre-combined horizontal) | ❌ | ❌ | ❌ | ❌ | Ready as-is |
| **Type 2** (Separate Young Men) | ✅ | ❌ | Optional | ✅ | Standard processing |
| **Type 3** (Old Men, portrait back) | ✅ | ✅ Back | Optional | ✅ | Must rotate back |
| **Type 4** (Raw with borders) | ✅ | ✅ Back | ✅ | ✅ | Full processing pipeline |
| **Type 5** (Pre-combined vertical) | ❌ | ❌ | ❌ | ❌ | Store as-is or split/recombine |

## Image Processing Services

### Core Classes

**`DraftImageProcessor`** (`src/rmcitecraft/services/draft_image_processor.py`)
- `process_front_card()` - Trim, deskew front card
- `process_back_card()` - Trim, rotate (if portrait), deskew back card
- `combine_cards()` - Horizontal combination with centering
- `cleanup_originals()` - Remove temporary files

**`AncestryLibraryAutomation`** (`src/rmcitecraft/services/ancestrylibrary_automation.py`)
- `combine_images()` - ImageMagick-based combination with trim
- Used for both FamilySearch and Ancestry downloads

### ImageMagick Commands

**Trimming with Fuzz** (remove black borders):
```bash
convert input.jpg -fuzz 25% -trim +repage output.jpg
```

**Rotation** (portrait to landscape):
```bash
convert input.jpg -rotate 90 output.jpg
# or -rotate -90 depending on orientation
```

**Deskewing** (straighten tilted cards):
```bash
convert input.jpg -deskew 40% output.jpg
```

**Horizontal Combination with Centering**:
```bash
# Extend shorter image to max height (centered)
convert front.jpg -gravity center -background black \
  -extent WxH back.jpg +append -fuzz 25% -trim +repage combined.jpg
```

## Detection Logic

### Primary Method: Connected Component Analysis (Recommended)

**As of 2026-02-09**, RMCitecraft uses ImageMagick connected component analysis to accurately detect card structure.

**Process:**
1. Convert image to grayscale
2. Threshold to separate paper (white) from background (black)
3. Find distinct white regions (paper cards)
4. Analyze region count and spatial arrangement

**ImageMagick Command:**
```bash
magick image.jpg \
  -colorspace Gray \
  -threshold 40% \
  -define connected-components:verbose=true \
  -define connected-components:area-threshold=50000 \
  -connected-components 8 \
  output.png
```

**Detection Rules:**

| Regions | Arrangement | Type | Confidence |
|---------|-------------|------|------------|
| 2 large (>1M pixels) | Side-by-side (x-gap < 50px) | **Type 1** | High |
| 2 large (>1M pixels) | Stacked (y-gap < 50px) | **Type 5** | High |
| Other | N/A | Unknown → fallback to aspect ratio | Low |

**Example Output:**
```
Objects (id: bounding-box centroid area mean-color):
  227: 1804x1208+1+298 904.7,904.3 2.15338e+06 gray(255)    ← LEFT CARD
  2: 1200x1799+1808+1 2408.2,836.5 1.93911e+06 gray(255)    ← RIGHT CARD
  0: 3008x1804+0+0 925.1,902.1 1.12959e+06 gray(0)          ← BLACK BACKGROUND

→ Detected Type 1: left ends at x=1805, right starts at x=1808, gap=3px
```

**Implementation:**
```python
from rmcitecraft.services.draft_image_processor import DraftImageProcessor

processor = DraftImageProcessor()
type_result = await processor.detect_image_type(image_path)

if type_result.type == "Type 1":
    # Pre-combined, no processing needed
    print(f"Confidence: {type_result.confidence}")
    print(f"Regions: {len(type_result.regions)}")
```

### Fallback Method: Aspect Ratio (Legacy)

**Used when connected component analysis is inconclusive or fails.**

**Check 1: Single vs Dual Image**
- Single image: Type 1, Type 5, or pre-downloaded combined
- Dual images: Type 2, Type 3, Type 4

**Check 2: Aspect Ratio Heuristics**
```python
aspect_ratio = width / height

if aspect_ratio >= 1.60:
    # Likely Type 1 (combined horizontal)
    type = "Type 1"
    confidence = "medium"  # Lower confidence without structural analysis
elif aspect_ratio < 1.0 and height >= 1800:
    # Likely Type 5 (combined vertical)
    type = "Type 5"
    confidence = "medium"
else:
    # Unknown - needs second image
    type = "Unknown"
    confidence = "low"
```

**⚠️ Limitation:** Aspect ratio alone cannot distinguish between:
- True Type 1 (two properly combined cards)
- Two unprocessed cards scanned together (need rotation/recombination)

### Determining Card Type (Complete Workflow)

**Step 1:** Run connected component analysis (primary)
**Step 2:** If inconclusive, fall back to aspect ratio
**Step 3:** For dual images (Type 2/3/4), check orientation:

```python
# For back cards
if height > width:
    # Portrait orientation - Type 3 or Type 4 back
    needs_rotation = True
else:
    # Landscape orientation - Type 2
    needs_rotation = False
```

**Step 4:** Check for borders and determine processing needs:
```python
# Sample edge pixels to detect dark borders
# If mean pixel value < 50, significant border exists
needs_trimming = True
```

**Step 5:** Determine registration type (optional):
```python
# Check form text via OCR or filename
if "born on or after April 28, 1877" in text:
    registration_type = "old_men"
elif "born on or after January 1, 1922" in text:
    registration_type = "young_men"
```

## Source-Specific Patterns

### FamilySearch 3:1 Image ARKs

**Typical Pattern**: Separate front/back images (Type 2, Type 3, Type 4)
- Always downloads 2 images
- Back may be rotated (Old Men cards)
- May have black borders

**URL Format**: `https://www.familysearch.org/ark:/61903/3:1:xxxxx`

**Download Method**: CMD-S keyboard shortcut in image viewer

### AncestryLibrary

**Typical Pattern**: Separate front/back images (Type 2, Type 4)
- Downloads 2 images via Tool menu
- Usually landscape orientation
- May have black borders
- Higher resolution than FamilySearch

**URL Format**: `https://www.ancestrylibrary.com/search/collections/2238/records/xxxxxx`

**Download Method**: Tool menu → Download option

### FamilySearch 1:1 Person ARKs

**Typical Pattern**: Pre-combined (Type 1) OR separate images (Type 2)
- Metadata-rich (15+ fields)
- Navigate to "View Original Document"
- Download dialog with format selection

**URL Format**: `https://www.familysearch.org/ark:/61903/1:1:xxxxx`

## Testing Checklist

When implementing or updating image processing:

- [ ] Test Type 1 (pre-combined horizontal) - should pass through unchanged
- [ ] Test Type 2 (separate Young Men) - trim + combine
- [ ] Test Type 3 (Old Men portrait back) - trim + rotate back + combine
- [ ] Test Type 4 (raw with borders) - full processing pipeline
- [ ] Test Type 5 (pre-combined vertical) - store as-is
- [ ] Verify portrait detection works correctly
- [ ] Verify rotation direction (90° vs -90°)
- [ ] Check final combined dimensions
- [ ] Verify black border removal
- [ ] Test with cards from different states
- [ ] Test with different registration years

## File Naming Convention

**Final Combined Images**:
```
surname, givenname (birth-death).jpg
```

**Examples**:
- `Imes, Clifford Heath (1922-1985).jpg`
- `Imes, Charles Edgar (1877-1960).jpg`
- `Imes, Chass B. (1878-1943).jpg`

**Temporary/Processing Files**:
- `1_image.jpg`, `2_image.jpg` - Raw downloads
- `1_trimmed.jpg`, `2_trimmed.jpg` - After trim
- `2_rotated.jpg` - After rotation (back card)
- `combined_temp.jpg` - Before final trim

## Common Issues and Solutions

### Issue: Back Card Upside Down

**Problem**: Back card rotated 180° instead of 90°

**Solution**: Check rotation direction logic
```python
# Correct rotation
if is_portrait and is_back_card:
    # Rotate 90° counterclockwise
    subprocess.run(["convert", input, "-rotate", "90", output])
```

### Issue: Cards Not Aligned Horizontally

**Problem**: Different heights after trimming

**Solution**: Use `-extent` with `-gravity center` to equalize heights:
```bash
convert front.jpg -gravity center -background black \
  -extent ${width}x${max_height} front_extended.jpg
```

### Issue: Excessive Trimming

**Problem**: `-fuzz 25%` removes too much content

**Solution**: Reduce fuzz percentage or add padding:
```bash
# Lower fuzz
convert input.jpg -fuzz 15% -trim +repage output.jpg

# Or add padding back
convert input.jpg -fuzz 25% -trim -bordercolor black \
  -border 10x10 +repage output.jpg
```

### Issue: Poor Quality After Processing

**Problem**: Loss of quality during processing

**Solution**: Use high-quality ImageMagick settings:
```bash
convert input.jpg -quality 95 -density 300 output.jpg
```

## Future Enhancements

1. **Automatic Type Detection**: ML-based classification of card types
2. **OCR Integration**: Extract text directly from images
3. **Quality Assessment**: Automatic detection of blur, skew, low contrast
4. **Smart Rotation**: Detect text orientation to determine correct rotation
5. **Vertical to Horizontal Conversion**: Auto-convert Type 5 to standard horizontal format
6. **Batch Processing UI**: Show preview of processing steps
7. **Manual Correction Interface**: Allow user to adjust rotation/cropping

## See Also

- [DRAFT_REGISTRATION_IMAGE_DOWNLOAD_STATUS.md](DRAFT_REGISTRATION_IMAGE_DOWNLOAD_STATUS.md) - Implementation status
- [DRAFT_REGISTRATION_FEATURE_REQUIREMENTS.md](DRAFT_REGISTRATION_FEATURE_REQUIREMENTS.md) - Requirements
- `src/rmcitecraft/services/draft_image_processor.py` - Image processing service
- `src/rmcitecraft/services/ancestrylibrary_automation.py` - Image download and combination

## Revision History

| Date | Changes |
|------|---------|
| 2026-02-09 | **Major update**: Implemented connected component analysis for Type 1/5 detection. Added `detect_image_type()` method using ImageMagick structural analysis instead of aspect ratio heuristics. Documented new detection methodology with examples. |
| 2026-02-08 | Initial documentation with 5 image types cataloged |
