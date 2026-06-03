#!/usr/bin/env python3
"""
RootsMagic MCP Server

Provides Claude with direct tools for querying RootsMagic databases.

To register with Claude Code, add to ~/.claude/settings.json:

{
  "mcpServers": {
    "rmtree": {
      "command": "uv",
      "args": ["run", "python", "/path/to/rmtree_server.py"],
      "env": {
        "RMTREE_DB": "/path/to/data/Iiams.rmtree"
      }
    }
  }
}

Then restart Claude Code. The tools will appear as:
- rmtree_search_person
- rmtree_get_family
- rmtree_query_census
- rmtree_link_census
"""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path for connect_rmtree
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP package not installed. Install with: uv pip install mcp", file=sys.stderr)
    sys.exit(1)

from rmcitecraft.database.connection import connect_rmtree

# Configuration
RMTREE_DB = os.environ.get("RMTREE_DB", "data/Iiams.rmtree")
CENSUS_DB = Path.home() / ".rmcitecraft" / "census.db"

# Create server
server = Server("rmtree")


def parse_year(date_str: str) -> str | None:
    """Extract year from RootsMagic date format."""
    if date_str and len(date_str) >= 7:
        return date_str[3:7]
    return None


@server.list_tools()
async def list_tools():
    """List available RootsMagic tools."""
    return [
        Tool(
            name="rmtree_search_person",
            description="Search for persons in RootsMagic database by name, birth year range, or birthplace",
            inputSchema={
                "type": "object",
                "properties": {
                    "surname": {
                        "type": "string",
                        "description": "Surname to search (partial match supported)"
                    },
                    "given": {
                        "type": "string",
                        "description": "Given name to search (partial match supported)"
                    },
                    "birth_year_min": {
                        "type": "integer",
                        "description": "Minimum birth year"
                    },
                    "birth_year_max": {
                        "type": "integer",
                        "description": "Maximum birth year"
                    },
                    "birthplace": {
                        "type": "string",
                        "description": "Birthplace to search (partial match)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="rmtree_get_family",
            description="Get family relationships for a person: parents, spouses, children, siblings",
            inputSchema={
                "type": "object",
                "properties": {
                    "rin": {
                        "type": "integer",
                        "description": "RootsMagic person ID (RIN)"
                    }
                },
                "required": ["rin"]
            }
        ),
        Tool(
            name="rmtree_get_person",
            description="Get detailed information about a person by RIN",
            inputSchema={
                "type": "object",
                "properties": {
                    "rin": {
                        "type": "integer",
                        "description": "RootsMagic person ID (RIN)"
                    }
                },
                "required": ["rin"]
            }
        ),
        Tool(
            name="census_query",
            description="Query census.db for census records by surname, year, or state",
            inputSchema={
                "type": "object",
                "properties": {
                    "surname": {
                        "type": "string",
                        "description": "Surname to search"
                    },
                    "census_year": {
                        "type": "integer",
                        "description": "Census year (1790, 1800, etc.)"
                    },
                    "state": {
                        "type": "string",
                        "description": "State name"
                    },
                    "unlinked_only": {
                        "type": "boolean",
                        "description": "Only show records not linked to RINs",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="census_link",
            description="Create a link between a census record and a RootsMagic person (RIN)",
            inputSchema={
                "type": "object",
                "properties": {
                    "census_person_id": {
                        "type": "integer",
                        "description": "Census person ID from census.db"
                    },
                    "rmtree_person_id": {
                        "type": "integer",
                        "description": "RootsMagic person ID (RIN)"
                    },
                    "rmtree_source_id": {
                        "type": "integer",
                        "description": "RootsMagic source ID"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Match confidence (0.0-1.0)",
                        "default": 0.85
                    },
                    "method": {
                        "type": "string",
                        "description": "Match method (e.g., 'manual_analysis')",
                        "default": "manual_analysis"
                    }
                },
                "required": ["census_person_id", "rmtree_person_id", "rmtree_source_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""

    if name == "rmtree_search_person":
        return await search_person(arguments)
    elif name == "rmtree_get_family":
        return await get_family(arguments)
    elif name == "rmtree_get_person":
        return await get_person(arguments)
    elif name == "census_query":
        return await query_census(arguments)
    elif name == "census_link":
        return await link_census(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def search_person(args: dict):
    """Search for persons."""
    try:
        conn = connect_rmtree(RMTREE_DB)
        cursor = conn.cursor()

        conditions = []
        params = []

        if args.get("surname"):
            conditions.append("n.Surname LIKE ?")
            params.append(f"%{args['surname']}%")

        if args.get("given"):
            conditions.append("n.Given LIKE ?")
            params.append(f"%{args['given']}%")

        if args.get("birthplace"):
            conditions.append("""
                EXISTS (SELECT 1 FROM EventTable e
                        JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                        WHERE e.OwnerID = p.PersonID AND e.EventType = 1
                        AND pl.Name LIKE ?)
            """)
            params.append(f"%{args['birthplace']}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        limit = args.get("limit", 20)

        cursor.execute(f"""
            SELECT p.PersonID, n.Given, n.Surname, p.Sex,
                   (SELECT e.Date FROM EventTable e
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
                   (SELECT pl.Name FROM EventTable e
                    LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace
            FROM PersonTable p
            JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
            WHERE {where_clause}
            ORDER BY n.Surname, Birth
            LIMIT ?
        """, params + [limit])

        results = []
        for row in cursor.fetchall():
            rin, given, surname, sex, birth, birthplace = row
            birth_year = parse_year(birth)

            # Filter by birth year range if specified
            if args.get("birth_year_min") and birth_year:
                if int(birth_year) < args["birth_year_min"]:
                    continue
            if args.get("birth_year_max") and birth_year:
                if int(birth_year) > args["birth_year_max"]:
                    continue

            results.append({
                "rin": rin,
                "given": given or "",
                "surname": surname or "",
                "sex": "M" if sex == 0 else "F" if sex == 1 else "?",
                "birth_year": birth_year,
                "birthplace": birthplace or ""
            })

        conn.close()
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_person(args: dict):
    """Get person details."""
    try:
        rin = args["rin"]
        conn = connect_rmtree(RMTREE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.PersonID, n.Given, n.Surname, p.Sex,
                   (SELECT e.Date FROM EventTable e
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as Birth,
                   (SELECT pl.Name FROM EventTable e
                    LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 1) as BirthPlace,
                   (SELECT e.Date FROM EventTable e
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as Death,
                   (SELECT pl.Name FROM EventTable e
                    LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
                    WHERE e.OwnerID = p.PersonID AND e.EventType = 2) as DeathPlace,
                   CAST(p.Note AS TEXT) as Note
            FROM PersonTable p
            JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
            WHERE p.PersonID = ?
        """, (rin,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return [TextContent(type="text", text=f"RIN {rin} not found")]

        result = {
            "rin": row[0],
            "given": row[1] or "",
            "surname": row[2] or "",
            "sex": "M" if row[3] == 0 else "F" if row[3] == 1 else "?",
            "birth_year": parse_year(row[4]),
            "birthplace": row[5] or "",
            "death_year": parse_year(row[6]),
            "deathplace": row[7] or "",
            "note": (row[8] or "")[:500]
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_family(args: dict):
    """Get family relationships."""
    try:
        rin = args["rin"]
        conn = connect_rmtree(RMTREE_DB)
        cursor = conn.cursor()

        result = {"rin": rin, "parents": [], "spouses": [], "children": [], "siblings": []}

        # Parents
        cursor.execute("""
            SELECT f.FatherID, f.MotherID,
                   (SELECT n.Given || ' ' || n.Surname FROM NameTable n
                    WHERE n.OwnerID = f.FatherID AND n.IsPrimary = 1) as Father,
                   (SELECT n.Given || ' ' || n.Surname FROM NameTable n
                    WHERE n.OwnerID = f.MotherID AND n.IsPrimary = 1) as Mother
            FROM ChildTable c
            JOIN FamilyTable f ON c.FamilyID = f.FamilyID
            WHERE c.ChildID = ?
        """, (rin,))
        parents = cursor.fetchone()
        if parents:
            if parents[0]:
                result["parents"].append({"rin": parents[0], "name": parents[2], "relation": "Father"})
            if parents[1]:
                result["parents"].append({"rin": parents[1], "name": parents[3], "relation": "Mother"})

        # Spouses
        cursor.execute("""
            SELECT
                CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END as SpouseID,
                (SELECT n.Given || ' ' || n.Surname FROM NameTable n
                 WHERE n.OwnerID = CASE WHEN f.FatherID = ? THEN f.MotherID ELSE f.FatherID END
                 AND n.IsPrimary = 1) as SpouseName
            FROM FamilyTable f
            WHERE f.FatherID = ? OR f.MotherID = ?
        """, (rin, rin, rin, rin))
        for sp in cursor.fetchall():
            if sp[0]:
                result["spouses"].append({"rin": sp[0], "name": sp[1]})

        # Children
        cursor.execute("""
            SELECT c.ChildID,
                   (SELECT n.Given || ' ' || n.Surname FROM NameTable n
                    WHERE n.OwnerID = c.ChildID AND n.IsPrimary = 1) as Name
            FROM FamilyTable f
            JOIN ChildTable c ON c.FamilyID = f.FamilyID
            WHERE f.FatherID = ? OR f.MotherID = ?
        """, (rin, rin))
        for ch in cursor.fetchall():
            result["children"].append({"rin": ch[0], "name": ch[1]})

        # Siblings
        cursor.execute("""
            SELECT c2.ChildID,
                   (SELECT n.Given || ' ' || n.Surname FROM NameTable n
                    WHERE n.OwnerID = c2.ChildID AND n.IsPrimary = 1) as Name
            FROM ChildTable c1
            JOIN ChildTable c2 ON c1.FamilyID = c2.FamilyID
            WHERE c1.ChildID = ? AND c2.ChildID != ?
        """, (rin, rin))
        for sib in cursor.fetchall():
            result["siblings"].append({"rin": sib[0], "name": sib[1]})

        conn.close()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def query_census(args: dict):
    """Query census.db."""
    try:
        if not CENSUS_DB.exists():
            return [TextContent(type="text", text="census.db not found")]

        conn = sqlite3.connect(str(CENSUS_DB))
        cursor = conn.cursor()

        conditions = []
        params = []

        if args.get("surname"):
            conditions.append("cp.surname LIKE ?")
            params.append(f"%{args['surname']}%")

        if args.get("census_year"):
            conditions.append("pg.census_year = ?")
            params.append(args["census_year"])

        if args.get("state"):
            conditions.append("pg.state LIKE ?")
            params.append(f"%{args['state']}%")

        if args.get("unlinked_only"):
            conditions.append("rl.link_id IS NULL")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT cp.person_id, cp.full_name, pg.census_year, pg.state, pg.county,
                   pg.page_number, cp.line_number, rl.rmtree_person_id as RIN
            FROM census_person cp
            JOIN census_page pg ON cp.page_id = pg.page_id
            LEFT JOIN rmtree_link rl ON cp.person_id = rl.census_person_id
            WHERE {where_clause}
            ORDER BY pg.census_year, pg.state, cp.surname
            LIMIT 50
        """, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                "census_person_id": row[0],
                "full_name": row[1],
                "census_year": row[2],
                "state": row[3],
                "county": row[4],
                "page": row[5],
                "line": row[6],
                "rin": row[7]
            })

        conn.close()
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def link_census(args: dict):
    """Create census-to-RIN link."""
    try:
        if not CENSUS_DB.exists():
            return [TextContent(type="text", text="census.db not found")]

        conn = sqlite3.connect(str(CENSUS_DB))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO rmtree_link
            (census_person_id, rmtree_person_id, rmtree_citation_id,
             match_confidence, match_method, linked_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (
            args["census_person_id"],
            args["rmtree_person_id"],
            args["rmtree_source_id"],
            args.get("confidence", 0.85),
            args.get("method", "manual_analysis")
        ))

        conn.commit()
        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "message": f"Linked census {args['census_person_id']} to RIN {args['rmtree_person_id']}"
        }))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
