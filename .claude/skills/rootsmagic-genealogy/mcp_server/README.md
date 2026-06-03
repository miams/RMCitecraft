# RootsMagic MCP Server

An MCP (Model Context Protocol) server that provides Claude with direct tools for querying RootsMagic databases.

## Installation

1. Install the MCP package:
   ```bash
   uv pip install mcp
   ```

2. Add to your Claude Code settings (`~/.claude/settings.json`):
   ```json
   {
     "mcpServers": {
       "rmtree": {
         "command": "uv",
         "args": [
           "run",
           "--directory", "/Users/miams/Code/RMCitecraft",
           "python",
           ".claude/skills/rootsmagic-genealogy/mcp_server/rmtree_server.py"
         ],
         "env": {
           "RMTREE_DB": "/Users/miams/Code/RMCitecraft/data/Iiams.rmtree"
         }
       }
     }
   }
   ```

3. Restart Claude Code

## Available Tools

Once installed, Claude will have access to these tools:

### rmtree_search_person
Search for persons in the database.

**Parameters:**
- `surname` (string): Surname to search (partial match)
- `given` (string): Given name to search (partial match)
- `birth_year_min` (integer): Minimum birth year
- `birth_year_max` (integer): Maximum birth year
- `birthplace` (string): Birthplace to search (partial match)
- `limit` (integer): Maximum results (default: 20)

### rmtree_get_person
Get detailed information about a person.

**Parameters:**
- `rin` (integer, required): RootsMagic person ID

### rmtree_get_family
Get family relationships (parents, spouses, children, siblings).

**Parameters:**
- `rin` (integer, required): RootsMagic person ID

### census_query
Query the census.db sidecar database.

**Parameters:**
- `surname` (string): Surname to search
- `census_year` (integer): Census year (1790, 1800, etc.)
- `state` (string): State name
- `unlinked_only` (boolean): Only show unlinked records

### census_link
Create a link between a census record and a RIN.

**Parameters:**
- `census_person_id` (integer, required): Census person ID
- `rmtree_person_id` (integer, required): RootsMagic RIN
- `rmtree_source_id` (integer, required): RootsMagic SourceID
- `confidence` (number): Match confidence 0.0-1.0 (default: 0.85)
- `method` (string): Match method (default: "manual_analysis")

## Example Usage in Claude

Once installed, you can ask Claude:

> "Search for all persons with surname Iiams born between 1730 and 1760"

Claude will use the `rmtree_search_person` tool automatically.

> "Show me the family of RIN 1561"

Claude will use the `rmtree_get_family` tool.

> "Find unlinked 1790 census records for Maryland"

Claude will use the `census_query` tool.

## Development

To test the server locally:

```bash
cd /Users/miams/Code/RMCitecraft
uv run python .claude/skills/rootsmagic-genealogy/mcp_server/rmtree_server.py
```

The server communicates via stdin/stdout using the MCP protocol.
