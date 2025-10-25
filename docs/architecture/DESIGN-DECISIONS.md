# Design Decisions

This document captures key design decisions made during development.

## Citation Formatting

### Output Format (Decision: 2025-10-20)
**Question**: What markup format should citation templates generate?

**Decision**: HTML format with basic tags (`<i>`, `<b>`, `<u>`)

**Rationale**: RootsMagic citation fields support basic HTML tags for italics, bold, and underline. All output destined for RootsMagic database fields must use HTML format.

**Examples**:
- Italics: `<i>FamilySearch</i>`
- Bold: `<b>United States Census</b>`
- Underline: `<u>text</u>`

---

## LLM Extraction Behavior

### Missing Field Handling (Decision: 2025-10-20)
**Question**: When LLM cannot extract required fields, should it guess or leave blank?

**Decision**: **Option A** - Strict extraction, no guessing

**Behavior**:
- If field cannot be reliably extracted from input, set to `None`
- Add field name to `missing_fields` array
- User will be prompted to fill in missing data during generation phase
- Never make "best guesses" - prefer explicit `None` over uncertain values

**Example**:
```python
# If ED is not in FamilySearch entry
{
    "enumeration_district": None,
    "missing_fields": ["enumeration_district"],
    "confidence": {}  # No confidence score for missing fields
}
```

---

### Confidence Thresholds (Decision: 2025-10-20)
**Question**: When should low-confidence extractions be flagged for user review?

**Decision**: **Option A** - Flag if any field < 0.8 confidence

**Behavior**:
- Calculate per-field confidence scores (0.0-1.0)
- If **any field** has confidence < 0.8, flag citation for user review
- UI will show confidence indicators on review screen
- User can accept or edit before final generation

**Thresholds**:
- `>= 0.9`: High confidence (green indicator)
- `0.8-0.89`: Medium confidence (yellow indicator)
- `< 0.8`: Low confidence (red indicator, requires review)

---

### Validation Rules (Decision: 2025-10-20)
**Question**: When should citation extraction be rejected as invalid?

**Decision**: Add missing fields to array for user input, don't reject

**Behavior**:
- **Never reject** an extraction due to missing fields
- Always add missing required fields to `missing_fields` array
- User will provide missing data during generation phase
- Only reject on:
  - Completely unparseable input
  - Invalid census year (not 1790-1950 or not divisible by 10)
  - Malformed FamilySearch URL (if present)

**Required Fields by Census Year**:
- 1790-1840: year, state, county, town_ward, sheet, person_name
- 1850-1870: year, state, county, town_ward, sheet, dwelling_number, person_name
- 1880: year, state, county, town_ward, enumeration_district, sheet, family_number, person_name
- 1900-1950: year, state, county, town_ward, enumeration_district, sheet, family_number, person_name

---

## State and Location Handling

### State Abbreviations (Decision: 2025-10-20)
**Question**: How should state names be abbreviated in short footnotes?

**Decision**: **Option B** - Manual lookup table with traditional abbreviations

**Rationale**:
- Traditional genealogy abbreviations differ from USPS codes
- Examples use "Oh." (not "OH") and "Md." (not "MD")
- Consistency requires controlled lookup table

**Implementation**:
```python
STATE_ABBREVIATIONS = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    # ... etc
    "Maryland": "Md.",
    "Ohio": "Oh.",
    "Pennsylvania": "Penn.",
    # ... etc
}
```

**County Abbreviation**: Always use "Co." (e.g., "Noble Co.")

---

## Person Name Handling

### Name Formatting (Decision: 2025-10-20)
**Question**: How should person names be formatted, especially with household notations?

**Decision**: Extract name exactly as written in census, require user review

**Behavior**:
- LLM extracts primary person's name from citation
- **Do not normalize** (preserve exactly as written)
- For household entries like "William H Ijams in household of Margaret E Brannon":
  - Extract: "William H Ijams" (primary person only)
  - Ignore household notation for citation purposes
- **Always flag for user review** if:
  - Middle initials present (may or may not have periods)
  - Suffixes present (Jr., Sr., III, Dr., Rev., etc.)
  - Unusual formatting
  - Household notation was present

**User Review Required Because**:
- Name must match exactly as written in census image
- Middle initials may vary: "William H Ijams" vs "William H. Ijams"
- Only user viewing image can confirm exact format

**UI Behavior**:
- Show extracted name
- Allow user to edit
- Provide "View FamilySearch Page" button for verification

---

## Census Year Handling

### 1890 Census (Decision: 2025-10-20)
**Question**: Should 1890 have special handling due to most records being destroyed?

**Decision**: **Skip 1890 census support** (defer to Phase 5 or later)

**Rationale**:
- Most 1890 census destroyed in fire (only fragments survive)
- Very rare in practice
- Focus on common census years first (1790-1880, 1900-1950)
- Can add later if needed

**Implementation**:
- Support years: 1790-1880 (every 10 years), 1900-1950 (every 10 years)
- If 1890 encountered, show error: "1890 census not currently supported"

---

## Performance and Concurrency

### Batch Processing Concurrency (Decision: 2025-10-20)
**Question**: How many citations should be processed in parallel?

**Decision**: **Option A** - Configurable with default of 10

**Configuration**:
```python
# In .env
LLM_MAX_CONCURRENT_EXTRACTIONS=10

# Adjustable based on:
# - LLM provider rate limits
# - System resources
# - User preference
```

**Recommended Values**:
- **Anthropic Claude**: 10 (conservative, avoid rate limits)
- **OpenAI**: 20 (higher rate limits)
- **Ollama (local)**: 5 (CPU-bound, avoid overload)

**Implementation**:
- Use `asyncio.Semaphore` to limit concurrency
- Show progress bar: "Processing 15 citations (3/15 complete)..."
- Allow user to cancel batch operation

---

## Change Log

| Date | Decision | Modified By |
|------|----------|-------------|
| 2025-10-20 | All initial design decisions | User + Claude |

---

## Future Decisions Needed

### Phase 2 (Citation UI)
- Window size and positioning preferences
- Color scheme for confidence indicators
- Keyboard shortcut mappings

### Phase 3 (Image Monitoring)
- Download folder auto-detection strategy
- File conflict resolution (if file already exists)
- Thumbnail generation settings

### Phase 4 (Image-DB Integration)
- Caption format preferences
- Media folder organization strategy

### Phase 5 (Polish)
- Support for 1890 census (if demand exists)
- State census templates
- Privacy settings defaults

---

## Notes

- All decisions are documented with rationale
- Decisions can be revisited if new information emerges
- User preferences should be configurable where reasonable
- Default values should work well for 80% of use cases
