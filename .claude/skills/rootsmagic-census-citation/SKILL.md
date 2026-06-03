---
name: rootsmagic-census-citation
description: >
  Add a fully-cited U.S. Federal Census record to a RootsMagic database from a
  FamilySearch ARK URL. Creates the Source (with Evidence Explained Footnote /
  ShortFootnote / Bibliography in the Fields BLOB), Citation, Census Event,
  spouse/child Witnesses with proper Roles, downloads the high-resolution image
  via Chrome CDP, files it under the project's media tree, and links it to
  Source + Event + Citation with the correct OwnerType. Use whenever a user
  hands you a FamilySearch census ARK, asks to "add a census source", "create
  a census citation", "attach a census image", or to transcribe a household
  into RootsMagic from FamilySearch. Covers 1790-1950 including the 1950
  experimental sample format.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(uv:*, python3:*, mkdir:*, cp:*, ls:*, curl:*)
---

# RootsMagic Census Citation Skill

End-to-end workflow for turning a FamilySearch ARK URL into a fully-attached,
Evidence-Explained-compliant census record in a RootsMagic `.rmtree` database.

Includes the source, the citation, the census event, spouse/child witness rows,
the downloaded high-resolution image filed in the correct media directory, and
every required link row — all in a single rollback-safe transaction.

---

## Read first: the OwnerType cheat sheet

`MediaLinkTable.OwnerType` and `CitationLinkTable.OwnerType` use this integer
code, and it is easy to invert if you guess from the count distribution.
**Always validate before writing** — see `reference/pitfalls.md` for the bug story.

| Code | Owner table       | Owner column |
|------|-------------------|--------------|
| 0    | PersonTable       | PersonID     |
| 1    | FamilyTable       | FamilyID     |
| **2** | **EventTable**   | **EventID**  |
| **3** | **SourceTable**  | **SourceID** |
| **4** | **CitationTable** | **CitationID** |
| 5    | PlaceTable        | PlaceID      |

Wrong OwnerType silently orphans the link in the RM UI — the SQL row exists
but the image / citation never appears under the intended record.
Run `scripts/verify_owner_types.py <dbpath>` to confirm the mapping against
the live database before any write.

---

## Database safety rules (non-negotiable)

1. **Use `connect_rmtree()`** — never raw `sqlite3.connect()`. The ICU
   extension must be loaded for RMNOCASE collation, and the helper handles it.
2. **Default to read-only.** Pass `read_only=False` only when actually writing.
3. **Back up before every write batch.** A timestamped copy in `backup/` is
   cheap insurance: `cp data/Iiams.rmtree backup/Iiams.rmtree.backup-$(date +%Y%m%d-%H%M%S)-<purpose>`.
4. **Wrap all inserts in a single transaction.** On any error: `rollback()`.
5. **Get user approval before writes.** Read the project's CLAUDE.md — it
   reiterates this. Show the user the exact citation strings and the list of
   records that will be created before pulling the trigger.
6. **Never use `sqlite3` CLI** on `.rmtree` files. It cannot load the ICU
   extension and will fail on every query that touches a RMNOCASE column.
7. **Never use SQL string functions** (`REPLACE`, `SUBSTR`, etc.) on `Fields`
   BLOB columns — they corrupt the data type. Decode in Python, mutate, re-encode.

---

## The standard workflow (8 steps)

For a typical "user gives you a FamilySearch ARK, you add the census" task:

```
1. Identify the RIN          → Search by name, narrow with birth/place, confirm
2. Inspect existing data     → Does the event exist? Are spouse/children in DB?
3. Pick the format template  → Find a recent same-year source for the same census-type
4. Fetch FamilySearch data   → Chrome CDP, get County / ED / sheet / line / household
5. Download the image        → Chrome CDP at scale?width=6000
6. Plan & show to user       → Print exact Footnote/ShortFootnote/Bibliography and approve
7. Write in one transaction  → Source, Citation, Event (if needed), Witnesses, Media, 3 MediaLinks
8. Verify reads back clean   → Citation appears on event; image visible from Source AND Event
```

Skip step 3 only if you already know the template; skip step 2 only if the user
has explicitly already created the event. Never skip 6.

### Step 1 — Identify the RIN

The article / user message may give you a name, initials, or a partial date.
Combine searches; don't assume the surname spelling matches the database.
This project tracks variants: **Iiams, Ijams, Iams, Imes, Iames, Ijames, Iiames**.

```sql
SELECT p.PersonID AS RIN, n.Given, n.Surname,
       (SELECT e.Date FROM EventTable e WHERE e.OwnerID = p.PersonID AND e.EventType = 1) AS Birth,
       (SELECT pl.Name FROM EventTable e LEFT JOIN PlaceTable pl ON pl.PlaceID = e.PlaceID
        WHERE e.OwnerID = p.PersonID AND e.EventType = 1) AS BirthPlace
FROM PersonTable p
JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
WHERE n.Surname LIKE '%Iams%' AND n.Given LIKE 'J%'
ORDER BY Birth;
```

When the lead is something distinctive (a profession, a disability, a place),
also search `PersonTable.Note` and `EventTable.Note` / `EventTable.Details` —
that field often holds the smoking-gun (e.g. "blind per WWII draft card").

### Step 2 — Inspect existing data

Before creating an event, check whether one is already there:

```sql
SELECT EventID, Date, PlaceID FROM EventTable
WHERE OwnerID = <RIN> AND OwnerType = 0 AND EventType = 18 AND Date LIKE 'D.+<YEAR>%';
```

If the event exists, reuse its EventID and skip the `INSERT INTO EventTable`.

Also check the spouse: is the at-census spouse already a person in the database?
Are they alive on the census date? If yes, plan to add them as a Witness (role 66
= wife, role <see RoleTable> for husband) on this event rather than creating a
duplicate event on their record.

### Step 3 — Pick the format template

Find an existing same-year same-format source and read its `Fields` BLOB:

```python
cur.execute("""
  SELECT SourceID, Name, CAST(Fields AS TEXT)
  FROM SourceTable
  WHERE Name LIKE 'Fed Census: <YEAR>%' AND TemplateID = 0
  ORDER BY SourceID DESC LIMIT 3
""")
```

Match the prose of the existing Footnote / ShortFootnote / Bibliography exactly —
only the data values change. See `reference/citation-formats.md` for the full
Evidence-Explained templates per census year.

### Step 4 — Fetch FamilySearch data

Use the existing Chrome CDP instance at `http://localhost:9222`. Never launch
a new browser — sessions are authenticated in the user's CDP profile.

Script: `scripts/fetch_familysearch_record.py <ARK_URL>` — prints the indexed
fields (person name, age, birthplace, ED, sheet, line, household) and the
image ARK (`3:1:...`). When the field you need is empty in the index
(common with the 1950 experimental format which leaves Supervisor District
blank), you'll need to read it off the image — ask the user, don't fabricate.

### Step 5 — Download the image

Script: `scripts/download_fs_image.py <IMAGE_TH_ID> <OUT_PATH>` —
downloads at `scale?width=6000` (~2.5 MB typical, full readable resolution).
For higher zoom use `width=12000`.

**Image path convention** (project-specific, do not deviate):
- Directory: `~/Genealogy/RootsMagic/Files/Records - Census/<YEAR> Federal/`
- Filename: `<YEAR>, <State>, <County> - <Surname>, <Given Name>.jpg`
- DB path: `?\Records - Census\<YEAR> Federal` (RM Windows-style with `?\` root marker, backslashes)
- DB filename: same as filesystem
- Caption: `Census: <YEAR> Fed Census - <County>, <ST>`

Example: `1940, New Mexico, Santa Fe - Iams, John Willis.jpg`

### Step 6 — Plan & show to user

Before any write, print to the user:
- The proposed Source.Name
- The full Footnote, ShortFootnote, Bibliography strings (unescaped — easier to proofread)
- The list of records that will be created (Source / Citation / Event-or-reuse /
  Witness rows by name / Media / 3 MediaLinks)
- Any data discrepancies between the FS record and the existing RM person
  (age, birthplace) so the user can sanity-check the identification

Ask explicit permission. Use AskUserQuestion with concrete options, not a free-text "shall I proceed?".

### Step 7 — Write in one transaction

Use `scripts/add_census_citation.py` as the template. Always:

```python
conn = connect_rmtree(DB, read_only=False)
cur = conn.cursor()
try:
    # ... all inserts ...
    conn.commit()
except Exception as e:
    conn.rollback()
    raise
finally:
    conn.close()
```

**Mandatory pre-checks inside the try block** (rollback safety):
- The owning person(s) exist.
- The intended PlaceID matches the expected Name.
- No duplicate Source with the same Name.
- No duplicate Witness for the same (EventID, PersonID).

### Step 8 — Verify

After commit, read back and print:
- Person's full event list, joined to source name where citation exists
- Witness's "owned + witnessed" event view (so you can see the shared fact from their side)
- Media path on disk (`os.path.exists`, size)

A clean verification means you can hand off to the user without "let me know if
RM doesn't show it" hedging.

---

## Schema cheat sheet (the minimum you need)

Detail is in `reference/schema-reference.md`. Quick form:

### SourceTable (free-form census = TemplateID 0)
```sql
INSERT INTO SourceTable (Name, RefNumber, ActualText, Comments, IsPrivate, TemplateID, Fields, UTCModDate)
VALUES (?, '', '', '', 0, 0, ?, julianday('now') - 2415018.5)
```
`Fields` is an **XML BLOB** with HTML inside it entity-encoded:
```xml
<Root><Fields>
  <Field><Name>Footnote</Name><Value>... &lt;i&gt;FamilySearch&lt;/i&gt; ... &quot;...&quot; ...</Value></Field>
  <Field><Name>ShortFootnote</Name><Value>...</Value></Field>
  <Field><Name>Bibliography</Name><Value>...</Value></Field>
</Fields></Root>
```
Encode with `.encode('utf-8')` before binding. Don't write raw `<i>` or `"` — use `&lt;i&gt;` and `&quot;`.

### CitationTable
```sql
INSERT INTO CitationTable
  (SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote, Bibliography, Fields, UTCModDate, CitationName)
VALUES (?, '', '', '', '', '', '', ?, julianday('now') - 2415018.5, '')
```
`Fields` BLOB is minimal: `<Root><Fields><Field><Name>Page</Name><Value></Value></Field></Fields></Root>`.

### CitationLinkTable (citation → event)
```sql
INSERT INTO CitationLinkTable
  (CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate)
VALUES (?, 2, <EventID>, 0, '~~~', 0, 0, julianday('now') - 2415018.5)
```
`OwnerType=2` = Event. Quality `'~~~'` is the project default (three tildes
encoding source/info/evidence quality).

### EventTable (Census = EventType 18)
```sql
INSERT INTO EventTable
  (EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate, IsPrimary, IsPrivate, Proof, Status, Sentence, Details, Note, UTCModDate)
VALUES (18, 0, <RIN>, 0, <PlaceID>, 0, ?, ?, 0, 0, 0, 0, '', '', '', julianday('now') - 2415018.5)
```
`OwnerType=0` = Person. Date format is `D.+YYYYMMDD..+00000000..`
(use `..` zeros for unknown month/day; e.g. `D.+19400000..+00000000..` =
"1940, unknown month/day"). SortDate is a BIGINT; reuse an existing event's
SortDate for the same date string (see `reference/schema-reference.md` for the
common 1850–1950 SortDate values).

### WitnessTable (spouse / child on the same census)
```sql
INSERT INTO WitnessTable
  (EventID, PersonID, WitnessOrder, Role, Sentence, Note, Given, Surname, Prefix, Suffix, UTCModDate)
VALUES (?, ?, 0, <RoleID>, '', '', '', '', '', '', julianday('now') - 2415018.5)
```
Common Role IDs for census events (verify with `SELECT * FROM RoleTable WHERE EventType = 18`):
- `63` = son
- `65` = daughter
- `66` = wife
- See `reference/schema-reference.md` for the full list.

The shared-fact pattern: don't create a duplicate census event on each
household member's record. Create the event once on the head of household,
attach everyone else via WitnessTable. The citation and image attached to the
event will appear under each witness's record automatically.

### MultimediaTable (the image row)
```sql
INSERT INTO MultimediaTable
  (MediaType, MediaPath, MediaFile, URL, Caption, RefNumber, Date, SortDate, Description, UTCModDate)
VALUES (1, ?, ?, ?, ?, '', ?, ?, '', julianday('now') - 2415018.5)
```
`MediaType=1` = image. `MediaPath` uses RM Windows form: `?\Records - Census\<YEAR> Federal`. `Date` = census day: `D.+19400401..+00000000..` etc.

### MediaLinkTable (image → source, event, citation — **all three**)
```sql
INSERT INTO MediaLinkTable
  (MediaID, OwnerType, OwnerID, IsPrimary, SortOrder, RectLeft, RectTop, RectRight, RectBottom, Comments, UTCModDate)
VALUES (?, ?, ?, 0, 0, NULL, NULL, NULL, NULL, '', julianday('now') - 2415018.5)
```
Three rows per image — one each for:
- `(OwnerType=3, OwnerID=<SourceID>)` — image on source
- `(OwnerType=2, OwnerID=<EventID>)`  — image on event
- `(OwnerType=4, OwnerID=<CitationID>)` — image on citation

Rect coords stay NULL — this project does not use RM's photo-tagging rectangles
for census images (verified 0 of 1818 1940-census image links use them).

---

## Quick-look: the most common operation

For a brand-new census from a FamilySearch ARK, with a spouse to attach as Wife:

```bash
# 1. Get the indexed fields
uv run python3 .claude/skills/rootsmagic-census-citation/scripts/fetch_familysearch_record.py \
    "https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3"

# 2. Download the image
uv run python3 .claude/skills/rootsmagic-census-citation/scripts/download_fs_image.py \
    TH-1942-27890-6409-22 \
    "$HOME/Genealogy/RootsMagic/Files/Records - Census/1940 Federal/1940, New Mexico, Santa Fe - Iams, John Willis.jpg"

# 3. Confirm OwnerType mapping against THIS database
uv run python3 .claude/skills/rootsmagic-census-citation/scripts/verify_owner_types.py data/Iiams.rmtree

# 4. Backup, then add the citation in one transaction (template script)
cp data/Iiams.rmtree backup/Iiams.rmtree.backup-$(date +%Y%m%d-%H%M%S)-pre-census
uv run python3 .claude/skills/rootsmagic-census-citation/scripts/add_census_citation.py
# (edit the constants at top of add_census_citation.py for the new record)
```

---

## Census year format quick reference

Full templates with worked examples in `reference/citation-formats.md`.

| Years | Citation key features |
|-------|----------------------|
| 1790-1840 | Head of household only, tally columns; no ED, no population schedule terminology |
| 1850, 1870 | Population schedule, sheet, dwelling/family, line |
| 1860 | Population schedule, **page** (not sheet), family/household ID (not line) |
| 1880 | **ED introduced**, page (stamped), line |
| 1900-1940 | Population schedule, ED, sheet, family number, line |
| 1950 standard | Population schedule, ED, **stamp** (not sheet), line |
| 1950 experimental sample | ED, **stamp only** — no sheet/line indexed; image is a photographed card stack |

For the 1950 experimental format specifically: the FamilySearch index leaves
"Supervisor District" / ED **blank**, and the card image's top edge is often
unreadable (photographed stacks at an angle). Ask the user for the ED.
Source name format: `Fed Census: 1950, <State>, <County> [ED <ED>, stamp <stamp>] <Surname>, <Given>`.

---

## Project conventions worth memorizing

These are specific to the host project (RMCitecraft / Iiams.rmtree) but most
RootsMagic projects use very similar patterns.

- **DB path**: `data/Iiams.rmtree` (working copy; never operate on production).
- **Media root**: `~/Genealogy/RootsMagic/Files/Records - Census/<YEAR> Federal/`.
- **Backup dir**: `backup/` (timestamped copies; never overwrite).
- **Surname variants** to search: Iiams, Ijams, Iams, Imes, Iames, Ijames, Iiames.
- **Chrome CDP**: must be already running on `localhost:9222` with the user
  logged into FamilySearch. Connect via `chromium.connect_over_cdp` — never
  launch a new browser. If the user's CDP isn't running, ask them to start it
  (the command is in the project CLAUDE.md).
- **Citation quality default**: `'~~~'` (three tildes).
- **No RM rectangle tagging** for census images.

---

## Pitfalls — read before writing

`reference/pitfalls.md` has the full list. The three that will burn you fastest:

1. **MediaLink OwnerType inversion.** Source ≠ 2 even though it has 2 as the
   first digit you see. Run `scripts/verify_owner_types.py` against the
   live DB before committing inserts.
2. **BLOB string mangling.** `SourceTable.Fields` is XML stored as BLOB.
   Read with `CAST(Fields AS TEXT)`. Write with `.encode('utf-8')`. Never
   `REPLACE()` it in SQL.
3. **Duplicate events instead of witnesses.** If the spouse / child / parent is
   already in the database, attach them to the existing head-of-household
   event as a Witness with the right Role, not by creating a parallel event.

---

## Reference files

- `reference/schema-reference.md` — full table schemas, role IDs, date format, SortDate constants
- `reference/citation-formats.md` — Evidence Explained citation templates per census year, with worked examples
- `reference/pitfalls.md` — bugs to avoid, with the OwnerType-inversion war story

## Reusable scripts

- `scripts/fetch_familysearch_record.py` — pull indexed fields from a FS ARK via Chrome CDP
- `scripts/download_fs_image.py` — download a census image at chosen resolution
- `scripts/verify_owner_types.py` — confirm MediaLink/CitationLink OwnerType mapping against the live DB
- `scripts/add_census_citation.py` — template transaction that creates source/citation/event/witness/media/links

Each script is standalone and prints usage when called with no args.
