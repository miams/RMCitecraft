---
priority: medium
topics: [draft-registration, features, changelog]
status: active
updated: 2026-02-10
---

# Draft Registration Features - Changelog

## Current Implementation (2026-02-10)

### Core Features

✅ **Ancestry Metadata Scraping** (Primary source)
- Extract from Ancestry Detail tab: name, gender, age, birth, physical description, employer, next of kin
- Superior data quality vs. FamilySearch
- Always used for metadata (never FamilySearch)

✅ **FamilySearch Image Downloads** (Preferred source)
- Download from FamilySearch ARKs (1:1 person pages, 3:1 image pages)
- Higher quality scans than Ancestry
- Proper CDP connection handling

✅ **Ancestry Image Downloads** (Fallback source)
- Used when FamilySearch URL unavailable
- Download both front and back card images

✅ **Ancestry URL Discovery**
- Search AncestryLibrary by name + birth year
- User confirmation dialog with RootsMagic person details
- Save discovered URL as source_url in database

✅ **Image Processing** (5 types auto-detected)
- Type A: Combined horizontal cards → content-aware crop
- Type B: Color separate cards → crop + combine
- Type C: B&W tilted cards → deskew + crop + rotate + combine
- Type D: Single card requiring 2nd download → process both + combine
- Type E: Vertical combined → rotate + content-aware crop

✅ **Metadata-Only Mode**
- Skip image downloads completely
- Scrape and save metadata + URLs only
- Useful for URL discovery phase

✅ **Hybrid UI Controls**
- Radio buttons: Standard, Ancestry-only, Metadata-only, Custom
- Collapsible advanced/debug options for granular control
- Auto-configuration based on workflow mode

✅ **Database Persistence**
- Store in `~/.rmcitecraft/ww2-draft.db`
- source_url field always contains Ancestry URL (never FamilySearch)
- Batch tracking and extraction history

✅ **Download Validation**
- Poll file size to detect Playwright race conditions
- Verify minimum file size (10KB)
- 60-second timeout with proper error handling
- Delete empty/failed downloads

## Recent Fixes (2026-02-08 to 2026-02-10)

### Image Processing Quality Fixes (2026-02-08)

**Vertical Centering Fix**
- Issue: White block under front card instead of black background
- Fix: Added vertical centering with `-gravity center -background black -extent`
- Result: Properly centered cards with black padding

**Content-Aware Crop for Color Images**
- Issue: Border trim not working for color images
- Fix: Added `-fuzz 15%` tolerance for color variation
- Result: Proper border removal on all image types

**Deskew Order Fix**
- Issue: Deskew applied after rotation, incorrect results
- Fix: Moved deskew before rotation in processing pipeline
- Result: Correct orientation for tilted cards

**Type E Implementation**
- Issue: Vertical combined cards not handled
- Fix: Added rotation + content-aware crop for vertical cards
- Result: Proper processing of all 5 image types

### Ancestry URL Handling (2026-02-09 to 2026-02-10)

**Source URL Database Fix**
- Issue: FamilySearch URLs being saved as source_url instead of Ancestry URLs
- Fix: Route discovered Ancestry URLs through Ancestry scraper, update source_url field
- Result: Database always contains Ancestry URLs for proper citations

**Workflow Routing Fix**
- Issue: When Ancestry URL discovered, still scraped metadata from FamilySearch
- Fix: Updated routing logic to use Ancestry scraper when URL discovered
- Result: Metadata always comes from Ancestry (superior quality)

### Download Reliability (2026-02-09)

**Playwright Download Race Condition**
- Issue: `download.save_as()` creates empty files, returns before content arrives
- Fix: Added `_wait_for_download_completion()` polling method
- Result: Validates file size, waits for stable content, 60s timeout

**Empty File Detection**
- Issue: 0-byte files created when downloads fail silently
- Fix: Poll file size every 500ms until stable (3 consecutive checks)
- Result: Detect and delete failed downloads, proper error logging

## Feature Timeline

### Phase 1: Core Batch Processing (Jan-Feb 2025)
- ✅ CSV/XLSX file reading
- ✅ Citation building from FamilySearch URLs
- ✅ Database writing (SourceTable, CitationTable, CitationLinkTable)
- ✅ Batch state tracking
- ✅ UI integration

### Phase 2: Automation & Images (Feb 2025)
- ✅ Playwright browser automation
- ✅ FamilySearch image downloads
- ✅ Basic image processing
- ✅ Image type detection

### Phase 3: Quality & Reliability (Feb 2025)
- ✅ Content-aware cropping
- ✅ Smart deskew with tolerance
- ✅ Vertical centering
- ✅ Download validation
- ✅ Error handling

### Phase 4: Ancestry Integration (Feb 2025)
- ✅ Ancestry URL discovery
- ✅ User confirmation dialogs
- ✅ Ancestry metadata scraping
- ✅ Proper source_url handling
- ✅ Metadata-only mode

### Phase 5: UX Improvements (Feb 2025)
- ✅ Hybrid radio + checkbox UI
- ✅ Collapsible advanced options
- ✅ Workflow presets
- ✅ Clear tooltips and documentation

## Known Limitations

- **Manual URL confirmation required** - Cannot auto-accept discovered URLs (by design)
- **Chrome CDP required** - Must run Chrome with remote debugging enabled
- **Single source per record** - Cannot handle records with both FS and Ancestry URLs simultaneously (uses FS for images, Ancestry for metadata)
- **WW2 only** - WW1 draft cards not yet implemented

## Future Enhancements

- [ ] WW1 draft card support
- [ ] Batch URL confirmation (approve all at once)
- [ ] Image quality scoring and selection
- [ ] OCR metadata extraction from images
- [ ] Citation quality validation against Evidence Explained
