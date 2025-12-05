---
priority: reference
topics: [database, ui]
---

# Using RMNOCASE Collation with RootsMagic Databases

RootsMagic uses a proprietary collation sequence called RMNOCASE, with several fields requiring it for sorting. As a work-around, unifuzz.dll is frequently used on the Windows platform. Below are methods to use RMNOCASE on the MacOS platform using icu.dylib.

## Method 1: SQLite Command Line

Use modern sqlite client that supports .load command. MacOS native sqlite client is too old. Homebrew install version is here:
/opt/homebrew/opt/sqlite/bin/sqlite3

Load a database in sqlite:
/opt/homebrew/opt/sqlite/bin/sqlite3 ./data/Iiams.rmtree

Run sqlite command:
.load "./sqlite-extension/icu.dylib"

Run sqlite query:
SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE');

You are now read to run queries in the RootsMagic database that are collated with RMNOCASE, such as:

SELECT Surname FROM NameTable ORDER BY Surname;

Or as one command:
/opt/homebrew/opt/sqlite/bin/sqlite3 ./data/Iiams.rmtree <<EOF
.load "./sqlite-extension/icu.dylib"
SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE');
SELECT Surname FROM NameTable ORDER BY Surname COLLATE RMNOCASE;
EOF

## Method 2: Python Scripts

Python scripts can also load the ICU extension to enable RMNOCASE collation:

```python
import sqlite3

def connect_rmtree(db_path, extension_path='./sqlite-extension/icu.dylib'):
    """Connect to RootsMagic database with RMNOCASE collation support."""
    conn = sqlite3.connect(db_path)

    # Load ICU extension and register RMNOCASE collation
    conn.enable_load_extension(True)
    conn.load_extension(extension_path)
    conn.execute(
        "SELECT icu_load_collation('en_US@colStrength=primary;caseLevel=off;normalization=on','RMNOCASE')"
    )
    conn.enable_load_extension(False)

    return conn

# Usage
conn = connect_rmtree('data/Iiams.rmtree')
cursor = conn.cursor()
cursor.execute("SELECT Surname FROM NameTable ORDER BY Surname COLLATE RMNOCASE LIMIT 10")
for row in cursor.fetchall():
    print(row[0])
conn.close()
```

**See `python_example.py` in this directory for complete working examples.**

To run the example:
```bash
python3 sqlite-extension/python_example.py
```

## Building icu.dylib for MacOS

Reference for creating icu.dylib for MacOS:

brew install sqlite icu4c pkg-config (don't use the MacOS version of SQLite)
Source files downloaded from SQLite sqlite-src-3500400, in the ./ext/icu directory
export PKG_CONFIG_PATH="$(brew --prefix icu4c)/lib/pkgconfig:$PKG_CONFIG_PATH"
gcc -I../../src -fPIC -dynamiclib icu.c -o icu.dylib \
 $(pkg-config --cflags --libs icu-uc icu-i18n icu-io) \
 -Wl,-undefined,dynamic_lookup
