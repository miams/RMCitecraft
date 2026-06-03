---
priority: high
topics: [draft-registration, automation, ancestry, familysearch]
status: active
updated: 2026-02-10
---

# Draft Registration Processing - Overview

## Purpose

Automate extraction of WW2 draft registration card metadata and images from FamilySearch and AncestryLibrary, with proper source attribution and Evidence Explained citations.

## Source Hierarchy (CRITICAL)

**Metadata:** ALWAYS scraped from Ancestry (superior data quality)
- Ancestry provides: gender, age, next of kin, normalized height
- FamilySearch lacks these critical fields

**Images:** FamilySearch preferred, Ancestry fallback
- FamilySearch: Higher quality scans
- Ancestry: Used when FamilySearch URL unavailable

**Citations:** FamilySearch preferred, Ancestry fallback

## Workflow

### Standard Workflow (Recommended)

For records with FamilySearch citations:

1. **Discover Ancestry URL** - Search AncestryLibrary by name + birth year
2. **User confirmation** - Prompt user to verify discovered URL
3. **Scrape metadata** - Extract from Ancestry Detail tab
4. **Download images** - From FamilySearch (preferred source)
5. **Process images** - Auto-detect type, deskew, crop, combine
6. **Save to database** - Store in `~/.rmcitecraft/ww2-draft.db` with Ancestry URL

### Ancestry-Only Workflow

For records with only Ancestry citations:

1. **Scrape metadata** - From Ancestry Detail tab
2. **Download images** - From Ancestry (fallback)
3. **Process images** - Same auto-processing
4. **Save to database** - Store with Ancestry URL

### Metadata-Only Mode

For URL discovery without image downloads:

1. **Discover Ancestry URL** - Search AncestryLibrary
2. **User confirmation** - Verify discovered URL
3. **Scrape metadata** - From Ancestry Detail tab
4. **Save to database** - Store metadata + URL only (no images)

## Metadata Fields Extracted

From Ancestry Detail tab:

- Full Name (parsed into given name + surname)
- Gender & Age
- Birth Date & Birth Place
- Residence Place (city)
- Physical Description: Race, Height (normalized: 5' 8"), Weight, Complexion, Eye Color, Hair Color
- Employer
- Registration Date & Registration Place
- Next of Kin (contact person)

## Image Processing

Automatic detection and processing of 5 image types:

| Type | Description | Processing Steps |
|------|-------------|------------------|
| **A** | Already combined horizontal | Content-aware crop only |
| **B** | Color separate cards | Crop → Combine |
| **C** | B&W tilted separate cards | Deskew → Crop → Rotate → Combine |
| **D** | Single card (2 downloads) | Download both → Process → Combine |
| **E** | Vertical combined | Rotate → Content-aware crop |

**Quality Improvements:**
- Content-aware cropping removes borders
- Vertical centering with black background
- Smart deskew with 1° tolerance
- Automatic rotation based on dimensions

See: `docs/architecture/DRAFT_IMAGE_PROCESSING_DESIGN.md` for technical details

## Database Schema

Stored in `~/.rmcitecraft/ww2-draft.db`:

**Tables:**
- `extraction_batch` - Batch tracking
- `draft_registration` - Metadata records

**Key fields in draft_registration:**
- `source_url` - Ancestry URL (always, never FamilySearch)
- `source_type` - "ancestrylibrary" or "familysearch"
- `url_type` - "ancestry_record" or "fs_1_1_person"
- `image_file_path` - Final processed image location
- Person data: name, birth, physical description, etc.

## UI Controls

### Workflow Mode (Radio Buttons)

- **Standard** - FS images + Ancestry metadata *(Default)*
- **Ancestry only** - Ancestry images + metadata
- **Metadata only** - No images, metadata only
- **Custom** - Manual control via advanced options

### Advanced/Debug Options (Collapsible)

- Discover Ancestry URLs
- Process FamilySearch URLs
- Process Ancestry URLs
- Metadata Only Mode

## Related Documentation

- **Architecture**: `docs/architecture/DRAFT_IMAGE_PROCESSING_DESIGN.md`
- **Schema**: `docs/reference/WW2_DRAFT_DATABASE_SCHEMA.yaml`
- **User Guide**: `docs/user-guides/DRAFT_REGISTRATION_IMAGE_DOWNLOAD.md`
- **Feature History**: `docs/projects/DRAFT_REGISTRATION_FEATURES.md`
- **Note Harvesting**: `docs/projects/NOTE_CITATION_HARVESTING.md`

## Implementation Status

✅ **Production Ready** (as of 2026-02-10)

- Ancestry metadata scraping
- FamilySearch image downloads
- Ancestry URL discovery with confirmation
- Image processing (all 5 types)
- Metadata-only mode
- Hybrid radio + checkbox UI
- Proper source_url handling (Ancestry URLs only)
