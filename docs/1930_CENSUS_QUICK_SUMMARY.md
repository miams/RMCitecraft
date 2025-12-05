---
priority: reference
topics: [database, census, citation, batch, testing]
---

# 1930 Census Issue - Quick Summary

**Problem**: All 6 tested 1930 census entries fail validation with missing Enumeration District (ED)

**Root Cause**: ED is NOT available in FamilySearch page metadata - only visible on census images

**Investigation Results**:
- ✅ Extraction code works correctly (comprehensive table + text scraping)
- ✅ URL extraction from formatted citations works
- ✅ Fallback mechanisms all working
- ❌ ED simply doesn't exist on FamilySearch web pages for these 1930 entries
- ❌ Citation text is placeholder format: "Entry for [person], 1930"
- ✅ ED is visible on census image headers (requires manual viewing)

**Why 1940 Worked But 1930 Failed**:
- 1940 citations: Created recently with full extraction, detailed data saved
- 1930 citations: Older placeholders (Sep 2023), minimal data captured

**Solution**: Manual Entry via Batch Processing UI
- Design completed: `docs/architecture/BATCH_PROCESSING_UI_DESIGN.md`
- Three-panel layout: queue + form + image viewer
- User views census image and enters missing fields
- Keyboard-first workflow: <10 keystrokes per citation
- Target: 360+ citations/hour (6x improvement over current manual process)

**Next Step**: Implement Batch UI Phase 1 (Core three-panel layout with navigation)

**Related Docs**:
- Full investigation: `docs/1930_CENSUS_INVESTIGATION_SUMMARY.md`
- Root cause analysis: `docs/1930_CENSUS_ED_EXTRACTION_ISSUE.md`
- Batch UI design: `docs/architecture/BATCH_PROCESSING_UI_DESIGN.md`
- Failed batch log: `docs/misc/census_batch_1930_20251106_170705.md`

**Status**: ✅ Investigation complete - Ready to implement UI solution
