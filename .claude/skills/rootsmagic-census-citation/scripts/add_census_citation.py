#!/usr/bin/env python3
"""Template for adding a fully-cited census record to a RootsMagic database.

EDIT the CONFIG section below to match the record you're adding, then run.
The script will:
  1. Run pre-checks (person exists, no duplicate source/event/witness).
  2. Create the Source with Evidence Explained Footnote/ShortFootnote/Bibliography.
  3. Create the Citation.
  4. Create the census Event (or reuse an existing one if EXISTING_EVENT_ID is set).
  5. Link Citation -> Event.
  6. Add household members as Witnesses with the right Role.
  7. Create the Multimedia entry.
  8. Link the Media to Source + Event + Citation (the correct THREE links).
  9. Validate every link OwnerType resolves to the expected table.
 10. Commit. On any error: rollback.

Run from project root:
    cp data/Iiams.rmtree backup/Iiams.rmtree.backup-$(date +%Y%m%d-%H%M%S)-pre-census
    uv run python3 .claude/skills/rootsmagic-census-citation/scripts/add_census_citation.py
"""
import sys
from rmcitecraft.database.connection import connect_rmtree


# ----------------------------------------------------------------------------
# CONFIG — EDIT EVERYTHING IN THIS BLOCK FOR THE SPECIFIC RECORD
# ----------------------------------------------------------------------------
DB = 'data/Iiams.rmtree'

# The head-of-household person (whose census event this is)
HEAD_RIN = 7533
HEAD_FULL_NAME = 'John Willis Iams'  # used inside the citation prose

# Set to an existing EventID to REUSE; leave None to CREATE a new event
EXISTING_EVENT_ID = None
PLACE_ID = 250                       # Required if creating; ignored if reusing
PLACE_NAME = 'Columbus, Franklin, Ohio, United States'  # Sanity check (cross-checked against PLACE_ID)
CENSUS_DATE_STR = 'D.+19500410..+00000000..'   # See reference/schema-reference.md "Date format"
CENSUS_SORT_DATE = 6727398195609993228         # See SortDate constants

# Citation source-of-truth values
YEAR = 1950
STATE_FULL = 'Ohio'
STATE_ABBR = 'Ohio'                  # ShortFootnote (traditional, with period if applicable)
COUNTY = 'Franklin'
COUNTY_ABBR = 'Franklin'             # Most counties have no abbreviation
CITY_TOWNSHIP = 'Columbus'
ED = '94-30'
SHEET = None                         # e.g. '12-A' for standard 1940; None for 1950 experimental
LINE = None                          # e.g. '5'; None for 1950 experimental
STAMP = '15379'                      # 1950 uses stamp; None for years that use sheet+line only
ARK = 'https://www.familysearch.org/ark:/61903/1:1:6JKY-W4CB'
ACCESS_DATE_LONG = '3 June 2026'     # Footnote "accessed" date
ACCESS_YEAR = '2026'                 # Bibliography year

# Database-name string by year — note 1940/1950 use commas in the title
DB_NAME_QUOTED = '&quot;United States, Census, 1950,&quot;'      # Footnote form (with trailing comma)
DB_NAME_BIBL   = '&quot;United States, Census, 1950.&quot;'      # Bibliography form (with trailing period)

# Bibliography line-2 prefix per year:
#   1940: 'U.S. <State>. <County> County. <YEAR> U.S. Census. Imaged. ...'
#   1950: 'U.S. <State>. <County> County. <YEAR> U.S. Census. Population Schedule. Imaged. ...'
BIBL_SCHEDULE_PHRASE = 'Population Schedule. '   # '' for 1940; 'Population Schedule. ' for 1950

# Locator section that goes inside [brackets] in the Source name and into the citation prose
LOCATOR_BRACKETS = f'ED {ED}, stamp {STAMP}'                                      # 1950 experimental
LOCATOR_FOOTNOTE = f'enumeration district (ED) {ED}, stamp {STAMP}'              # 1950 experimental
LOCATOR_SHORT    = f'E.D. {ED}, stamp {STAMP}'                                    # 1950 experimental

# Household members already in the database. Each is added as a Witness on the event.
# Format: (PersonID, RoleID, role_name_for_log)
# Role IDs for census (EventType 18): 63=son, 65=daughter, 66=wife. Verify with:
#   SELECT RoleID, RoleName FROM RoleTable WHERE EventType = 18;
WITNESSES = [
    (7534, 66, 'wife'),    # Elsie Mae Baker
]

# Media (image) settings
MEDIA_PATH    = r'?\Records - Census\1950 Federal'
MEDIA_FILE    = '1950, Ohio, Franklin - Iams, John Willis.jpg'
MEDIA_CAPTION = 'Census: 1950 Fed Census - Franklin, OH'
MEDIA_DATE    = 'D.+19500401..+00000000..'             # Census Day
MEDIA_SORT_DATE = 6727393247807668236                  # April 1, 1950 SortDate
# ----------------------------------------------------------------------------


# Derived strings
SOURCE_NAME = (
    f'Fed Census: {YEAR}, {STATE_FULL}, {COUNTY} '
    f'[{LOCATOR_BRACKETS}] {HEAD_FULL_NAME.rsplit(maxsplit=1)[-1]}, '
    f'{" ".join(HEAD_FULL_NAME.split()[:-1])}'
)

FOOTNOTE = (
    f'{YEAR} U.S. census, {COUNTY} County, {STATE_FULL}, {CITY_TOWNSHIP}, '
    f'{LOCATOR_FOOTNOTE}, {HEAD_FULL_NAME}; '
    f'imaged, {DB_NAME_QUOTED} &lt;i&gt;FamilySearch&lt;/i&gt; '
    f'({ARK} : accessed {ACCESS_DATE_LONG}).'
)

SHORT_FOOTNOTE = (
    f'{YEAR} U.S. census, {COUNTY_ABBR} Co., {STATE_ABBR}, {CITY_TOWNSHIP}, '
    f'{LOCATOR_SHORT}, {HEAD_FULL_NAME}.'
)

BIBLIOGRAPHY = (
    f'U.S. {STATE_FULL}. {COUNTY} County. {YEAR} U.S. Census. '
    f'{BIBL_SCHEDULE_PHRASE}'
    f'Imaged. {DB_NAME_BIBL} &lt;i&gt;FamilySearch&lt;/i&gt;. '
    f'{ARK} : {ACCESS_YEAR}.'
)

SOURCE_FIELDS_XML = (
    '<Root><Fields>'
    f'<Field><Name>Footnote</Name><Value>{FOOTNOTE}</Value></Field>'
    f'<Field><Name>ShortFootnote</Name><Value>{SHORT_FOOTNOTE}</Value></Field>'
    f'<Field><Name>Bibliography</Name><Value>{BIBLIOGRAPHY}</Value></Field>'
    '</Fields></Root>'
)

CITATION_FIELDS_XML = (
    '<Root><Fields><Field><Name>Page</Name><Value></Value></Field></Fields></Root>'
)


# OwnerType constants (DO NOT CHANGE without re-verifying with verify_owner_types.py)
OT_PERSON   = 0
OT_FAMILY   = 1
OT_EVENT    = 2
OT_SOURCE   = 3
OT_CITATION = 4
OT_PLACE    = 5


def main():
    print("=== DRY RUN PREVIEW ===")
    print(f"Source Name:     {SOURCE_NAME}")
    print(f"Footnote (raw):  {FOOTNOTE}")
    print(f"ShortFootnote:   {SHORT_FOOTNOTE}")
    print(f"Bibliography:    {BIBLIOGRAPHY}")
    print(f"Event:           {'REUSE ' + str(EXISTING_EVENT_ID) if EXISTING_EVENT_ID else 'CREATE new at ' + str(PLACE_ID)}")
    print(f"Witnesses:       {WITNESSES}")
    print(f"Media file:      {MEDIA_FILE}")

    print("\nProceed? (Ctrl-C to abort, Enter to continue)", file=sys.stderr)
    try:
        input()
    except EOFError:
        # non-interactive; assume go
        pass

    conn = connect_rmtree(DB, read_only=False)
    cur = conn.cursor()

    try:
        # Pre-checks
        cur.execute("SELECT 1 FROM PersonTable WHERE PersonID = ?", (HEAD_RIN,))
        assert cur.fetchone(), f"Head RIN {HEAD_RIN} not found"

        for wrin, role, label in WITNESSES:
            cur.execute("SELECT 1 FROM PersonTable WHERE PersonID = ?", (wrin,))
            assert cur.fetchone(), f"Witness RIN {wrin} ({label}) not found"

        cur.execute("SELECT 1 FROM SourceTable WHERE Name = ?", (SOURCE_NAME,))
        assert not cur.fetchone(), f"Source already exists: {SOURCE_NAME}"

        if EXISTING_EVENT_ID is None:
            cur.execute("SELECT 1 FROM PlaceTable WHERE PlaceID = ? AND Name = ?", (PLACE_ID, PLACE_NAME))
            assert cur.fetchone(), f"PlaceID {PLACE_ID} does not have Name {PLACE_NAME!r}"
            cur.execute(
                "SELECT EventID FROM EventTable "
                "WHERE OwnerID = ? AND OwnerType = 0 AND EventType = 18 AND Date LIKE ?",
                (HEAD_RIN, f"D.+{YEAR}%")
            )
            assert not cur.fetchone(), f"A {YEAR} census event already exists on RIN {HEAD_RIN}"

        # 1) Source
        cur.execute(
            "INSERT INTO SourceTable (Name, RefNumber, ActualText, Comments, IsPrivate, TemplateID, Fields, UTCModDate) "
            "VALUES (?, '', '', '', 0, 0, ?, julianday('now') - 2415018.5)",
            (SOURCE_NAME, SOURCE_FIELDS_XML.encode('utf-8'))
        )
        source_id = cur.lastrowid
        print(f"SourceID = {source_id}")

        # 2) Citation
        cur.execute(
            "INSERT INTO CitationTable (SourceID, Comments, ActualText, RefNumber, Footnote, ShortFootnote, Bibliography, Fields, UTCModDate, CitationName) "
            "VALUES (?, '', '', '', '', '', '', ?, julianday('now') - 2415018.5, '')",
            (source_id, CITATION_FIELDS_XML.encode('utf-8'))
        )
        citation_id = cur.lastrowid
        print(f"CitationID = {citation_id}")

        # 3) Event
        if EXISTING_EVENT_ID is not None:
            event_id = EXISTING_EVENT_ID
            cur.execute("SELECT 1 FROM EventTable WHERE EventID = ?", (event_id,))
            assert cur.fetchone(), f"EXISTING_EVENT_ID {event_id} not found"
            print(f"Reusing EventID {event_id}")
        else:
            cur.execute(
                "INSERT INTO EventTable "
                "(EventType, OwnerType, OwnerID, FamilyID, PlaceID, SiteID, Date, SortDate, "
                " IsPrimary, IsPrivate, Proof, Status, Sentence, Details, Note, UTCModDate) "
                "VALUES (18, 0, ?, 0, ?, 0, ?, ?, 0, 0, 0, 0, '', '', '', julianday('now') - 2415018.5)",
                (HEAD_RIN, PLACE_ID, CENSUS_DATE_STR, CENSUS_SORT_DATE)
            )
            event_id = cur.lastrowid
            print(f"EventID = {event_id}")

        # 4) Citation link -> event
        cur.execute(
            "INSERT INTO CitationLinkTable "
            "(CitationID, OwnerType, OwnerID, SortOrder, Quality, IsPrivate, Flags, UTCModDate) "
            "VALUES (?, ?, ?, 0, '~~~', 0, 0, julianday('now') - 2415018.5)",
            (citation_id, OT_EVENT, event_id)
        )

        # 5) Witnesses
        for wrin, role, label in WITNESSES:
            cur.execute("SELECT 1 FROM WitnessTable WHERE EventID = ? AND PersonID = ?", (event_id, wrin))
            if cur.fetchone():
                print(f"  Witness already exists: RIN {wrin} ({label}) — skipping")
                continue
            cur.execute(
                "INSERT INTO WitnessTable "
                "(EventID, PersonID, WitnessOrder, Role, Sentence, Note, Given, Surname, Prefix, Suffix, UTCModDate) "
                "VALUES (?, ?, 0, ?, '', '', '', '', '', '', julianday('now') - 2415018.5)",
                (event_id, wrin, role)
            )
            print(f"  Witness: RIN {wrin} as {label} (Role {role}), WitnessID {cur.lastrowid}")

        # 6) Multimedia
        cur.execute(
            "INSERT INTO MultimediaTable "
            "(MediaType, MediaPath, MediaFile, URL, Caption, RefNumber, Date, SortDate, Description, UTCModDate) "
            "VALUES (1, ?, ?, ?, ?, '', ?, ?, '', julianday('now') - 2415018.5)",
            (MEDIA_PATH, MEDIA_FILE, ARK, MEDIA_CAPTION, MEDIA_DATE, MEDIA_SORT_DATE)
        )
        media_id = cur.lastrowid
        print(f"MediaID = {media_id}")

        # 7) Media links (3 rows) — Event, Source, Citation
        link_specs = [
            (OT_EVENT,    event_id,    'Event'),
            (OT_SOURCE,   source_id,   'Source'),
            (OT_CITATION, citation_id, 'Citation'),
        ]
        for ot, oid, label in link_specs:
            cur.execute(
                "INSERT INTO MediaLinkTable "
                "(MediaID, OwnerType, OwnerID, IsPrimary, SortOrder, RectLeft, RectTop, RectRight, RectBottom, Comments, UTCModDate) "
                "VALUES (?, ?, ?, 0, 0, NULL, NULL, NULL, NULL, '', julianday('now') - 2415018.5)",
                (media_id, ot, oid)
            )
            print(f"  MediaLink: Media {media_id} -> OwnerType {ot} ({label}) OwnerID {oid}")

        # 8) Post-write validation
        print("\nValidating links...")
        for ot, oid, label in link_specs:
            target_table = {OT_EVENT: 'EventTable', OT_SOURCE: 'SourceTable', OT_CITATION: 'CitationTable'}[ot]
            target_col   = {OT_EVENT: 'EventID',    OT_SOURCE: 'SourceID',    OT_CITATION: 'CitationID'}[ot]
            cur.execute(f"SELECT 1 FROM {target_table} WHERE {target_col} = ?", (oid,))
            assert cur.fetchone(), f"MediaLink validation failed: OwnerType {ot}, OwnerID {oid} not in {target_table}"
            print(f"  OK: OwnerType {ot} -> {target_table}.{target_col} {oid}")

        conn.commit()
        print(f"\nCOMMITTED. SourceID={source_id} CitationID={citation_id} EventID={event_id} MediaID={media_id}")

    except Exception as e:
        conn.rollback()
        print(f"ROLLED BACK: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
