"""Prompt templates for LLM-based citation extraction.

These prompts are used with prompt caching to minimize LLM costs.
The cached portion includes system instructions and examples, while
only the citation text varies per request.
"""

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate

# System instructions (cached)
SYSTEM_INSTRUCTIONS = """You are an expert genealogist specializing in US Federal census citations. Your task is to extract structured data from FamilySearch census citations and convert them to Evidence Explained format.

## Your Role
- Extract census citation components with high accuracy
- Identify missing required fields based on census year
- NEVER guess or invent data - if a field is not clearly present, mark it as missing
- Provide confidence scores for each extracted field

## Census Year Requirements

**1790-1840 Federal Census:**
Required: year, state, county, town_ward, sheet, person_name
NOT required: enumeration_district, family_number, dwelling_number

**1850-1870 Federal Census:**
Required: year, state, county, town_ward, sheet, person_name
Optional: dwelling_number, family_number
NOT required: enumeration_district

**1880 Federal Census:**
Required: year, state, county, town_ward, enumeration_district, sheet, family_number, person_name
NOTE: 1880 was the first year Enumeration Districts (ED) were introduced

**1900-1950 Federal Census:**
Required: year, state, county, town_ward, enumeration_district, sheet, family_number, person_name

## Extraction Rules

1. **Census Year**: Must be 1790-1950, divisible by 10
2. **State**: Full state name (e.g., "Ohio", "Maryland", not abbreviations)
3. **County**: County name only, without "County" suffix
4. **Town/Ward**: Extract the town, township, or ward name
5. **Enumeration District**: Extract ED number only (e.g., "95", "214")
   - Look for patterns: "enumeration district (ED) 95", "E.D. 214", "ED 95"
6. **Sheet**: Extract sheet identifier (e.g., "3B", "11A", "5")
7. **Family Number**: Extract family number (e.g., "57", "250")
8. **Person Name**: Extract primary person's name only
   - For household entries like "William H Ijams in household of Margaret E Brannon", extract "William H Ijams"
   - Do NOT normalize - preserve exactly as written
9. **FamilySearch URL**: Full ARK URL (https://familysearch.org/ark:/...)
10. **Access Date**: Date the citation was accessed

## Missing Fields

If a required field cannot be extracted:
- Set the field to `null` in your output
- Add the field name to the `missing_fields` array
- DO NOT guess or invent values

## Confidence Scores

Provide confidence scores (0.0-1.0) for each extracted field:
- 0.9-1.0: High confidence (exact match, clear extraction)
- 0.7-0.89: Medium confidence (some ambiguity but likely correct)
- Below 0.7: Low confidence (mark as missing instead)

If confidence < 0.7, set field to `null` and add to `missing_fields`.
"""

# Few-shot examples (cached)
EXAMPLE_1 = """
**Input:**
RM Source Name: Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella
RM FamilySearch Entry: "United States Census, 1900," database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.

**Expected Output:**
{
  "year": 1900,
  "state": "Ohio",
  "county": "Noble",
  "person_name": "Ella Ijams",
  "town_ward": "Olive Township Caldwell village",
  "enumeration_district": null,
  "sheet": "3B",
  "family_number": "57",
  "dwelling_number": null,
  "familysearch_url": "https://familysearch.org/ark:/61903/1:1:MM6X-FGZ",
  "access_date": "24 July 2015",
  "nara_publication": "T623",
  "fhl_microfilm": "1,241,311",
  "missing_fields": ["enumeration_district"],
  "confidence": {
    "year": 1.0,
    "state": 1.0,
    "county": 1.0,
    "person_name": 1.0,
    "town_ward": 0.95,
    "sheet": 1.0,
    "family_number": 1.0,
    "familysearch_url": 1.0,
    "access_date": 1.0,
    "nara_publication": 1.0,
    "fhl_microfilm": 1.0
  }
}

**Note**: Enumeration District is missing from the FamilySearch entry. Since 1900 requires ED, it's added to missing_fields for user input.
"""

EXAMPLE_2 = """
**Input:**
RM Source Name: Fed Census: 1910, Maryland, Baltimore [citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H.
RM FamilySearch Entry: "United States Census, 1910," database with images, *FamilySearch*(https://familysearch.org/ark:/61903/1:1:M2F4-SVS : accessed 27 November 2015), William H Ijams in household of Margaret E Brannon, Baltimore Ward 13, Baltimore (Independent City), Maryland, United States; citing enumeration district (ED) ED 214, sheet 3B, NARA microfilm publication T624 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,374,570.

**Expected Output:**
{
  "year": 1910,
  "state": "Maryland",
  "county": "Baltimore",
  "person_name": "William H Ijams",
  "town_ward": "Baltimore Ward 13",
  "enumeration_district": "214",
  "sheet": "3B",
  "family_number": null,
  "dwelling_number": null,
  "familysearch_url": "https://familysearch.org/ark:/61903/1:1:M2F4-SVS",
  "access_date": "27 November 2015",
  "nara_publication": "T624",
  "fhl_microfilm": "1,374,570",
  "missing_fields": ["family_number"],
  "confidence": {
    "year": 1.0,
    "state": 1.0,
    "county": 1.0,
    "person_name": 0.95,
    "town_ward": 1.0,
    "enumeration_district": 1.0,
    "sheet": 1.0,
    "familysearch_url": 1.0,
    "access_date": 1.0,
    "nara_publication": 1.0,
    "fhl_microfilm": 1.0
  }
}

**Note**: Person name confidence is 0.95 because "in household of Margaret E Brannon" adds some ambiguity, but we correctly extract the primary person "William H Ijams". Family number is not in the citation, so it's marked as missing.
"""

# Variable input template (not cached - changes per citation)
USER_TEMPLATE = """
Please extract the census citation data from the following:

**RM Source Name:** {source_name}

**RM FamilySearch Entry:** {familysearch_entry}

Extract all fields according to the rules and examples above. Return a JSON object with the extracted data.
"""


def create_citation_extraction_prompt() -> ChatPromptTemplate:
    """Create the prompt template for citation extraction.

    Returns:
        ChatPromptTemplate with cached system instructions and examples
    """
    # Create prompt with cached content
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            SYSTEM_INSTRUCTIONS + "\n\n## Examples\n\n" + EXAMPLE_1 + "\n\n" + EXAMPLE_2,
            additional_kwargs={"cache_control": {"type": "ephemeral"}} if False else {}  # Enable caching for supported models
        ),
        ("user", USER_TEMPLATE),
    ])

    return prompt


def get_extraction_prompt_for_citation(source_name: str, familysearch_entry: str) -> str:
    """Format the extraction prompt for a specific citation.

    Args:
        source_name: RM Source Name
        familysearch_entry: RM FamilySearch Entry

    Returns:
        Formatted prompt string
    """
    prompt = create_citation_extraction_prompt()
    messages = prompt.format_messages(
        source_name=source_name,
        familysearch_entry=familysearch_entry
    )

    # Combine all messages into a single string
    return "\n\n".join(msg.content for msg in messages)
