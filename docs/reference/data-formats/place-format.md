# RootsMagic 11: Place Name Format and Structure

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** PlaceTable, EventTable
**Purpose:** Document place name format, hierarchy, and field usage

---

## Overview

RootsMagic uses a **hierarchical, comma-delimited** place name format to store geographic locations. Places range from specific addresses to countries, with most following a standard 4-level hierarchy: City, County, State/Province, Country.

### Key Concepts

- **Hierarchical Structure:** Places organized from specific to general, separated by commas
- **Comma-Delimited Format:** Each level separated by `, ` (comma-space)
- **Normalized Names:** Standardized place names for consistency
- **Reverse Order:** Places stored in reverse order for alphabetical sorting
- **Master/Detail:** Relationship for place details (cemeteries, buildings within cities)
- **Coordinates:** Latitude/Longitude support with precision indicator

---

## Place Name Format Specification

### Standard Format

```
City, County, State/Province, Country
```

**Examples:**
```
Baltimore, Baltimore, Maryland, United States
Pittsburgh, Allegheny, Pennsylvania, United States
Aberdeen, Brown, South Dakota, United States
London, London, England, United Kingdom
```

### Format Rules

1. **Separator:** Comma followed by space (`, `)
2. **Order:** Specific to general (smallest to largest geographic unit)
3. **Levels:** Typically 1-4 levels, can be more for detailed locations
4. **Consistency:** Same level of detail throughout database preferred
5. **No trailing comma:** Do not end place names with comma

---

## Place Hierarchy Levels

### 4-Level Hierarchy (Most Common)

**Distribution in sample database:**
- 4+ levels: 3,321 places (65.3%)
- 3 levels: 1,061 places (20.9%)
- 2 levels: 139 places (2.7%)
- 1 level: 561 places (11.0%)

### Level Definitions

| Level | Description | US Example | International |
|-------|-------------|------------|---------------|
| 1 | City/Town/Township | Baltimore | London |
| 2 | County/District | Baltimore County | Greater London |
| 3 | State/Province | Maryland | England |
| 4 | Country | United States | United Kingdom |

### Common Patterns

**United States (4 levels):**
```
City, County, State, United States
```

**Canada (4 levels):**
```
City, District, Province, Canada
```

**United Kingdom (4 levels):**
```
City, County, Country, United Kingdom
```

**Other countries (3 levels):**
```
City, Province, Country
```

**Simple (1-2 levels):**
```
Country
State, Country
```

---

## Hierarchy Level Examples

### 1 Level

Single geographic unit (country, state, or standalone location):

```
Ireland
Germany
Pennsylvania
\
1064 S. 10th
```

**Usage:** Countries, states without city, standalone addresses

---

### 2 Levels

Two geographic units:

```
Alabama, United States
Alberta, Canada
1235 E. 12th Ave, Apt. 15
313 Woodlawn Rd.,
```

**Usage:** State + Country, incomplete addresses

---

### 3 Levels

Three geographic units (common for non-US locations):

```
Abbeville, South Carolina, United States
Accomack, Virginia, United States
Adair, Iowa, United States
Adams, Colorado, United States
Adams, Illinois, United States
```

**Usage:** City + State + Country (no county), international locations

---

### 4+ Levels

Standard US format with all levels:

```
Aberdeen, Brown, South Dakota, United States
Abilene, Taylor, Texas, United States
Baltimore, Baltimore, Maryland, United States
Pittsburgh, Allegheny, Pennsylvania, United States
```

**5+ Levels (detailed locations):**
```
Old Iams Cemetery, Trotwood, Montgomery, Ohio, United States
12 Alcazar Ave, Kingston, Ulster, New York, United States
4817 East 17th Street, Denver, Denver, Colorado, United States
```

**Usage:** Full hierarchy including specific buildings, cemeteries, addresses

---

## PlaceTable Fields

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| **PlaceID** | INTEGER | Unique identifier (Primary Key) |
| **Name** | TEXT | Place name in standard format (comma-delimited) |
| **Normalized** | TEXT | Standardized/corrected place name |
| **Reverse** | TEXT | Place name in reverse order for sorting |
| **Abbrev** | TEXT | Abbreviated form (rarely used) |
| **PlaceType** | INTEGER | 0=Standard, 1=Other, 2=Detail place |
| **MasterID** | INTEGER | Reference to parent place (0 if master) |

### Geographic Coordinates

| Field | Type | Description |
|-------|------|-------------|
| **Latitude** | INTEGER | Latitude × 10,000,000 (7 decimal places) |
| **Longitude** | INTEGER | Longitude × 10,000,000 (7 decimal places) |
| **LatLongExact** | INTEGER | 1=Exact coordinates, 0=Approximate |

**Coordinate Storage:**
- Stored as integers (multiply degrees by 10,000,000)
- Example: 39.2904° = 392,904,000
- Precision: 7 decimal places (~1.1 cm accuracy)

**Coordinate Usage:**
- 85.2% of places have coordinates
- Only 1.4% marked as exact (most are approximate)

### External References

| Field | Type | Description |
|-------|------|-------------|
| **fsID** | INTEGER | FamilySearch place ID |
| **anID** | INTEGER | Ancestry.com place ID |

### Other Fields

| Field | Type | Description |
|-------|------|-------------|
| **Note** | TEXT | User notes about the place |
| **UTCModDate** | FLOAT | Last modification date (Julian day) |

---

## Name vs Normalized vs Reverse

### Name Field

**Purpose:** The place name as entered by the user

**Format:** Comma-delimited hierarchy

**Example:**
```
Baltimore, Baltimore, Maryland, United States
```

---

### Normalized Field

**Purpose:** Standardized or corrected place name

**Usage Rate:** 93.6% same as Name, 6.4% different

**When Different:**
- Spelling corrections
- Expanded abbreviations
- Added missing hierarchy levels
- Standardized formats

**Examples:**

| Name | Normalized |
|------|------------|
| Havana, Cuba | Havana, Ciudad de La Habana, Cuba |
| Baltimore, Maryland, United States | Baltimore, Baltimore (city), Maryland, United States |
| East Saint Louis, Saint Clair, Illinois | East Saint Louis, St. Clair, Illinois, United States |
| London, England | London, London, England, United Kingdom |
| Warrenville, Dupage, Illinois | Warrenville, DuPage, Illinois, United States |

**AI Agent Guidance:** Use Normalized when available, fallback to Name

---

### Reverse Field

**Purpose:** Place name in reverse order for alphabetical sorting/indexing

**Format:** Reverse the hierarchy (Country first, City last)

**Examples:**

| Name (Original) | Reverse (For Sorting) |
|----------------|----------------------|
| Palo Alto, Santa Clara, California, United States | United States, California, Santa Clara, Palo Alto |
| Pittsburgh, Allegheny, Pennsylvania, United States | United States, Pennsylvania, Allegheny, Pittsburgh |
| Carlisle, Cumberland, Pennsylvania, United States | United States, Pennsylvania, Cumberland, Carlisle |
| Ireland | Ireland |

**Usage:** Enables sorting by country → state → county → city

**Note:** Single-level places have Reverse = Name

---

## PlaceType Values

### Type 0: Standard Place (4,514 places, 88.8%)

Regular geographic locations following standard hierarchy.

**Examples:**
- City, County, State, Country
- State, Country
- Country

**MasterID:** Always 0 (no parent)

---

### Type 1: Other/Unknown (219 places, 4.3%)

Places that don't fit standard categories.

**Examples:**
- Abbreviated codes (PROVO - Provo Utah)
- Special locations
- Legacy formats

**MasterID:** Always 0

---

### Type 2: Detail Place (349 places, 6.9%)

Specific locations within a master place (buildings, cemeteries, addresses).

**Examples:**
- Old Iams Cemetery (within Trotwood, Montgomery, Ohio)
- 12 Alcazar Ave (within Kingston, Ulster, New York)
- 4817 East 17th Street (within Denver, Colorado)

**MasterID:** Points to parent PlaceID (never 0)

**Note:** Type value inferred from MasterID presence, may not be explicitly set to 2

---

## Master/Detail Relationships

### Concept

**Master Place:** Main geographic location (city, town)
**Detail Place:** Specific location within master (cemetery, building, address)

### MasterID Field

- **MasterID = 0:** This is a master place (no parent)
- **MasterID > 0:** This is a detail place (points to parent PlaceID)

### Statistics

- Master places: 4,680 (92.1%)
- Detail places: 402 (7.9%)

### Examples

| Detail Place | Master Place |
|--------------|--------------|
| Old Iams Cemetery | Trotwood, Montgomery, Ohio, United States |
| 12 Alcazar Ave | Kingston, Ulster, New York, United States |
| 4817 East 17th Street | Denver, Denver, Colorado, United States |
| 876 Downing Street | Denver, Denver, Colorado, United States |
| Ebenezer Cemetery | Spruce Hill, Juniata, Pennsylvania, United States |
| Franklin Cemetery | West Bethlehem Township, Washington, Pennsylvania, United States |
| Woodland Cemetery | Dayton, Montgomery, Ohio, United States |

### Query Master/Detail

```sql
-- Get detail places with their masters
SELECT
    detail.PlaceID,
    detail.Name as DetailPlace,
    master.PlaceID as MasterID,
    master.Name as MasterPlace
FROM PlaceTable detail
JOIN PlaceTable master ON detail.MasterID = master.PlaceID
WHERE detail.MasterID != 0;
```

---

## Parsing Place Names

### Python: Split Hierarchy Levels

```python
def parse_place_name(place_name):
    """Parse comma-delimited place name into hierarchy levels."""
    if not place_name:
        return []

    # Split on comma-space
    levels = place_name.split(', ')

    return {
        'full': place_name,
        'levels': levels,
        'count': len(levels),
        'city': levels[0] if len(levels) >= 1 else None,
        'county': levels[1] if len(levels) >= 2 else None,
        'state': levels[2] if len(levels) >= 3 else None,
        'country': levels[3] if len(levels) >= 4 else None
    }

# Example usage
place = "Baltimore, Baltimore, Maryland, United States"
parsed = parse_place_name(place)

# Output:
# {
#   'full': 'Baltimore, Baltimore, Maryland, United States',
#   'levels': ['Baltimore', 'Baltimore', 'Maryland', 'United States'],
#   'count': 4,
#   'city': 'Baltimore',
#   'county': 'Baltimore',
#   'state': 'Maryland',
#   'country': 'United States'
# }
```

### Python: Get Short Form

```python
def get_place_short(place_name, max_levels=2):
    """Get shortened place name (first N levels)."""
    if not place_name:
        return None

    levels = place_name.split(', ')
    return ', '.join(levels[:max_levels])

# Examples:
# "Baltimore, Baltimore, Maryland, United States" → "Baltimore, Maryland"
# "Pittsburgh, Allegheny, Pennsylvania, United States" → "Pittsburgh, Pennsylvania"
```

### Python: Get Place Level

```python
def get_place_level(place_name, level):
    """
    Get specific hierarchy level.
    level: 0=city, 1=county, 2=state, 3=country
    """
    if not place_name:
        return None

    levels = place_name.split(', ')
    return levels[level] if level < len(levels) else None

# Examples:
place = "Baltimore, Baltimore, Maryland, United States"
get_place_level(place, 0)  # "Baltimore" (city)
get_place_level(place, 2)  # "Maryland" (state)
get_place_level(place, 3)  # "United States" (country)
```

---

## Coordinate Conversion

### Python: Convert Integer Coordinates to Degrees

```python
def convert_coordinates(lat_int, lon_int):
    """Convert integer coordinates to decimal degrees."""
    if not lat_int or not lon_int:
        return None, None

    latitude = lat_int / 10_000_000.0
    longitude = lon_int / 10_000_000.0

    return latitude, longitude

# Example:
lat_int = 392904000
lon_int = -766224000

lat, lon = convert_coordinates(lat_int, lon_int)
# lat = 39.2904° N
# lon = -76.6224° W
```

### SQL: Get Places with Coordinates

```sql
SELECT
    PlaceID,
    Name,
    Latitude / 10000000.0 as LatitudeDeg,
    Longitude / 10000000.0 as LongitudeDeg,
    LatLongExact
FROM PlaceTable
WHERE Latitude IS NOT NULL
  AND Latitude != 0
  AND Longitude IS NOT NULL
  AND Longitude != 0
ORDER BY Name;
```

---

## Validation Rules

### Rule 1: Consistent Hierarchy Levels

**Recommendation:** Use 4-level hierarchy for US places, 3-level for international

**Check:**
```sql
-- Find places with inconsistent hierarchy levels
SELECT
    Name,
    LENGTH(Name) - LENGTH(REPLACE(Name, ',', '')) + 1 as Levels
FROM PlaceTable
WHERE Name LIKE '%United States'
  AND (LENGTH(Name) - LENGTH(REPLACE(Name, ',', '')) + 1) != 4;
```

---

### Rule 2: No Trailing/Leading Spaces

**Issue:** Spaces before/after commas cause inconsistency

**Check:**
```python
def validate_place_format(place_name):
    """Validate place name format."""
    issues = []

    if place_name.startswith(' ') or place_name.endswith(' '):
        issues.append("Leading or trailing whitespace")

    if ',,' in place_name:
        issues.append("Empty hierarchy level (double comma)")

    if ', ' not in place_name and ',' in place_name:
        issues.append("Missing space after comma")

    return issues
```

---

### Rule 3: Normalized Should Exist

**Recommendation:** Populate Normalized field for all places

**Check:**
```sql
SELECT COUNT(*)
FROM PlaceTable
WHERE Name IS NOT NULL
  AND (Normalized IS NULL OR Normalized = '');
```

---

### Rule 4: Coordinates Should Match Geographic Level

**Issue:** Country-level places shouldn't have precise coordinates

**Guidance:**
- City/Town: Can have exact coordinates (LatLongExact=1)
- County/State: Use approximate center coordinates
- Country: Use capital city or geographic center

---

## Common Query Patterns

### Get All Places in a State

```sql
SELECT PlaceID, Name
FROM PlaceTable
WHERE Name LIKE '%Maryland, United States'
ORDER BY Name;
```

### Get All Places in a County

```sql
SELECT PlaceID, Name
FROM PlaceTable
WHERE Name LIKE '%Baltimore, Maryland, United States'
ORDER BY Name;
```

### Get Country-Level Places Only

```sql
SELECT PlaceID, Name
FROM PlaceTable
WHERE Name NOT LIKE '%,%'  -- No commas = single level
ORDER BY Name;
```

### Get Places by Coordinate Proximity

```sql
-- Find places within ~50 miles of Baltimore (39.2904°, -76.6224°)
SELECT
    PlaceID,
    Name,
    Latitude / 10000000.0 as Lat,
    Longitude / 10000000.0 as Lon
FROM PlaceTable
WHERE Latitude BETWEEN 389000000 AND 396000000  -- ±0.7° latitude
  AND Longitude BETWEEN -773000000 AND -759000000  -- ±0.7° longitude
  AND Latitude IS NOT NULL
  AND Latitude != 0;
```

---

## Formatting for Display

### Short Form (City, State)

```python
def format_place_short(place_name):
    """Format place as 'City, State' for US locations."""
    levels = place_name.split(', ')
    if len(levels) >= 4 and levels[3] == 'United States':
        return f"{levels[0]}, {levels[2]}"  # City, State
    elif len(levels) >= 3:
        return f"{levels[0]}, {levels[2]}"  # City, Country
    else:
        return place_name

# "Baltimore, Baltimore, Maryland, United States" → "Baltimore, Maryland"
# "London, London, England, United Kingdom" → "London, England"
```

### Medium Form (City, County, State)

```python
def format_place_medium(place_name):
    """Format place as 'City, County, State'."""
    levels = place_name.split(', ')
    if len(levels) >= 3:
        return ', '.join(levels[:3])
    else:
        return place_name

# "Baltimore, Baltimore, Maryland, United States" → "Baltimore, Baltimore, Maryland"
```

---

## Notes for AI Agents

1. **Prefer Normalized over Name** - Use Normalized field when available for standardized spellings

2. **Parse by comma-space** - Use `, ` (comma-space) as separator, not just comma

3. **Handle variable levels** - Don't assume 4 levels, check actual count

4. **Master/Detail relationship** - Check MasterID to find specific locations within cities

5. **Coordinates are approximate** - Only 1.4% marked exact, use for general location only

6. **Reverse field for sorting** - Use Reverse field when displaying alphabetical place lists

7. **PlaceID=0 means no place** - Check for PlaceID=0 in EventTable (indicates no place recorded)

8. **Geographic display flexibility:**
   - Biography: Use short form (City, State)
   - Timeline: Use medium form (City, County, State)
   - Citations: Use full form (all levels)

9. **Country variations matter:**
   - US: 4 levels typical (City, County, State, Country)
   - UK: 4 levels (City, County, Country, United Kingdom)
   - Others: 3 levels (City, Province, Country)

10. **Detail places add context** - Cemetery names, addresses provide specific context for events

---

## Related Documentation

- **RM11_Schema_Reference.md** - PlaceTable schema
- **RM11_DataDef.yaml** - PlaceTable field definitions
- **RM11_Data_Quality_Rules.md** - Place validation rules

---

## Summary

RootsMagic place names follow a **comma-delimited hierarchical format** with typical structure:

```
City, County, State/Province, Country
```

Key features:
- **65% of places** use 4+ level hierarchy
- **93.6% use Name = Normalized** (minimal corrections needed)
- **85% have coordinates** (mostly approximate)
- **8% are detail places** (cemeteries, addresses within cities)
- **Reverse field** enables country-first sorting

The system balances **flexibility** (1-5+ levels) with **standardization** (recommended 4-level format), making it suitable for both US and international genealogy research.

---

**End of Document**
