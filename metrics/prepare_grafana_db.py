import sqlite3
import os
import shutil
from pathlib import Path

# Paths
SOURCE_DB = Path("../data/Iiams.rmtree")
DEST_DB = Path("data/rootsmagic_clean.db")
ICU_EXTENSION = Path("../sqlite-extension/icu.dylib")

def get_table_schema(cursor, table_name):
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()
    if result:
        return result[0]
    return None

def clean_schema(sql):
    """Remove RMNOCASE collation from schema definition."""
    if not sql:
        return None
    # Remove case-insensitive collation
    clean_sql = sql.replace(" COLLATE RMNOCASE", "")
    return clean_sql

def main():
    print(f"Preparing Grafana database...")
    
    # Ensure destination directory exists
    DEST_DB.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing destination
    if DEST_DB.exists():
        os.remove(DEST_DB)

    # Connect to Source (with ICU for safety)
    try:
        src_conn = sqlite3.connect(SOURCE_DB)
        src_conn.enable_load_extension(True)
        src_conn.load_extension(str(ICU_EXTENSION))
        print(f"Connected to source: {SOURCE_DB}")
    except Exception as e:
        print(f"Error connecting to source (proceeding without ICU might fail): {e}")
        # Fallback if extension load fails (might not be needed just to read if we don't sort)
        src_conn = sqlite3.connect(SOURCE_DB)

    # Connect to Destination
    dest_conn = sqlite3.connect(DEST_DB)
    print(f"Created destination: {DEST_DB}")

    src_cursor = src_conn.cursor()
    dest_cursor = dest_conn.cursor()

    # Get list of tables
    src_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in src_cursor.fetchall() if not row[0].startswith('sqlite_')]

    for table in tables:
        print(f"Processing table: {table}...")
        
        # Get original schema
        schema = get_table_schema(src_cursor, table)
        
        # Clean schema (remove RMNOCASE)
        clean_create_sql = clean_schema(schema)
        
        try:
            # Create table in dest
            dest_cursor.execute(clean_create_sql)
            
            # Copy data
            # We select * from source. 
            # Note: If source has calculated columns or complex things relying on RMNOCASE in the SELECT, this might fail.
            # But usually SELECT * is safe.
            src_cursor.execute(f"SELECT * FROM {table}")
            rows = src_cursor.fetchall()
            
            if rows:
                placeholders = ','.join(['?'] * len(rows[0]))
                dest_cursor.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
                dest_conn.commit()
                print(f"  -> Copied {len(rows)} rows.")
            else:
                print(f"  -> Empty table.")
                
        except Exception as e:
            print(f"  -> Error processing {table}: {e}")

    # Add performance indexes
    print("\nAdding performance indexes...")
    try:
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_ownerid ON EventTable(OwnerID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON EventTable(EventType)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_placeid ON EventTable(PlaceID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_ownerid ON NameTable(OwnerID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_isprimary ON NameTable(IsPrimary)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_place_coords ON PlaceTable(Latitude, Longitude)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_citation_sourceid ON CitationTable(SourceID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_family_father ON FamilyTable(FatherID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_family_mother ON FamilyTable(MotherID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_child_childid ON ChildTable(ChildID)")
        dest_cursor.execute("CREATE INDEX IF NOT EXISTS idx_child_familyid ON ChildTable(FamilyID)")
        dest_conn.commit()
        print("  -> Added 11 performance indexes")
    except Exception as e:
        print(f"  -> Error adding indexes: {e}")

    # Create performance views
    print("\nCreating performance views...")
    try:
        # Person summary view
        dest_cursor.execute("""
            CREATE VIEW IF NOT EXISTS person_summary AS
            SELECT
                p.PersonID,
                n.Given || ' ' || n.Surname as full_name,
                n.Surname,
                n.Given,
                birth.Date as birth_date,
                death.Date as death_date,
                birth_place.PlaceName as birth_place,
                death_place.PlaceName as death_place,
                CAST((julianday(death.Date) - julianday(birth.Date)) / 365.25 AS INTEGER) as lifespan_years
            FROM PersonTable p
            JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
            LEFT JOIN EventTable birth ON birth.OwnerID = p.PersonID AND birth.EventType = 1
            LEFT JOIN EventTable death ON death.OwnerID = p.PersonID AND death.EventType = 2
            LEFT JOIN PlaceTable birth_place ON birth.PlaceID = birth_place.PlaceID
            LEFT JOIN PlaceTable death_place ON death.PlaceID = death_place.PlaceID
        """)
        print("  -> Created person_summary view")

        # Family connections view
        dest_cursor.execute("""
            CREATE VIEW IF NOT EXISTS family_connections AS
            SELECT
                f.FamilyID,
                f.FatherID,
                f.MotherID,
                father_name.Given || ' ' || father_name.Surname as father_name,
                father_name.Surname as father_surname,
                mother_name.Given || ' ' || mother_name.Surname as mother_name,
                mother_name.Surname as mother_surname,
                marriage.Date as marriage_date,
                marriage_place.PlaceName as marriage_place
            FROM FamilyTable f
            LEFT JOIN NameTable father_name ON father_name.OwnerID = f.FatherID AND father_name.IsPrimary = 1
            LEFT JOIN NameTable mother_name ON mother_name.OwnerID = f.MotherID AND mother_name.IsPrimary = 1
            LEFT JOIN EventTable marriage ON marriage.OwnerID = f.FamilyID AND marriage.EventType = 300 AND marriage.OwnerType = 1
            LEFT JOIN PlaceTable marriage_place ON marriage.PlaceID = marriage_place.PlaceID
        """)
        print("  -> Created family_connections view")

        # Citation quality view
        dest_cursor.execute("""
            CREATE VIEW IF NOT EXISTS citation_quality AS
            SELECT
                st.SourceID,
                st.Name as source_name,
                COUNT(DISTINCT ct.CitationID) as citation_count,
                COUNT(DISTINCT ml.MediaID) as media_count,
                CASE
                    WHEN st.TemplateID = 0 THEN 'Free-Form'
                    ELSE 'Template-Based'
                END as citation_type
            FROM SourceTable st
            LEFT JOIN CitationTable ct ON ct.SourceID = st.SourceID
            LEFT JOIN MediaLinkTable ml ON ml.OwnerID = st.SourceID AND ml.OwnerType = 3
            GROUP BY st.SourceID
        """)
        print("  -> Created citation_quality view")

        dest_conn.commit()
        print("  -> Created 3 performance views")
    except Exception as e:
        print(f"  -> Error creating views: {e}")

    # Close connections
    src_conn.close()
    dest_conn.close()

    # Set permissions for Docker
    os.chmod(DEST_DB, 0o666)

    print("\n" + "="*60)
    print("✓ Database ready for Grafana!")
    print("="*60)
    print(f"Location: {DEST_DB}")
    print("\nNext steps:")
    print("  1. Start Grafana: docker-compose up -d")
    print("  2. Open http://localhost:3000")
    print("  3. Navigate to Phase 1 Validation dashboard")
    print("  4. Run validation queries to test data quality")

if __name__ == "__main__":
    main()
