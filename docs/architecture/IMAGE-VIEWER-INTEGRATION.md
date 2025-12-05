---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Census Image Viewer Integration - Complete

**Date**: 2025-10-25
**Status**: ✅ Integrated and Functional

---

## Summary

Successfully integrated census image viewer into the citation processing dialog. When users process pending citations from the browser extension, the census image now automatically appears alongside the citation form at 150% zoom.

---

## Implementation Complete

### Components Created

1. **MediaPathResolver** (`src/rmcitecraft/utils/media_resolver.py`)
   - Resolves RootsMagic symbolic paths (`?`, `~`, `*`) to absolute paths
   - Finds census images for persons and events
   - Handles media root discovery automatically

2. **CensusImageViewer** (`src/rmcitecraft/ui/components/image_viewer.py`)
   - Interactive NiceGUI component with zoom/pan controls
   - 50%-300% zoom range with preset buttons (100%, 150%, 200%)
   - Arrow buttons for panning
   - Programmatic positioning capability

3. **Integration** (`src/rmcitecraft/ui/tabs/citation_manager.py`)
   - Added `_find_census_image_for_person()` helper method
   - Integrated viewer into citation processing dialog
   - Automatic image lookup by person name and census year

### Files Modified

**src/rmcitecraft/ui/tabs/citation_manager.py:**
- Lines 9-10: Added `Path` import
- Lines 22-23: Added image viewer and media resolver imports
- Lines 37-41: Added MediaPathResolver initialization in `__init__()`
- Lines 975-1000: Added image viewer to right column of process dialog
- Lines 1458-1515: Added `_find_census_image_for_person()` helper method

---

## How It Works

### Automatic Image Detection

When user clicks "Process" on a pending citation:

```python
# 1. Extract person info from citation data
person_name = data.get('name', '')        # e.g., "Upton Imes"
census_year = data.get('censusYear')      # e.g., 1930

# 2. Find census image
image_path = self._find_census_image_for_person(person_name, census_year)

# 3. Display image viewer at 150% zoom
if image_path:
    create_census_image_viewer(
        image_path=image_path,
        initial_zoom=1.5  # User's requested 150%
    )
```

### Database Lookup Process

The `_find_census_image_for_person()` method:

1. **Parse name** into given name and surname
2. **Query PersonTable** using RMNOCASE collation:
   ```sql
   SELECT p.PersonID
   FROM PersonTable p
   JOIN NameTable n ON p.PersonID = n.OwnerID
   WHERE n.Surname COLLATE RMNOCASE = 'Imes'
     AND n.Given COLLATE RMNOCASE LIKE 'Upton%'
   ```
3. **Get all census images** for that PersonID
4. **Filter by census year** (match 1930)
5. **Return image path** or None

---

## User Experience

### Before Integration

```
┌─────────────────────────────────────────────────┐
│ Process Citation Dialog                        │
├─────────────────────────────────────────────────┤
│ Left Column:        Right Column:              │
│   Citation Fields     Citation Preview         │
│   Missing Fields                                │
│                                                 │
│ User needs to:                                  │
│ 1. Open FamilySearch in browser                │
│ 2. Switch windows back and forth               │
│ 3. Manually copy ED, sheet, line               │
└─────────────────────────────────────────────────┘
```

### After Integration

```
┌───────────────────────────────────────────────────────────────┐
│ Process Citation Dialog                                      │
├───────────────────────────────────────────────────────────────┤
│ Left Column:          Right Column:                          │
│   Citation Fields     [Census Image @ 150%]                  │
│   Missing Fields      [Zoom: - 150% + ⊡ 100% 150% 200%]    │
│                       [Pan controls: ↑ ← ⊙ → ↓]             │
│                                                               │
│                       Citation Preview                        │
│                       (updates in real-time)                  │
│                                                               │
│ User workflow:                                                │
│ 1. Dialog opens with image at 150% zoom                      │
│ 2. Type ED, sheet, line while viewing image                  │
│ 3. Citations update in real-time                             │
│ 4. Click Save - done!                                        │
└───────────────────────────────────────────────────────────────┘
```

**No window switching required!**

---

## Configuration

### Environment Variables

```bash
# .env file
RM_MEDIA_ROOT_DIRECTORY=/Users/miams/Genealogy/RootsMagic/Files
RM_DATABASE_PATH=/Users/miams/Code/RMCitecraft/data/Iiams.rmtree
```

### Default Behavior

- **Media root auto-discovery**: Defaults to `~/Genealogy/RootsMagic/Files` if not set
- **Initial zoom**: 150% (user's preference)
- **Image positioning**: Top-left (can be customized via `position_to_area()`)

---

## Database Integration

### Person Lookup

Uses **RMNOCASE collation** for case-insensitive name matching:

```python
cursor.execute(
    """
    SELECT p.PersonID
    FROM PersonTable p
    JOIN NameTable n ON p.PersonID = n.OwnerID
    WHERE n.Surname COLLATE RMNOCASE = ?
      AND n.Given COLLATE RMNOCASE LIKE ?
    LIMIT 1
    """,
    (surname, f"{given_name}%")
)
```

### Census Image Lookup

MediaPathResolver handles the complete workflow:

```python
# Get all census images for person (sorted by year)
images = self.media_resolver.get_census_images_for_person(cursor, person_id)

# Returns: [(1940, Path("1940 census.jpg")), (1930, Path("1930 census.jpg")), ...]

# Find matching year
for year, image_path in images:
    if year == census_year:
        return image_path
```

---

## Example: Processing Upton Imes 1930 Census

**Pending Citation Data:**
```json
{
  "name": "Upton Imes",
  "censusYear": 1930,
  "eventPlace": "Southampton, Bedford, Pennsylvania, United States",
  "lineNumber": 32,
  "sheetNumber": "3",
  "sheetLetter": "A"
}
```

**Automatic Image Lookup:**
1. Extract: name="Upton Imes", year=1930
2. Query: Find PersonID for "Imes, Upton"
3. Result: PersonID=5624
4. Query: Get census images for PersonID=5624
5. Result: [(1940, Path("...")), (1930, Path("...")), (1900, Path("..."))]
6. Filter: year=1930
7. Display: `/Users/miams/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/1930, Pennsylvania, Bedford - Iames, Upton.jpg` at 150% zoom

**User sees:**
- Left: Citation form with missing ED field (needs to be filled)
- Right: 1930 census image at 150% zoom showing the record
- User types "30-17" in ED field
- Citation preview updates instantly
- User clicks Save

---

## Error Handling

### Person Not Found

```python
if not person_row:
    logger.debug(f"Person not found: {person_name}")
    return None
```

**UI Fallback:**
```
┌─────────────────────────────┐
│  🖼  No census image        │
│      available              │
│                             │
│  Looking for:               │
│  Upton Imes (1930)          │
└─────────────────────────────┘
```

### Image File Missing

MediaPathResolver checks file existence:

```python
full_path = Path(resolved_path) / media_file

if not full_path.exists():
    logger.warning(f"Media file not found: {full_path}")
    return None
```

### Invalid Census Year

```python
try:
    census_year_int = int(census_year_val)
    image_path = self._find_census_image_for_person(person_name, census_year_int)
except (ValueError, TypeError) as e:
    logger.warning(f"Invalid census year: {census_year_val}")
    # Falls through to "No image available" message
```

---

## Testing Checklist

- [x] MediaPathResolver resolves `?` symbol to media root
- [x] Person lookup works with RMNOCASE collation
- [x] Census images found for existing persons (PersonID 5624)
- [x] Image viewer renders at 150% zoom
- [x] Zoom controls functional (in/out, presets)
- [x] Pan controls functional (arrows, center)
- [x] Missing image shows graceful fallback
- [x] Real-time citation updates still work
- [x] Dialog opens and closes properly

---

## Future Enhancements

### Potential Features

1. **Mouse wheel zoom**: Zoom in/out with scroll wheel
2. **Click and drag pan**: Drag image instead of arrow buttons
3. **Keyboard shortcuts**:
   - `Ctrl +` / `Ctrl -`: Zoom
   - `Ctrl 0`: Reset zoom
   - Arrow keys: Pan
4. **Multiple images**: Thumbnail strip if person has multiple census pages
5. **Image tools**:
   - Brightness/contrast adjustment
   - Rotation (for sideways scans)
   - Fullscreen mode
6. **Smart positioning**: Auto-position to specific area based on line number

---

## Documentation

- **Architecture**: `docs/architecture/IMAGE-VIEWER.md` - Complete API documentation
- **Integration**: This file (`IMAGE-VIEWER-INTEGRATION.md`) - Integration details
- **Real-time Updates**: `docs/implementation/REALTIME-UPDATES-FIX.md` - Citation preview updates

---

**Implementation Status**: ✅ Complete and Integrated
**Next Steps**: User testing and feedback
**Date Completed**: 2025-10-25

