# Pitfalls and how to avoid them

War stories from the field. Read this before your first write batch.

---

## 1. MediaLink / CitationLink OwnerType inversion

**The bug.** RootsMagic uses an integer OwnerType in both `MediaLinkTable` and
`CitationLinkTable` to discriminate which table the `OwnerID` references.
It is tempting to guess the mapping from the count distribution:

```
MediaLink OwnerType 2: 11115 rows (~one per census image)
MediaLink OwnerType 3: 12763 rows (~one per census image + a few extras)
MediaLink OwnerType 4: 12566 rows (~one per census image)
```

The counts are close enough that you might assume Source/Citation/Event in
some convenient order. They don't.

**The correct mapping** (verified by tracing concrete OwnerIDs back to their
unique table):

| OwnerType | Owner Table |
|-----------|-------------|
| 0 | PersonTable |
| 1 | FamilyTable |
| 2 | EventTable |
| 3 | SourceTable |
| 4 | CitationTable |
| 5 | PlaceTable |

**Why the SQL won't catch a mistake.** SQLite doesn't enforce a FK on
(OwnerType, OwnerID) because the target table varies. Insert with the wrong
OwnerType and the row commits cleanly — the image is just orphaned from the RM
UI. You won't find out until the user opens RootsMagic and says "I don't see
the image on the Source tab".

**How to avoid:**
1. Run `scripts/verify_owner_types.py <dbpath>` against the live DB before
   any insert batch. It picks a known-good media row and walks the OwnerIDs
   back to confirm.
2. In the insert code, build the row tuples from a labelled constant:
   ```python
   OWNER_EVENT, OWNER_SOURCE, OWNER_CITATION = 2, 3, 4
   for owner_type, owner_id in [
       (OWNER_EVENT, event_id),
       (OWNER_SOURCE, source_id),
       (OWNER_CITATION, citation_id),
   ]:
       cur.execute("INSERT INTO MediaLinkTable ...", (media_id, owner_type, owner_id, ...))
   ```
3. After commit, validate by joining each new link to the expected table:
   ```python
   for ot, oid in cur.execute("SELECT OwnerType, OwnerID FROM MediaLinkTable WHERE MediaID = ?", (media_id,)):
       table = {2: 'EventTable', 3: 'SourceTable', 4: 'CitationTable'}[ot]
       col   = {2: 'EventID',    3: 'SourceID',    4: 'CitationID'}[ot]
       cur.execute(f"SELECT 1 FROM {table} WHERE {col} = ?", (oid,))
       assert cur.fetchone()
   ```

---

## 2. SourceTable.Fields BLOB string mangling

**The bug.** The `Fields` column is XML stored as a BLOB. It contains HTML
formatting tags that are XML entity-encoded (`&lt;i&gt;` for `<i>`, `&quot;`
for `"`). Two failure modes:

- **SQL string functions on BLOB**: `UPDATE SourceTable SET Fields = REPLACE(Fields, 'old', 'new')` corrupts the BLOB type and changes the encoding silently.
- **Double-decoding**: reading with `CAST(Fields AS TEXT)` returns entity-encoded text. If you `html.unescape()` it, then write back without re-encoding, the next reader sees raw `<i>` which the XML parser treats as markup and breaks.

**How to avoid:**

Read pattern:
```python
cur.execute("SELECT CAST(Fields AS TEXT) FROM SourceTable WHERE SourceID = ?", (sid,))
text = cur.fetchone()[0]   # entities are still encoded: &lt;i&gt;, &quot;, etc.
```

Mutate pattern: do plain Python string ops on the entity-encoded text — don't
decode first.
```python
new_text = text.replace('&lt;i&gt;FamilySearch&lt;/i&gt;', '&lt;i&gt;Ancestry.com&lt;/i&gt;')
```

Write pattern:
```python
cur.execute("UPDATE SourceTable SET Fields = ? WHERE SourceID = ?", (new_text.encode('utf-8'), sid))
```

When constructing fresh BLOB content (new source), build the XML string with
already-encoded entities:
```python
footnote = '... &lt;i&gt;FamilySearch&lt;/i&gt; ... &quot;United States, Census, 1940,&quot; ...'
xml = f'<Root><Fields><Field><Name>Footnote</Name><Value>{footnote}</Value></Field>...</Fields></Root>'
cur.execute("INSERT INTO SourceTable (... Fields ...) VALUES (..., ?, ...)", (..., xml.encode('utf-8'), ...))
```

**Note:** Other tables (PersonTable.Note, EventTable.Note) store TEXT with raw
HTML — they are not XML and don't follow this rule. The XML-BLOB pattern is
specific to `SourceTable.Fields` and `CitationTable.Fields`.

---

## 3. Duplicate events instead of witness rows

**The bug.** A census record covers a household — head, spouse, children,
boarders. The naive pattern is to create a parallel `EventTable` row for each
person, each with its own citation link.

This works in the short term but creates maintenance debt:
- Citation prose changes (e.g. fix a typo) → must be edited on each duplicate.
- Image attachment changes → must be re-linked on each duplicate.
- The household relationship is lost from the data model — RM doesn't know
  these four events are the same census enumeration.

**The correct pattern (shared facts via WitnessTable):**

1. Create **one** Census event, owned by the head of household
   (`EventTable.OwnerType=0, OwnerID=<HoH RIN>`).
2. For each other household member who is in the database, insert a
   `WitnessTable` row:
   ```sql
   INSERT INTO WitnessTable (EventID, PersonID, WitnessOrder, Role, ...)
   VALUES (<event_id>, <member_rin>, 0, <role_id>, ...);
   ```
   Where `<role_id>` matches the relationship: 66 = wife, 63 = son, 65 = daughter.
3. Link the citation to the head's event once: `CitationLinkTable(citation_id, OwnerType=2, OwnerID=event_id)`.
4. Link the image to the head's event once: `MediaLinkTable(media_id, OwnerType=2, OwnerID=event_id)`.

In RM, the spouse / children will see this as a witnessed event with the
sentence "[Witness] appeared as the [role] of [head] in the census of [date] [place]."
The citation and image appear under each witness's record automatically.

**Decision tree for duplicate-vs-witness:**

- Is the other household member in the RM database? → Yes: witness. No: nothing
  to do; they aren't tracked.
- Are you sure the head-of-household relationship is correct? → Yes: witness.
  No: ask the user — sometimes the "head" on the census is the boarder, not the
  RM-tracked ancestor.
- Is the user specifically asking for duplicate events? → Honor the request,
  but warn them about the maintenance cost.

---

## 4. Date format errors

The `EventTable.Date` and `MultimediaTable.Date` columns use a specific string
format that is **not** ISO 8601:

```
D.+YYYYMMDD..+YYYYMMDD..
```

Common mistakes:
- Writing `2020-04-01` (ISO) → invalid; RM displays it as garbage.
- Writing `D.+19400401` (missing trailing `..+00000000..`) → invalid.
- Using `DA+...` for an exact date → RM treats it as "about", showing "Abt 1 Apr 1940".

Date prefix reference:
- `D.` — exact ("on")
- `DA` — approximate ("about", "circa")
- `DB` — before
- `DF` — after
- `D-` — between (used with two YYYYMMDD blocks)

For census events, always use `D.` (exact, since you can pin to enumeration date)
or `D.+YYYY0000..+00000000..` (year-only when day isn't known/relevant).

---

## 5. PlaceID confusion

`EventTable.PlaceID` is a foreign key, not a name. Common mistakes:
- Inserting with `PlaceID = 0` "for now" — RM displays "no place" and the place
  doesn't appear on the timeline.
- Looking up by partial match — collapses "Columbus, Ohio, United States" with
  "Columbus, Franklin, Ohio, United States" (different IDs).

Always exact-match the canonical comma form when looking up:
```python
cur.execute("SELECT PlaceID FROM PlaceTable WHERE Name = ?",
            ("Columbus, Franklin, Ohio, United States",))
```

If the place doesn't exist, **don't auto-insert** from this skill. Ask the user
to add it via RootsMagic's place manager — that normalizes the spelling,
populates lat/lon, and avoids duplicates.

---

## 6. Census event OwnerType=0 vs 1

The `OwnerType` on the `EventTable` row (not the link tables!) discriminates
person events from family events:

| OwnerType | OwnerID is | Event examples |
|-----------|------------|----------------|
| 0 | PersonID | Birth, Death, Census, Occupation, Residence |
| 1 | FamilyID | Marriage, Divorce, Family Census (rare) |

For census events, **always use OwnerType=0** with the head of household as
OwnerID. Family-owned census events exist in RM but are nonstandard and don't
interact cleanly with the witness pattern.

---

## 7. ICU extension / RMNOCASE collation

If you see this error, you used `sqlite3.connect()` directly instead of
`connect_rmtree()`:

```
sqlite3.OperationalError: no such collation sequence: RMNOCASE
```

Many `NameTable` and other text columns use RMNOCASE for case-insensitive
comparison with ICU Unicode support. Without the extension, even reading them
fails.

Fix: always use `from rmcitecraft.database.connection import connect_rmtree`.

---

## 8. "Working copy" vs production database

Per project CLAUDE.md: RMCitecraft operates on a working copy at
`data/Iiams.rmtree`. The user's production RootsMagic database is elsewhere
and is hand-copied back when satisfied.

Implications:
- Don't try to write to the user's production path.
- Don't assume the working copy is fresh — the user may have made
  manual edits in RootsMagic GUI between sessions. Re-read state, don't trust
  cached values.

---

## 9. The 1950 experimental format "blank ED" trap

The FamilySearch index for the 1950 experimental sample format leaves the
Supervisor District / ED field **blank**. The image is a photographed stack of
cards taken at an angle, so the top edge with the stamped ED is often cropped
out of view in the displayed image.

Mistakes:
- Guessing the ED from a nearby record (adjacent index entries may be different EDs).
- Reusing the ED from another household in the same city (e.g. "Columbus = ED 94-474")
  — Columbus had many EDs in 1950.
- Omitting the ED silently — leaves an incomplete citation.

Correct action: **ask the user for the ED**. They likely know it from context
(a NARA finding aid, the image at higher zoom, or knowledge of the address's
ED assignment). Use `AskUserQuestion` with concrete options, and offer the
"omit ED" fallback so the citation is honest about what's verifiable.

---

## 10. Mismatched FamilySearch indexed name vs database record

The FS index OCR / transcription often mangles the surname. Examples seen:
- "Iams" → "Dams" (capital I read as D)
- "Ijams" → "Ljams"
- "Imes" → "Ines"

The user has already confirmed identification when they hand you the ARK —
don't second-guess based on the index name. Use the database's primary name
when constructing the citation prose, not the FS transcription. (The citation
should reflect the *person*, not the *index error*; the ARK alone is sufficient
for someone to retrieve the original.)

---

## 11. Skipping pre-write duplicate checks

Common ways to accidentally double-write:
- User said "create the source" but you missed that they had already created
  the source earlier — query by Name before inserting.
- The census event already exists — query by OwnerID/EventType/Date pattern.
- The spouse is already attached as a witness from a prior session.

Always include these pre-checks in the try block before any insert:

```python
# Source uniqueness
cur.execute("SELECT 1 FROM SourceTable WHERE Name = ?", (source_name,))
assert not cur.fetchone(), f"Source already exists: {source_name}"

# Event uniqueness (same year, same person, same type)
cur.execute("""SELECT EventID FROM EventTable
               WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 18 AND Date LIKE ?""",
            (rin, f"D.+{year}%"))
assert not cur.fetchone(), f"Census event for {year} already exists on RIN {rin}"

# Witness uniqueness
cur.execute("SELECT 1 FROM WitnessTable WHERE EventID = ? AND PersonID = ?", (event_id, witness_rin))
assert not cur.fetchone(), f"{witness_rin} already a witness on event {event_id}"
```

Failed assertions trigger rollback (assuming you're in a try/except), so the
DB stays clean.
