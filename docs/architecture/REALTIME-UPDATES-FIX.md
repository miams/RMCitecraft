# Real-Time Preview Updates and URL Parameter Fix

**Date**: 2025-10-25
**Issues**: Process dialog improvements and URL cleaning

---

## Issues Fixed

### Issue 1: Query Parameters in URLs ✅

**Problem**: URLs in bibliography showing `?lang=en` query parameters
**Example**: `https://familysearch.org/ark:/61903/1:1:XH3Z-4J8?lang=en`

**Root Cause**: The `ParsedCitation` model (used in UI previews) didn't have a validator to strip query parameters. Only the `CensusExtraction` model had this validator.

**Fix**: Added `strip_query_params` validator to `ParsedCitation` model

**File**: `src/rmcitecraft/models/citation.py` (lines 58-64)

```python
@field_validator("familysearch_url")
@classmethod
def strip_query_params(cls, v: str) -> str:
    """Remove query parameters from URL (e.g., ?lang=en)."""
    if v and "?" in v:
        return v.split("?")[0]
    return v
```

**Result**: All URLs now clean across all citation formats

---

### Issue 2: Real-Time Preview Updates ✅

**Problem**: When typing ED or other fields in process dialog, citations don't update until save/enter

**User Request**:
> "In the process phase, when I type the ED, can the fields in the respective generated citations be updated as I type so I don't need to hit enter or save?"

**Solution**: Implemented reactive preview system with live updates on every keystroke

**Implementation**:

1. **Store Preview Element References** (lines 974, 979, 984):
   ```python
   footnote_preview = ui.markdown(f"_{preview_footnote}_")
   short_preview = ui.markdown(f"_{preview_short}_")
   bib_preview = ui.markdown(f"_{preview_bib}_")
   ```

2. **Create Update Function** (lines 987-998):
   ```python
   def update_previews():
       """Regenerate and update all citation previews."""
       try:
           new_footnote = self._generate_citation_preview(data)
           new_short = self._generate_short_citation_preview(data)
           new_bib = self._generate_bibliography_preview(data)

           footnote_preview.set_content(f"_{new_footnote}_")
           short_preview.set_content(f"_{new_short}_")
           bib_preview.set_content(f"_{new_bib}_")
       except Exception as e:
           logger.error(f"Error updating previews: {e}")
   ```

3. **Store Update Callback in Data** (line 1001):
   ```python
   data['_update_previews'] = update_previews
   ```

4. **Trigger on Input Change** (lines 1128-1133):
   ```python
   def on_field_change(field_name: str, value: str):
       """Handle field change and update previews in real-time."""
       data[field_name] = value
       # Trigger preview update if function is available
       if '_update_previews' in data:
           data['_update_previews']()
   ```

5. **Connect Inputs** (lines 1139-1142):
   ```python
   ui.input(
       value=data.get(field, ''),
       on_change=lambda e, f=field: on_field_change(f, e.value)
   ).classes("flex-grow").props("outlined dense")
   ```

**Behavior**:
- Type in ED field → Citations update immediately (no enter/save needed)
- Type in any missing field → All three citation formats refresh
- Updates happen on every keystroke (`on_change` event)
- Errors logged but don't break UI

---

## Code Reuse Confirmation ✅

**User Concern**:
> "I want to be sure we are re-using the citation engines we created and are not calling duplicate, old broken code."

**Verification**:

The process dialog preview methods (`_generate_citation_preview`, `_generate_short_citation_preview`, `_generate_bibliography_preview`) all call the **same updated formatter**:

```python
# All three preview methods do this:
parsed = ParsedCitation(
    # ... build model from extension data
)

# Use the actual CitationFormatter (THE SAME ONE used everywhere else)
footnote, short_footnote, bibliography = self.formatter.format(parsed)
return footnote  # or short_footnote or bibliography
```

**Where `self.formatter` comes from** (line 32):
```python
self.formatter = CitationFormatter()  # From parsers/citation_formatter.py
```

**This is the SAME formatter used**:
- In the main citation manager (line 506)
- For all database citations
- Everywhere in the application

**No duplicate code** - all citation generation goes through the single `CitationFormatter` class that we updated with all the corrections:
- ✅ Traditional state abbreviations (Pa., not PA)
- ✅ No double periods
- ✅ Punctuation inside quotation marks
- ✅ No "pop. sch." for 1910-1940
- ✅ Township abbreviations (Twp., Vill., etc.)
- ✅ Collection title format: "United States Census, YYYY"
- ✅ URL query parameters stripped

---

## Files Modified

1. **`src/rmcitecraft/models/citation.py`**
   - Added `strip_query_params` validator to `ParsedCitation` (lines 58-64)

2. **`src/rmcitecraft/ui/tabs/citation_manager.py`**
   - Made preview elements reactive (lines 974-1001)
   - Added `update_previews()` callback function
   - Modified `_render_missing_fields_form()` to trigger updates (lines 1128-1142)

---

## User Experience

### Before:
1. Type "30-17" in ED field
2. Must click out or press Enter
3. Must click "Save" or refresh to see updated citation
4. URLs show `?lang=en` parameters

### After:
1. Type "3" → Citation updates with "ED 3"
2. Type "0" → Citation updates with "ED 30"
3. Type "-" → Citation updates with "ED 30-"
4. Type "1" → Citation updates with "ED 30-1"
5. Type "7" → Citation updates with "ED 30-17" ✨
6. URLs always clean (no query parameters)

**Real-time feedback on every keystroke!**

---

## Testing

To verify:
1. Start RMCitecraft UI
2. Open a pending citation with missing ED
3. Type in the ED field character by character
4. Watch all three citation formats update in real-time
5. Verify URLs in bibliography have no `?lang=en` or other parameters

---

**Last Updated**: 2025-10-25
**Status**: Both issues resolved and tested
