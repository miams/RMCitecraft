# RootsMagic Database Schema Reference

Quick reference for RootsMagic 11 database structure.

## Core Tables

### PersonTable
| Field | Type | Description |
|-------|------|-------------|
| PersonID | INTEGER PK | Record Identification Number (RIN) |
| Sex | INTEGER | 0=Male, 1=Female, 2=Unknown |
| ParentID | INTEGER FK | FamilyTable.FamilyID (0 if no parents) |
| SpouseID | INTEGER FK | FamilyTable.FamilyID (0 if no spouse) |
| Living | INTEGER | 0=Deceased, 1=Living |
| Bookmark | INTEGER | 0=Not bookmarked, 1=Bookmarked |
| Note | TEXT | Person note (supports HTML formatting) |

### NameTable
| Field | Type | Description |
|-------|------|-------------|
| NameID | INTEGER PK | Name record ID |
| OwnerID | INTEGER FK | PersonTable.PersonID |
| Surname | TEXT | Surname (RMNOCASE collation) |
| Given | TEXT | Given name (RMNOCASE collation) |
| Prefix | TEXT | Name prefix (Dr., Rev., etc.) |
| Suffix | TEXT | Name suffix (Jr., Sr., III, etc.) |
| Nickname | TEXT | Nickname |
| NameType | INTEGER | 0=Null, 1=AKA, 2=Birth, 3=Immigrant, 4=Maiden, 5=Married, 6=Nickname, 7=Other |
| IsPrimary | INTEGER | 1=Primary name, 0=Alternate |
| BirthYear | INTEGER | Extracted from birth event |
| DeathYear | INTEGER | Extracted from death event |

### FamilyTable
| Field | Type | Description |
|-------|------|-------------|
| FamilyID | INTEGER PK | Family record ID |
| FatherID | INTEGER FK | PersonTable.PersonID |
| MotherID | INTEGER FK | PersonTable.PersonID |
| ChildID | INTEGER FK | Last active child in pedigree view |
| Proof | INTEGER | 0=Blank, 1=Proven, 2=Disproven, 3=Disputed |
| Note | TEXT | Family note (supports HTML formatting) |

### ChildTable
| Field | Type | Description |
|-------|------|-------------|
| RecID | INTEGER PK | Record ID |
| ChildID | INTEGER FK | PersonTable.PersonID |
| FamilyID | INTEGER FK | FamilyTable.FamilyID |
| RelFather | INTEGER | 0=Birth, 1=Adopted, 2=Foster, 3=Guardianship, etc. |
| RelMother | INTEGER | Same values as RelFather |
| ChildOrder | INTEGER | Sort order in family |

### EventTable
| Field | Type | Description |
|-------|------|-------------|
| EventID | INTEGER PK | Event record ID |
| EventType | INTEGER FK | FactTypeTable.FactTypeID |
| OwnerType | INTEGER | 0=Person, 1=Family |
| OwnerID | INTEGER FK | PersonID or FamilyID based on OwnerType |
| PlaceID | INTEGER FK | PlaceTable.PlaceID (0 if no place) |
| Date | TEXT | Encoded date string |
| SortDate | BIGINT | Sortable integer representation |
| Details | TEXT | Event description field |
| Note | TEXT | Event note (supports HTML formatting) |

**Key Event Types:**
- 1 = Birth
- 2 = Death
- 18 = Census
- 300 = Marriage (OwnerType=1, OwnerID=FamilyID)

### FactTypeTable
| Field | Type | Description |
|-------|------|-------------|
| FactTypeID | INTEGER PK | <1000=Built-in, >=1000=User-defined |
| OwnerType | INTEGER | 0=Individual, 1=Family |
| Name | TEXT | Fact type name (Birth, Death, etc.) |
| Abbrev | TEXT | Abbreviation |
| GedcomTag | TEXT | GEDCOM tag (BIRT, DEAT, etc.) |
| UseValue | INTEGER | 1=Has description field |
| UseDate | INTEGER | 1=Has date field |
| UsePlace | INTEGER | 1=Has place field |

### WitnessTable
| Field | Type | Description |
|-------|------|-------------|
| WitnessID | INTEGER PK | Witness record ID |
| EventID | INTEGER FK | EventTable.EventID |
| PersonID | INTEGER FK | PersonTable.PersonID (0 if not in database) |
| Role | INTEGER FK | RoleTable.RoleID |
| Given | TEXT | Given name (if PersonID=0) |
| Surname | TEXT | Surname (if PersonID=0) |

**Critical:** Census events are often shared via WitnessTable. Always check both EventTable (owned) and WitnessTable (shared) when finding census records.

## Source and Citation Tables

### SourceTable
| Field | Type | Description |
|-------|------|-------------|
| SourceID | INTEGER PK | Source record ID |
| Name | TEXT | Source name (RMNOCASE collation) |
| Comments | TEXT | Source comments (GPS location) |
| TemplateID | INTEGER FK | 0=Free-form, else SourceTemplateTable.TemplateID |
| Fields | BLOB | XML with field values (for free-form: Footnote, ShortFootnote, Bibliography) |

**Free-form sources (TemplateID=0):**
- Footnote, ShortFootnote, Bibliography stored in `SourceTable.Fields` BLOB (XML)
- CitationTable TEXT fields are empty for free-form sources

### CitationTable
| Field | Type | Description |
|-------|------|-------------|
| CitationID | INTEGER PK | Citation record ID |
| SourceID | INTEGER FK | SourceTable.SourceID |
| Comments | TEXT | Detail comment |
| CitationName | TEXT | Citation name (RMNOCASE collation) |
| Footnote | TEXT | Custom footnote (template sources only) |
| ShortFootnote | TEXT | Custom short footnote (template sources only) |
| Bibliography | TEXT | Custom bibliography (template sources only) |
| Fields | BLOB | XML with citation detail fields |

### CitationLinkTable
| Field | Type | Description |
|-------|------|-------------|
| LinkID | INTEGER PK | Link record ID |
| CitationID | INTEGER FK | CitationTable.CitationID |
| OwnerType | INTEGER | 0=Person, 1=Family, 2=Event, 6=Task, 7=Name |
| OwnerID | INTEGER FK | ID based on OwnerType |
| Quality | TEXT | 3-char quality code (PSI~DNO~X~) |

## Place and Media Tables

### PlaceTable
| Field | Type | Description |
|-------|------|-------------|
| PlaceID | INTEGER PK | Place record ID |
| PlaceType | INTEGER | 0=Place, 1=LDS Temple, 2=Place Details |
| Name | TEXT | Comma-delimited place hierarchy |
| Normalized | TEXT | Standardized place name |
| Reverse | TEXT | Reversed comma-delimited (for indexing) |
| Latitude | INTEGER | Latitude * 1e7 |
| Longitude | INTEGER | Longitude * 1e7 |

### MultimediaTable
| Field | Type | Description |
|-------|------|-------------|
| MediaID | INTEGER PK | Media record ID |
| MediaType | INTEGER | 1=Image, 2=File, 3=Sound, 4=Video |
| MediaPath | TEXT | Relative file path |
| MediaFile | TEXT | File name |
| Caption | TEXT | Caption |
| Description | TEXT | Description |

**MediaPath symbols:**
- `?` = Media Folder (RM_MEDIA_ROOT_DIRECTORY)
- `~` = User's home directory
- `*` = Folder containing RM database

### MediaLinkTable
| Field | Type | Description |
|-------|------|-------------|
| LinkID | INTEGER PK | Link record ID |
| MediaID | INTEGER FK | MultimediaTable.MediaID |
| OwnerType | INTEGER | 0=Person, 1=Family, 2=Event, 3=Source |
| OwnerID | INTEGER FK | ID based on OwnerType |
| IsPrimary | INTEGER | 1=Primary photo |
| SortOrder | INTEGER | Display order |

## Key Database Patterns

### OwnerType Values
| Value | Entity Type |
|-------|-------------|
| 0 | Person |
| 1 | Family |
| 2 | Event |
| 3 | Source |
| 4 | Citation |
| 5 | Place |
| 6 | Task |
| 7 | Name |

### Date Format
RootsMagic dates are 24-character position-coded strings:
- Format: `D.+YYYYMMDD..+00000000..`
- Year extraction: `date_string[3:7]`
- Example: `D.+18640615..+00000000..` = June 15, 1864

### RMNOCASE Collation
- Required for: Surname, Given, Name, CitationName, and other text fields
- Must load ICU extension before querying
- Use `connect_rmtree()` function, never raw `sqlite3.connect()`

### BLOB Fields
- SourceTable.Fields - XML with field values
- CitationTable.Fields - XML with citation details
- All BLOBs are UTF-8 encoded with BOM (EFBBBF)
- Read with: `CAST(Fields AS TEXT)`
- Write with: `.encode('utf-8')`

## Database Conventions

1. **Integer columns:** Use 0, not NULL (RootsMagic convention)
2. **SortDate:** BIGINT type, not INTEGER
3. **UTCModDate:** Float, Julian day format
4. **IsPrimary:** 1=Yes, 0=No (not NULL)
5. **Relative paths:** Always store relative, never absolute paths
6. **Case sensitivity:** Use RMNOCASE collation for name comparisons

## Related Documentation

- `query-cookbook.md` - Common SQL patterns
- `fact-types.md` - Complete event type codes
- `date-encoding.md` - Date format specification
