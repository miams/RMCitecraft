---
priority: archive
topics: [database, census, citation, batch, testing]
---

# Sorting and Status Icon Enhancements

**Date:** October 20, 2025

## New Features

### 1. Third Status Icon - Missing FamilySearch URL ❌

Added a **red error icon** for citations missing FamilySearch URLs, which are critical for citation verification.

#### Status Icon Priority:

| Icon | Color | Status | Meaning | Priority |
|------|-------|--------|---------|----------|
| ❌ `error` | Red | Missing URL | FamilySearch URL not found | **0 (Highest)** |
| ⚠️ `warning` | Amber | Missing Fields | Incomplete citation data | 1 |
| ◯ `radio_button_unchecked` | Blue | Ready | Complete, ready to format | 2 |
| ✓ `check_circle` | Green | Formatted | Already formatted in database | 3 (Lowest) |

**Logic:**
```python
if not has_url:
    # Priority 1: Missing FamilySearch URL (critical error)
    status_icon = "error"
    status_color = "text-red-600"
    status_tooltip = "Missing FamilySearch URL"
elif has_formatted:
    # Already formatted (complete)
    status_icon = "check_circle"
    status_color = "text-green-600"
elif is_complete:
    # Ready to format
    status_icon = "radio_button_unchecked"
    status_color = "text-blue-600"
else:
    # Missing census fields
    status_icon = "warning"
    status_color = "text-amber-600"
```

### 2. Sortable Citation List

Added sort controls to Citation Manager with three sort options:

#### Sort Controls UI:

```
┌─────────────────────────────────────────┐
│ Sort by: [Status] [Name] [ID]           │
└─────────────────────────────────────────┘
```

#### Sort Options:

1. **Sort by Status** (Default)
   - Sorts by status priority: Missing URL → Missing Fields → Ready → Formatted
   - Secondary sort by person name alphabetically
   - **Use case:** Find citations with problems first

2. **Sort by Name**
   - Alphabetical by person name (A-Z)
   - **Use case:** Find specific person

3. **Sort by ID**
   - Numerical by Citation ID
   - **Use case:** Find specific citation number

#### Sort Direction:
- Click same button again to **toggle sort direction** (ascending ↑ / descending ↓)
- Status label shows current sort: `"Sorted by status ↑ (502 citations)"`

### 3. Smart Sorting Implementation

**Status Sort Priority:**
```python
# Sort by status priority, then by name
sorted_citations = sorted(
    citations,
    key=lambda x: (status_priority, person_name_lower),
    reverse=sort_reverse
)
```

**Priority Values:**
- `0` = Missing URL (shown first)
- `1` = Missing fields
- `2` = Ready to format
- `3` = Already formatted (shown last)

When sorted by status ascending (default):
1. All citations with missing URLs appear first
2. Citations with missing census fields
3. Complete citations ready to format
4. Already formatted citations at bottom

## User Workflow Benefits

### Before Sorting:
- Citations displayed in database order
- Hard to find problematic citations
- Manual scanning required

### After Sorting:

**Scenario 1: Find Missing URLs**
```
1. Load 1950 census (502 citations)
2. Sort by Status (default)
3. Missing URLs appear at top with ❌ red icon
4. Click citation → "Open FamilySearch" button disabled
5. User knows which citations need attention
```

**Scenario 2: Find Specific Person**
```
1. Click "Sort by Name"
2. Citations alphabetized
3. Scroll to "Smith, John"
4. Quick access to specific person's citation
```

**Scenario 3: Process in Priority Order**
```
1. Sort by Status (default)
2. Start with top citation (highest priority)
3. Fix missing URL or fields
4. Move to next citation
5. Work through list systematically
```

## UI Changes

### Citation Manager Header:

**Before:**
```
Census Year: [1950 ▼]   Status   [Select All]
```

**After:**
```
Census Year: [1950 ▼]   Status   [Select All]
Sort by: [Status] [Name] [ID]
```

### Status Label:

**Before:**
```
Loaded 502 citations
```

**After:**
```
Sorted by status ↑ (502 citations)
```

### Citation Item:

**Before (2 status icons):**
- ✓ Green = Formatted
- ⚠️ Amber = Missing fields

**After (3 status icons):**
- ❌ Red = Missing URL (new!)
- ⚠️ Amber = Missing fields
- ◯ Blue = Ready to format
- ✓ Green = Formatted

## Implementation Details

### Files Modified:

**`src/rmcitecraft/ui/tabs/citation_manager.py`:**
- Added sort state variables (`sort_by`, `sort_reverse`)
- Added sort control buttons in UI
- Added third status icon logic
- Implemented `_get_citation_sort_key()` - Extract sort keys from citation
- Implemented `_sort_citations()` - Sort citations by criteria
- Implemented `_on_sort_changed()` - Handle sort button clicks
- Updated `_update_citation_list()` - Apply sorting before rendering

**Lines Added:** ~130 lines

### Performance Considerations:

**Sorting Cost:**
- Must parse every citation to determine status
- O(n log n) sort complexity
- For 502 citations: ~0.5-1 second initial sort
- Re-sort on button click: ~0.5-1 second

**Optimization:**
- Could cache parsed results for performance
- Current implementation prioritizes simplicity
- Acceptable for typical dataset sizes (< 1000 citations)

### Sort Behavior:

**Toggle Logic:**
```python
def _on_sort_changed(self, sort_by: str):
    if self.sort_by == sort_by:
        # Same field - toggle direction
        self.sort_reverse = not self.sort_reverse
    else:
        # New field - reset to ascending
        self.sort_by = sort_by
        self.sort_reverse = False
```

**Examples:**
- Click "Status" → Sort by status ascending
- Click "Status" again → Sort by status descending
- Click "Name" → Sort by name ascending (reset direction)
- Click "Name" again → Sort by name descending

## Testing Results

### Test 1: Status Sort (1950 census, 502 citations)

**Result:**
- ❌ Citations with missing URLs: Appear first
- ⚠️ Citations with missing fields: Next
- ◯ Complete citations: After incomplete
- ✓ Formatted citations: At bottom

✓ **Working as expected**

### Test 2: Name Sort

**Result:**
- Citations alphabetized by person name
- A-Z order (or Z-A when reversed)

✓ **Working as expected**

### Test 3: ID Sort

**Result:**
- Citations sorted by CitationID numerically
- Lowest → Highest (or reversed)

✓ **Working as expected**

### Test 4: Toggle Direction

**Result:**
- First click: Ascending ↑
- Second click: Descending ↓
- Status label updates

✓ **Working as expected**

## Future Enhancements

### Option 1: Save Sort Preference
- Remember user's sort preference
- Persist across sessions
- Auto-apply on year selection

### Option 2: Multi-Column Sort
- Primary + secondary sort
- E.g., "Status, then Name"
- More complex UI

### Option 3: Filter by Status
- Show only incomplete citations
- Show only missing URLs
- Reduce list size

### Option 4: Sort Performance
- Cache parsed citations
- Only re-parse when data changes
- Faster sort operations

## User Impact

### What's Better:

✅ **Prioritize Problem Citations**
- Missing URLs highlighted in red
- Sorted to top by default
- Immediate visibility

✅ **Flexible Sorting**
- Sort by priority, name, or ID
- Toggle direction
- Find specific citations quickly

✅ **Visual Clarity**
- 3 distinct status levels
- Color-coded priorities
- Tooltips explain status

### What to Improve:

⚠️ **Sort Performance**
- Slight delay on large datasets
- Could cache parsed results

⚠️ **Sort Persistence**
- Sort resets on year change
- Could remember preference

## Summary

✅ **Three status icons** - Red for missing URLs, Amber for missing fields, Blue for ready, Green for formatted

✅ **Sortable by Status** - Citations with problems appear first (default)

✅ **Sortable by Name** - Find specific person alphabetically

✅ **Sortable by ID** - Find specific citation number

✅ **Toggle Sort Direction** - Click same button to reverse order

✅ **Status Label Updates** - Shows current sort and direction

The Citation Manager is now significantly more user-friendly for managing large numbers of citations and identifying problems that need attention.

---

**Status:** ✅ Implemented and tested

**Ready for:** User review and Week 4 continuation
