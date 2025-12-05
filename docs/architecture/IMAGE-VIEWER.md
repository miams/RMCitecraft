---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Census Image Viewer Component

**Date**: 2025-10-25
**Feature**: Embedded census image viewer with zoom/pan controls

---

## Overview

The census image viewer provides an interactive way to display census record images alongside citation editing forms. Users can zoom to 150%, pan to specific areas (like "top right corner"), and navigate multiple census images for a person.

---

## Components

### 1. MediaPathResolver

**Module**: `src/rmcitecraft/utils/media_resolver.py`

Resolves RootsMagic symbolic media paths to absolute file system paths.

**RootsMagic Path Symbols:**
- `?` = Media root directory (typically `~/Genealogy/RootsMagic/Files`)
- `~` = User's home directory
- `*` = Database directory (folder containing `.rmtree` file)

**Example Usage:**

```python
from pathlib import Path
from rmcitecraft.utils.media_resolver import MediaPathResolver

# Initialize with media root
resolver = MediaPathResolver(
    media_root="/Users/miams/Genealogy/RootsMagic/Files",
    database_path="data/Iiams.rmtree"
)

# Resolve a media path from database
image_path = resolver.resolve(
    media_path="?\\Records - Census\\1930 Federal",
    media_file="1930, Pennsylvania, Greene - Iams, George B.jpg"
)
# Returns: Path("/Users/miams/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/1930, Pennsylvania, Greene - Iams, George B.jpg")

# Get census image for specific event
conn = sqlite3.connect("data/Iiams.rmtree")
cursor = conn.cursor()

image_path = resolver.get_census_image_for_event(cursor, event_id=12345)

# Get all census images for a person
images = resolver.get_census_images_for_person(cursor, person_id=5624)
# Returns: [(1940, Path("...")), (1930, Path("...")), (1900, Path("..."))]
```

**Methods:**

- `resolve(media_path, media_file)` - Resolve path symbols to absolute path
- `get_census_image_for_event(cursor, event_id)` - Get census image for EventID
- `get_census_images_for_person(cursor, person_id)` - Get all census images for PersonID

---

### 2. CensusImageViewer

**Module**: `src/rmcitecraft/ui/components/image_viewer.py`

Interactive NiceGUI component with zoom and pan controls.

**Features:**
- Zoom controls: 50% - 300%
- Preset zoom levels: 100%, 150%, 200%
- Pan controls: Arrow buttons or drag
- Position to specific image area
- Keyboard shortcuts: Ctrl+/-, Ctrl+0 (reset)

**Example Usage:**

```python
from pathlib import Path
from rmcitecraft.ui.components.image_viewer import create_census_image_viewer

# Create and render viewer
viewer = create_census_image_viewer(
    image_path=Path("/path/to/census.jpg"),
    initial_zoom=1.5  # Start at 150%
)

# Change image
viewer.set_image(Path("/path/to/another_census.jpg"))

# Position to top-right corner at 150% zoom
viewer.position_to_area(
    x_percent=1.0,   # Right side (0.0 = left, 1.0 = right)
    y_percent=0.0,   # Top (0.0 = top, 1.0 = bottom)
    zoom=1.5         # 150% zoom
)

# Manual zoom control
viewer._set_zoom(2.0)  # 200%

# Manual pan control
viewer._pan(dx=50, dy=-30)  # Pan 50px right, 30px up
```

**UI Layout:**

```
┌─────────────────────────────────────────┐
│ Census Image    [−] 150% [+] [⊡] 100% 150% 200% │
├─────────────────────────────────────────┤
│                                         │
│        [Scrollable Image Area]          │
│                                         │
├─────────────────────────────────────────┤
│         [↑]                             │
│    [←] [⊙] [→]                          │
│         [↓]                             │
└─────────────────────────────────────────┘
```

---

## Integration with Citation Process Dialog

### Side-by-Side Layout

When processing citations with missing fields, display census image alongside form:

```python
from rmcitecraft.utils.media_resolver import MediaPathResolver
from rmcitecraft.ui.components.image_viewer import create_census_image_viewer

# In citation_manager.py process dialog

with ui.row().classes("w-full gap-4"):
    # Left side: Citation form
    with ui.column().classes("w-1/2"):
        ui.label("Complete Citation Details").classes("text-lg font-bold")
        # ... render missing fields form ...

    # Right side: Census image
    with ui.column().classes("w-1/2"):
        # Get census image for this citation's event
        resolver = MediaPathResolver(database_path=self.db_path)
        image_path = resolver.get_census_image_for_event(
            cursor=self.cursor,
            event_id=citation_data['event_id']
        )

        if image_path:
            viewer = create_census_image_viewer(
                image_path=image_path,
                initial_zoom=1.5  # Default to 150% as user requested
            )

            # Optionally position to specific area
            # viewer.position_to_area(x_percent=1.0, y_percent=0.0, zoom=1.5)
        else:
            ui.label("No census image available").classes("text-gray-500")
```

### Automatic Image Detection

When user clicks "Process" for a pending citation:

1. Get EventID from database (links citation to census event)
2. Use `MediaPathResolver` to find linked census image
3. Display image at 150% zoom in right panel
4. User types missing ED/sheet/line while viewing image
5. Real-time citation preview updates as they type

**Workflow:**

```
User clicks "Process" on pending citation
        ↓
Get EventID from WitnessTable (links citation to event)
        ↓
MediaPathResolver.get_census_image_for_event(event_id)
        ↓
Display image at 150% zoom (right panel)
        ↓
User views image and fills missing fields
        ↓
Citation preview updates in real-time
        ↓
User clicks "Save" - citation complete
```

---

## Database Schema

**Relevant Tables:**

```sql
-- Census images linked to events
SELECT
    m.MediaID,
    m.MediaFile,
    m.MediaPath,           -- Contains ?, ~, or * symbols
    m.Caption,
    e.EventID,
    e.EventType,           -- 18 = Census
    e.OwnerID AS PersonID
FROM MultimediaTable m
JOIN MediaLinkTable ml ON m.MediaID = ml.MediaID
JOIN EventTable e ON ml.OwnerID = e.EventID
WHERE ml.OwnerType = 2     -- 2 = Event owner type
  AND m.MediaPath LIKE '%Census%';
```

**MediaLinkTable.OwnerType:**
- 0 = Person
- 2 = Event
- 4 = Citation

---

## File Organization

**Census Image Directory Structure:**

```
~/Genealogy/RootsMagic/Files/
├── Records - Census/
│   ├── 1790 Federal/
│   ├── 1800 Federal/
│   ├── ...
│   ├── 1900 Federal/
│   │   └── 1900, Pennsylvania, Bedford - Iames, Upton.jpg
│   ├── 1910 Federal/
│   ├── 1920 Federal/
│   ├── 1930 Federal/
│   │   └── 1930, Pennsylvania, Bedford - Iames, Upton.jpg
│   ├── 1940 Federal/
│   │   └── 1940, Pennsylvania, Bedford - Imes, Upton.jpg
│   ├── 1950 Federal/
│   ├── 1850 Federal Slave Schedule/
│   ├── 1860 Federal Slave Schedule/
│   └── Federal Mortality Schedule 1850-1885/
└── Pictures - People/
    └── ...
```

**Database MediaPath Values:**

```
?\Records - Census\1930 Federal
?\Records - Census\1940 Federal
?\Pictures - People
```

---

## User Experience

### Before Image Viewer

1. User processes pending citation
2. Realizes ED/sheet/line missing
3. Opens FamilySearch in separate browser window
4. Switches back and forth to copy values
5. Manually types values, clicks Save

### After Image Viewer

1. User processes pending citation
2. Census image automatically appears at 150% zoom
3. User views image and citation form side-by-side
4. Types values while viewing image
5. Citation preview updates in real-time
6. Clicks Save when complete

**No window switching required!**

---

## Configuration

**Environment Variables** (`.env`):

```bash
# Media root directory (replaces ? symbol)
RM_MEDIA_ROOT_DIRECTORY=/Users/miams/Genealogy/RootsMagic/Files

# Database path
RM_DATABASE_PATH=/Users/miams/Code/RMCitecraft/data/Iiams.rmtree
```

**Default Behavior:**
- If `RM_MEDIA_ROOT_DIRECTORY` not set, defaults to `~/Genealogy/RootsMagic/Files`
- Zoom defaults to 150% (user's preference)
- Image positioned at top-left (can be customized)

---

## Future Enhancements

**Potential Features:**

1. **Mouse Wheel Zoom**: Zoom with scroll wheel
2. **Drag to Pan**: Click and drag image to pan
3. **Fit to Width**: Zoom to fit image width in viewport
4. **Fullscreen Mode**: Expand image to full screen
5. **Image Rotation**: Rotate 90° for sideways scans
6. **Brightness/Contrast**: Adjust image for readability
7. **Multiple Images**: Thumbnail strip if multiple census pages
8. **Keyboard Shortcuts**:
   - `Ctrl +` / `Ctrl -`: Zoom in/out
   - `Ctrl 0`: Reset zoom
   - Arrow keys: Pan
   - `Space`: Toggle fullscreen

---

## Testing

**Test Scenarios:**

1. **Path Resolution**:
   ```python
   # Test ? symbol resolution
   resolver = MediaPathResolver(media_root="/Users/miams/Genealogy/RootsMagic/Files")
   path = resolver.resolve("?\\Records - Census\\1930 Federal", "test.jpg")
   assert path == Path("/Users/miams/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/test.jpg")
   ```

2. **Image Viewer Rendering**:
   ```python
   viewer = create_census_image_viewer(image_path=Path("test.jpg"))
   assert viewer.zoom_level == 1.0
   viewer._set_zoom(1.5)
   assert viewer.zoom_level == 1.5
   ```

3. **Database Integration**:
   ```python
   # Test getting image for PersonID 5624
   images = resolver.get_census_images_for_person(cursor, person_id=5624)
   assert len(images) == 3  # 1940, 1930, 1900
   assert images[0][0] == 1940  # Most recent first
   ```

---

**Last Updated**: 2025-10-25
**Status**: Implemented and ready for integration
**Next Steps**: Integrate viewer into citation_manager.py process dialog
