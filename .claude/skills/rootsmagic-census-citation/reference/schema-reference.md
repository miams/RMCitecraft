# RootsMagic Schema Reference for Census Citations

Tables and columns you will touch when adding a census record. Verified
against RootsMagic 9 .rmtree (SQLite) format.

## Connect

```python
from rmcitecraft.database.connection import connect_rmtree
conn = connect_rmtree('data/Iiams.rmtree', read_only=False)
cur = conn.cursor()
# ... work ...
conn.commit()
conn.close()
```

Never use bare `sqlite3.connect()` — RMNOCASE collation will fail.
Never use the `sqlite3` CLI — same reason.

---

## Owner Type codes (the bug-prone one)

`MediaLinkTable.OwnerType` and `CitationLinkTable.OwnerType` share this scheme:

| OwnerType | Owner Table | Owner Column |
|-----------|-------------|--------------|
| 0 | PersonTable | PersonID |
| 1 | FamilyTable | FamilyID |
| 2 | EventTable | EventID |
| 3 | SourceTable | SourceID |
| 4 | CitationTable | CitationID |
| 5 | PlaceTable | PlaceID |

To **verify against a specific database** (recommended before any write batch),
use `scripts/verify_owner_types.py <dbpath>` which checks that the OwnerIDs at
each OwnerType actually exist in the expected table.

Why this is bug-prone: my first attempt at this skill guessed the mapping from
the distribution of OwnerTypes (almost-equal counts at 2/3/4 for 1940 census
images) and assumed 2=Source, 3=Citation, 4=Event. The truth is 2=Event,
3=Source, 4=Citation. The SQL succeeds either way — there's no foreign-key
constraint — but RootsMagic's UI silently fails to display the link.

---

## SourceTable

```
CREATE TABLE SourceTable (
  SourceID    INTEGER PRIMARY KEY,
  Name        TEXT,           -- "Fed Census: 1940, NM, Santa Fe [ED 25-20A, sheet 12-A, line 5] Iams, John Willis"
  RefNumber   TEXT,           -- '' for census
  ActualText  TEXT,           -- '' for census
  Comments    TEXT,           -- '' for census (use for Source-level GPS prose if desired)
  IsPrivate   INTEGER,        -- 0
  TemplateID  INTEGER,        -- 0 for free-form (all census use 0 in this project)
  Fields      BLOB,           -- XML; see "Fields BLOB encoding" below
  UTCModDate  FLOAT           -- julianday('now') - 2415018.5
)
```

### Source naming convention (project-specific but useful)

`Fed Census: <YEAR>, <State>, <County> [<location key>] <Surname>, <Given>`

Where `<location key>` is the smallest distinct locator for the year:

- 1790-1840: `[page <N>]` or `[stamp <N>]`
- 1850-1870: `[sheet <N>, line <N>]` or `[page <N>, line <N>]` for 1860
- 1880: `[ED <state-ed>, page <N>, line <N>]` or `[ED <state-ed>, sheet <N>, line <N>]`
- 1900-1940: `[ED <state-ed>, sheet <N>-<A>, line <N>]`
- 1950 standard: `[ED <state-ed>, sheet <N>, line <N>]` or `[ED <state-ed>, stamp <N>]`
- 1950 experimental: `[ED <state-ed>, stamp <N>]`

### Fields BLOB encoding

Stored as UTF-8 bytes representing this XML:

```xml
<Root><Fields>
  <Field><Name>Footnote</Name><Value>...prose with &amp;quot; entities for " and &amp;lt;i&amp;gt;...&amp;lt;/i&amp;gt; for italics...</Value></Field>
  <Field><Name>ShortFootnote</Name><Value>...</Value></Field>
  <Field><Name>Bibliography</Name><Value>...</Value></Field>
</Fields></Root>
```

(In the actual stored bytes there is only ONE level of entity-encoding —
`&quot;` and `&lt;i&gt;` literally. The double-encoding in the snippet above is
just because I had to escape it again to put it in this markdown file.)

**Critical rule:** never use SQL string functions on this BLOB. Read with
`CAST(Fields AS TEXT)`, mutate in Python, write back with `.encode('utf-8')`.

### Reading Fields

```python
cur.execute("SELECT CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?", (sid,))
xml_text = cur.fetchone()[0]
# Entities stay encoded; parse with ET if you need structured access:
import xml.etree.ElementTree as ET
root = ET.fromstring(xml_text)
fields = {f.find('Name').text: f.find('Value').text for f in root.findall('Fields/Field')}
```

### Writing Fields

```python
xml = '<Root><Fields>' + ''.join(
    f'<Field><Name>{n}</Name><Value>{v}</Value></Field>' for n, v in fields.items()
) + '</Fields></Root>'
cur.execute("UPDATE SourceTable SET Fields = ? WHERE SourceID = ?", (xml.encode('utf-8'), sid))
```

The `<Value>` content should already contain `&quot;` and `&lt;...&gt;` —
not raw `"` or `<`. The XML parser would otherwise treat them as markup.

---

## CitationTable

```
CREATE TABLE CitationTable (
  CitationID    INTEGER PRIMARY KEY,
  SourceID      INTEGER,           -- FK to SourceTable
  Comments      TEXT,              -- ''
  ActualText    TEXT,              -- ''
  RefNumber     TEXT,              -- ''
  Footnote      TEXT,              -- '' (templated sources drive these from Fields)
  ShortFootnote TEXT,              -- ''
  Bibliography  TEXT,              -- ''
  Fields        BLOB,              -- minimal: <Root><Fields><Field><Name>Page</Name><Value></Value></Field></Fields></Root>
  UTCModDate    FLOAT,
  CitationName  TEXT               -- ''
)
```

For census: the Footnote / ShortFootnote / Bibliography live on the **Source**
Fields BLOB, not the Citation. The Citation row is mostly a join row. Its only
content is the optional `Page` field (left empty for census because the page
info is already in the Source name and Footnote).

---

## CitationLinkTable

Links a Citation to whatever cites it (typically an Event).

```
CREATE TABLE CitationLinkTable (
  LinkID      INTEGER PRIMARY KEY,
  CitationID  INTEGER,           -- FK
  OwnerType   INTEGER,           -- 2 for Event (most common for census)
  OwnerID     INTEGER,           -- EventID
  SortOrder   INTEGER,           -- 0
  Quality     TEXT,              -- '~~~' (three tildes = default)
  IsPrivate   INTEGER,           -- 0
  Flags       INTEGER,           -- 0
  UTCModDate  FLOAT
)
```

`Quality` is three single-character ratings concatenated: Source / Information /
Evidence. Tilde `~` is "default / unrated". You can use letters like `*` (best),
`!` (good), `+` (fair), `-` (poor), `~` (default) per RM conventions, but the
project defaults to `'~~~'`.

To attach the **same citation** to multiple events (e.g. linking it to both
head-of-household and spouse events when you chose duplicate events instead of
witnesses), just insert multiple rows with the same CitationID and different
OwnerIDs. But — prefer the witness pattern; see WitnessTable below.

---

## EventTable

```
CREATE TABLE EventTable (
  EventID    INTEGER PRIMARY KEY,
  EventType  INTEGER,             -- 18 = Census; see FactTypeTable for the catalog
  OwnerType  INTEGER,             -- 0 = Person; 1 = Family
  OwnerID    INTEGER,             -- PersonID or FamilyID
  FamilyID   INTEGER,             -- 0 for individual events
  PlaceID    INTEGER,             -- FK to PlaceTable
  SiteID     INTEGER,             -- 0
  Date       TEXT,                -- 'D.+YYYYMMDD..+YYYYMMDD..' (start..end)
  SortDate   BIGINT,              -- precomputed sort key; see SortDate constants below
  IsPrimary  INTEGER,             -- 0
  IsPrivate  INTEGER,             -- 0
  Proof      INTEGER,             -- 0
  Status     INTEGER,             -- 0
  Sentence   TEXT,                -- '' (RM auto-generates if empty)
  Details    TEXT,                -- '' (place details like ED, township)
  Note       TEXT,                -- '' (free-form notes)
  UTCModDate FLOAT
)
```

### Common EventType codes

| ID | Name |
|----|------|
| 1 | Birth |
| 2 | Death |
| 4 | Burial |
| 18 | Census |
| 26 | Occupation |
| 29 | Residence |
| 300 | Marriage |

For the full list: `SELECT FactTypeID, Name FROM FactTypeTable ORDER BY FactTypeID;`

### Date format

`D.+YYYYMMDD..+YYYYMMDD..` where:
- `D` = exact date marker (use `DA` for approximate / "about")
- First `YYYYMMDD` = start date (`00` for unknown month/day)
- `..` = literal separator
- Second `YYYYMMDD` = end date for ranges (`00000000` for non-range)
- Trailing `..` = literal

| Date string                  | Meaning                  |
|------------------------------|--------------------------|
| `D.+19400000..+00000000..`   | 1940 (unknown month/day) |
| `D.+19400401..+00000000..`   | 1 April 1940 (exact)     |
| `D.+19500410..+00000000..`   | 10 April 1950            |
| `DA+19850527..+00000000..`   | About 27 May 1985        |

### SortDate constants for common census years

These are stable across the database — reuse to avoid recomputation:

| Date string                | SortDate              |
|----------------------------|-----------------------|
| `D.+19400000..+00000000..` | 6721622461029285900   |
| `D.+19400401..+00000000..` | 6721761010561228812   |
| `D.+19500000..+00000000..` | 6727251960563499020   |
| `D.+19500401..+00000000..` | 6727393247807668236   |
| `D.+19500410..+00000000..` | 6727398195609993228   |
| `D.+19500514..+00000000..` | 6727435579005337612   |

If you need a SortDate not listed, query the existing data:
```sql
SELECT DISTINCT Date, SortDate FROM EventTable WHERE Date = '<your date>' LIMIT 1;
```

---

## WitnessTable (the shared-fact pattern)

```
CREATE TABLE WitnessTable (
  WitnessID     INTEGER PRIMARY KEY,
  EventID       INTEGER,         -- FK to the event the witness participates in
  PersonID      INTEGER,         -- the witness
  WitnessOrder  INTEGER,         -- 0 (sort order)
  Role          INTEGER,         -- FK to RoleTable (or 0 for default "Witness")
  Sentence      TEXT,            -- '' (RM auto-generates from Role)
  Note          TEXT,            -- ''
  Given         TEXT,            -- '' (override name, rarely used)
  Surname       TEXT,            -- ''
  Prefix        TEXT,            -- ''
  Suffix        TEXT,            -- ''
  UTCModDate    FLOAT
)
```

### Why use it for census

A census record is a household snapshot. The standard RM pattern:
- Create **one** Census event, owned by the head of household (`OwnerType=0`, `OwnerID=<HoH RIN>`).
- For each other household member who is also in the database, insert a
  `WitnessTable` row with the appropriate Role.
- Citation, image, and event details propagate to each witness's record
  automatically — they appear under "events I appeared in" / shared facts.

This avoids:
- Duplicate events on each member with parallel citations to maintain.
- Drift if you later correct one but forget the others.
- Bloat in the EventTable.

### Role IDs for census events (EventType 18)

Verify against the actual database with:
```sql
SELECT RoleID, RoleName FROM RoleTable WHERE EventType = 18 ORDER BY RoleID;
```

Common values seen in this project:

| RoleID | RoleName  |
|--------|-----------|
| 63 | son |
| 65 | daughter |
| 66 | wife |
| 19 | (verify in your DB) |
| 64 | (verify in your DB) |
| 68 | (verify in your DB) |
| 69 | (verify in your DB) |
| 70 | (verify in your DB) |
| 72 | (verify in your DB) |
| 73 | (verify in your DB) |
| 74 | (verify in your DB) |
| 76 | (verify in your DB) |
| 77 | (verify in your DB) |
| 78 | (verify in your DB) |
| 92 | (verify in your DB) |

Each Role row has a Sentence template that RM uses to generate the displayed
narrative ("X appeared as the daughter of Y in the census of Z").

---

## RoleTable

```
CREATE TABLE RoleTable (
  RoleID     INTEGER PRIMARY KEY,
  RoleName   TEXT,             -- 'wife', 'son', 'daughter', etc.
  EventType  INTEGER,          -- FK to FactTypeTable - which event types use this role
  RoleType   INTEGER,          -- 0
  Sentence   TEXT,             -- '[ThisPerson:First] appeared as the [ThisPerson:Role] of [person] in the census of< [Date:Plain]>< [PlaceDetails]>< [Place:First]>.'
  UTCModDate FLOAT
)
```

You typically don't create new roles for census work — use the existing
catalog. Inspect with:

```sql
SELECT RoleID, RoleName, Sentence FROM RoleTable WHERE EventType = 18 ORDER BY RoleID;
```

---

## MultimediaTable

```
CREATE TABLE MultimediaTable (
  MediaID      INTEGER PRIMARY KEY,
  MediaType    INTEGER,           -- 1 = image
  MediaPath    TEXT,              -- '?\Records - Census\1940 Federal' (Windows-style with ?\ root)
  MediaFile    TEXT,              -- '1940, New Mexico, Santa Fe - Iams, John Willis.jpg'
  URL          TEXT,              -- the FamilySearch ARK URL
  Thumbnail    BLOB,              -- NULL (RM auto-generates)
  Caption      TEXT,              -- 'Census: 1940 Fed Census - Santa Fe, NM'
  RefNumber    TEXT,              -- ''
  Date         TEXT,              -- census-day date format: 'D.+19400401..+00000000..'
  SortDate     BIGINT,
  Description  TEXT,              -- ''
  UTCModDate   FLOAT
)
```

### MediaPath convention

`?\` is RootsMagic's marker for "relative to the configured Media Root directory"
(`RM_MEDIA_ROOT_DIRECTORY` env var; for this project: `~/Genealogy/RootsMagic/Files/`).

The literal stored value uses **backslashes** (Windows-style), regardless of
OS:
```
?\Records - Census\1940 Federal
?\Records - Census\1950 Federal
?\Records - Military\WW II - Draft Registration\NM
```

Resolved at runtime to: `~/Genealogy/RootsMagic/Files/Records - Census/1940 Federal/`.

### MediaFile naming

Census images follow this pattern across all years:

```
<YEAR>, <State>, <County> - <Surname>, <Given Name>.jpg
```

Examples:
- `1940, New Mexico, Santa Fe - Iams, John Willis.jpg`
- `1950, Ohio, Franklin - Iams, John Willis.jpg`
- `1920, New Mexico, Luna - Iams, Perry Elmer.jpg`

For other media types: `<Surname>, <Given Name> (<birth-death>).jpg` is the
pattern used for portraits / draft cards / obituaries — for census, the
year/state/county prefix is what differs.

### Caption convention

`Census: <YEAR> Fed Census - <County>, <ST>` (state abbreviation, no period).
- `Census: 1940 Fed Census - Santa Fe, NM`
- `Census: 1950 Fed Census - Franklin, OH`

---

## MediaLinkTable

```
CREATE TABLE MediaLinkTable (
  LinkID      INTEGER PRIMARY KEY,
  MediaID     INTEGER,
  OwnerType   INTEGER,           -- 2=Event, 3=Source, 4=Citation (NOT what you might guess; see top)
  OwnerID     INTEGER,
  IsPrimary   INTEGER,           -- 0
  Include1    INTEGER,           -- NULL/0; flags for which reports include the image
  Include2    INTEGER,           -- NULL/0
  Include3    INTEGER,           -- NULL/0
  Include4    INTEGER,           -- NULL/0
  SortOrder   INTEGER,           -- 0
  RectLeft    INTEGER,           -- NULL (no photo tagging on census images)
  RectTop     INTEGER,           -- NULL
  RectRight   INTEGER,           -- NULL
  RectBottom  INTEGER,           -- NULL
  Comments    TEXT,              -- ''
  UTCModDate  FLOAT
)
```

### For a census image, create **three** rows

```python
for owner_type, owner_id in [
    (2, event_id),     # image on event
    (3, source_id),    # image on source
    (4, citation_id),  # image on citation
]:
    cur.execute(
        "INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID, IsPrimary, SortOrder, "
        "RectLeft, RectTop, RectRight, RectBottom, Comments, UTCModDate) "
        "VALUES (?, ?, ?, 0, 0, NULL, NULL, NULL, NULL, '', julianday('now') - 2415018.5)",
        (media_id, owner_type, owner_id)
    )
```

All three are needed for the image to appear correctly in the RM UI under each
record type. Missing the Source link means the image is invisible on the
source's Media tab; missing the Event link means it's invisible on the event's
Media tab.

---

## PlaceTable (lookup, not insertion)

```
CREATE TABLE PlaceTable (
  PlaceID  INTEGER PRIMARY KEY,
  Name     TEXT,
  ...
)
```

Census places typically already exist — look them up by exact name:

```python
cur.execute("SELECT PlaceID FROM PlaceTable WHERE Name = ?", (full_place_name,))
```

Where `full_place_name` is the canonical comma-separated form:
- `Columbus, Franklin, Ohio, United States`
- `Santa Fe, Santa Fe, New Mexico, United States`

If the place doesn't exist, that's a separate decision — usually the user
should create it in RM's place manager so it gets normalized. Don't auto-create
PlaceTable rows from this skill.

---

## Pre-write verification queries

Run these before any insert batch:

```python
# 1) Person exists
cur.execute("SELECT 1 FROM PersonTable WHERE PersonID = ?", (rin,))
assert cur.fetchone(), f"RIN {rin} not found"

# 2) Place matches expected name
cur.execute("SELECT 1 FROM PlaceTable WHERE PlaceID = ? AND Name = ?", (place_id, place_name))
assert cur.fetchone(), f"PlaceID {place_id} name mismatch"

# 3) No duplicate event
cur.execute(
    "SELECT EventID FROM EventTable WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 18 AND Date LIKE ?",
    (rin, f"D.+{year}%")
)
assert not cur.fetchone(), f"Census event for {year} already exists on RIN {rin}"

# 4) No duplicate source name
cur.execute("SELECT 1 FROM SourceTable WHERE Name = ?", (source_name,))
assert not cur.fetchone(), f"Source already exists: {source_name}"

# 5) No duplicate witness
cur.execute("SELECT 1 FROM WitnessTable WHERE EventID = ? AND PersonID = ?", (event_id, witness_rin))
assert not cur.fetchone(), f"{witness_rin} already a witness on event {event_id}"
```

---

## Verification queries (after commit)

```python
# Owning person's events with attached source names
cur.execute("""
    SELECT e.EventID, ft.Name, e.Date, pl.Name AS Place,
           (SELECT s.Name FROM CitationLinkTable cl
            JOIN CitationTable c ON c.CitationID = cl.CitationID
            JOIN SourceTable s ON s.SourceID = c.SourceID
            WHERE cl.OwnerType = 2 AND cl.OwnerID = e.EventID LIMIT 1) AS Source
    FROM EventTable e
    LEFT JOIN FactTypeTable ft ON ft.FactTypeID = e.EventType
    LEFT JOIN PlaceTable pl ON pl.PlaceID = e.PlaceID
    WHERE e.OwnerID = ? AND e.OwnerType = 0
    ORDER BY e.SortDate
""", (rin,))

# Witness's view (owned + witnessed)
cur.execute("""
    SELECT 'owned' AS src, e.EventID, ft.Name, e.Date, pl.Name FROM EventTable e
    LEFT JOIN FactTypeTable ft ON ft.FactTypeID = e.EventType
    LEFT JOIN PlaceTable pl ON pl.PlaceID = e.PlaceID
    WHERE e.OwnerID = ? AND e.OwnerType = 0
    UNION ALL
    SELECT 'witness(' || r.RoleName || ')', e.EventID, ft.Name, e.Date, pl.Name
    FROM WitnessTable w
    JOIN EventTable e ON e.EventID = w.EventID
    LEFT JOIN FactTypeTable ft ON ft.FactTypeID = e.EventType
    LEFT JOIN PlaceTable pl ON pl.PlaceID = e.PlaceID
    LEFT JOIN RoleTable r ON r.RoleID = w.Role
    WHERE w.PersonID = ?
""", (witness_rin, witness_rin))

# Media link integrity
cur.execute("""
    SELECT OwnerType, OwnerID,
           CASE OwnerType WHEN 2 THEN 'Event' WHEN 3 THEN 'Source' WHEN 4 THEN 'Citation' END AS Expected
    FROM MediaLinkTable WHERE MediaID = ?
""", (media_id,))
```
