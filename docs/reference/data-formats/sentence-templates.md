# RootsMagic 11: Sentence Template Language

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** FactTypeTable, RoleTable
**Field:** FactTypeTable.Sentence

---

## Overview

RootsMagic uses a **sentence template language** to generate narrative text from genealogical facts. Templates combine static text with dynamic variables that are replaced with actual data (names, dates, places, etc.) when generating biographies, reports, and event descriptions.

### Key Concepts

- **Template:** A pattern string with placeholders for data
- **Variable:** A placeholder enclosed in brackets `[variable]` that gets replaced with actual data
- **Modifier:** Optional formatting instructions added to variables using colon syntax `[variable:modifier]`
- **Conditional:** Logic to show/hide text based on whether data exists
- **Choice:** Select between alternative text based on context (gender, singular/plural)

---

## Basic Syntax

### Static Text

Plain text appears as-is in the output:

```
was born
```

### Variables

Variables are enclosed in square brackets and replaced with data:

```
[person] was born [Date] [Place].
```

**Output:** "John Smith was born 15 May 1850 Baltimore, Maryland."

### Optional Sections

Text enclosed in angle brackets `< >` is shown only if the variable inside has a value:

```
[person] was born< [Date]>< [Place]>.
```

**Examples:**
- With date and place: "John Smith was born 15 May 1850 Baltimore, Maryland."
- Date only: "John Smith was born 15 May 1850."
- No date or place: "John Smith was born."

---

## Variable Reference

### Core Variables

| Variable | Description | Example Output |
|----------|-------------|----------------|
| `[person]` | Person's name (lowercase context) | "John Smith" |
| `[Person]` | Person's name (sentence start) | "John Smith" |
| `[Date]` | Event date | "15 May 1850" |
| `[Place]` | Event place | "Baltimore, Maryland" |
| `[PlaceDetails]` | Additional place information | "St. Paul's Church" |
| `[Desc]` | Event description/detail field | varies by event |
| `[couple]` | Couple names | "John Smith and Mary Jones" |
| `[Contact]` | Contact person | "Jane Smith" |
| `[Official]` | Official/celebrant name | "Rev. Thomas Brown" |

### Variable Modifiers

Modifiers change how variables are displayed. Syntax: `[variable:modifier]`

#### Person Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `[person:first]` | Given name only | "John" |
| `[person:Given:Surname]` | Full name format | "John Smith" |
| `[Person:Full]` | Full formal name | "John William Smith" |
| `[Person:Casual]` | Casual name form | "John" |
| `[Person:Caps:HeShe]` | Capitalized pronoun | "He" |
| `[Person:HeShe:CAPS]` | All-caps pronoun | "HE" |
| `[person:Age]` | Person's age at event | "35" or "35 years" |
| `[Person:Age:At:Caps]` | Age with "At" prefix | "At 35" |
| `[person:poss]` | Possessive pronoun (his/her) | "his" |
| `[person:hisher]` | Possessive pronoun variant | "his" |
| `[Person:Poss]` | Capitalized possessive | "His" |

#### Date Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `[Date:Plain]` | Plain date format | "May 15, 1850" |
| `[Date:on]` | With "on" preposition | "on 15 May 1850" |
| `[date:year]` | Year only | "1850" |

#### Place Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `[Place:Plain]` | Plain format | "Baltimore, Maryland" |
| `[Place:plain]` | Lowercase plain format | "baltimore, maryland" |
| `[Place:Short]` | Shortened form | "Baltimore, MD" |
| `[place:short]` | Lowercase short | "baltimore, md" |
| `[Place:First]` | First element only | "Baltimore" |
| `[Place:Full]` | Complete hierarchy | "Baltimore, Baltimore County, Maryland, USA" |
| `[PlaceDetails:plain]` | Plain place details | "St. Paul's Church" |
| `[placedetails:ln]` | Place details (lowercase) | "st. paul's church" |

#### Description Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `[Desc:A]` | With article (a/an) | "a farmer" |
| `[Desc:NoCaps]` | No capitalization | "farmer" |
| `[desc:plain]` | Plain lowercase | "farmer" |

---

## Conditional Logic

### Basic Conditional: `<?...>`

Show content only if a variable has a value:

```
<?[Desc]|[person] was [Desc:A].|[person] had no occupation.>
```

**Syntax:** `<?[variable]|text if present|text if absent>`

**Examples:**
- If Desc = "farmer": "John Smith was a farmer."
- If Desc is empty: "John Smith had no occupation."

### Conditional with Embedded Variables

```
<?[Desc]|[person] owned property valued at [Desc].|[person] owned no property.>
```

**Output:**
- With value: "John Smith owned property valued at $500."
- Without value: "John Smith owned no property."

### Comparison Conditional

```
<?[Desc]=Inv|Inventory|[Desc]>
```

**Syntax:** `<?[variable]=value|text if equal|text if not equal>`

**Output:**
- If Desc = "Inv": "Inventory"
- If Desc = "Will": "Will"

### Multi-Value Conditional

```
<?[Desc]|[Desc]|will>
```

**Syntax:** `<?[variable]|use variable value|default text>`

**Output:**
- If Desc = "codicil": "codicil"
- If Desc is empty: "will"

### Block Conditional

Templates can have multi-line conditional blocks:

```
<?
|On [Date], the <i>[Desc]</i> newspaper published the following article:

>
```

**Note:** Empty condition before `|` means "if any data exists in the fact"

---

## Choice Expressions

### Gender-Based Choices

```
<himself|herself>
<He|She>
<his|her>
```

**Syntax:** `<male option|female option>`

The system selects based on the person's sex field.

**Example:**
```
[person] described <himself|herself> as [Desc].
```

**Output:**
- Male: "John Smith described himself as tall."
- Female: "Mary Smith described herself as tall."

### Singular/Plural Choices

```
<#Couple#was|were>
```

**Syntax:** `<#Context#singular|plural>`

**Example:**
```
[couple] <#Couple#was|were> married [Date].
```

**Output:**
- One person: "John Smith was married 15 May 1850."
- Couple: "John Smith and Mary Jones were married 15 May 1850."

---

## Complete Template Examples

### Simple Template (Birth)

```
[person] was born< [Date]>< [PlaceDetails]>< [Place]>.
```

**Possible outputs:**
- Full data: "John Smith was born 15 May 1850 at home Baltimore, Maryland."
- Date only: "John Smith was born 15 May 1850."
- Place only: "John Smith was born Baltimore, Maryland."
- Minimal: "John Smith was born."

### Complex Template (Death)

```
[person] died< of [Desc]>< [Date]>< [person:Age]>< [PlaceDetails]>< [Place]>.
```

**Output:** "John Smith died of pneumonia 3 January 1920 aged 69 at home Baltimore, Maryland."

### Conditional Template (Occupation)

```
In <?[Desc]|[date:year], [person] was [Desc:A]< [Place]>. [Person:HeShe:CAPS] worked for [PlaceDetails:plain].|[person] listed no occupation< [Date]>.>
```

**With occupation:**
"In 1880, John Smith was a farmer Baltimore, Maryland. HE worked for John Brown."

**Without occupation:**
"John Smith listed no occupation 1880."

### Multi-Line Template (Obituary)

```
<?
|An obituary was published for [person] [date] in the <i>[desc]</i> [place:short]. It reads:

>
```

**Output:**
"An obituary was published for John Smith 5 Jan 1920 in the *Baltimore Sun* Baltimore, MD. It reads:

"

### Family Event Template (Marriage)

```
[couple] <#Couple#was|were> married< [Date]>< [PlaceDetails]>< [Place]>.
```

**Output:** "John Smith and Mary Jones were married 20 June 1875 St. Paul's Church Baltimore, Maryland."

### Military Registration Template

```
On [Date:Plain], [Person] registered for the World War I military draft while residing [Place]. [Person:Age:At:Caps], his physical appearance is described as: [placedetails:plain].
```

**Output:** "On June 5, 1917, John Smith registered for the World War I military draft while residing Baltimore, Maryland. At 35, his physical appearance is described as: tall, brown hair, blue eyes."

---

## HTML/Markup in Templates

Templates can include HTML formatting:

```
<i>[Desc]</i>
<b>[person]</b>
```

**Common tags:**
- `<i>...</i>` - Italics (for newspaper names, book titles)
- `<b>...</b>` - Bold
- Newlines - Line breaks in output

---

## Special Patterns

### Empty Templates

Some fact types have placeholder text:

```
[NEED TO DEFINE SENTENCE: Arrival]
[NEED TO DEFINE SENTENCE: Award]
[NEED TO DEFINE SENTENCE: Letter]
```

These indicate the template is not yet defined and needs customization.

### Property Transfer Template

```
[Person:Poss] family moved<?[Desc]| from [Desc]> to <[Place:Plain]> <[Date:on]>.
```

**Output:**
- With origin: "His family moved from Virginia to Baltimore, Maryland on 15 May 1850."
- Without origin: "His family moved to Baltimore, Maryland on 15 May 1850."

---

## Template Processing Rules

### Order of Evaluation

1. **Variable substitution** - Replace `[variable]` with actual data
2. **Modifier application** - Apply `:modifier` transformations
3. **Optional section evaluation** - Show/hide `< >` sections based on data presence
4. **Conditional evaluation** - Process `<?...>` logic
5. **Choice selection** - Pick from `<option1|option2>` based on context

### Whitespace Handling

- Multiple spaces collapse to single space
- Leading/trailing spaces in optional sections are trimmed
- Newlines in templates become newlines in output

### Empty Variable Behavior

- If `[variable]` is empty, it's replaced with empty string
- `< [variable]>` section is omitted entirely if variable is empty
- `<?[variable]|text if present|text if absent>` uses the "absent" branch

---

## Parsing Algorithm (Pseudocode)

```python
def render_sentence_template(template, data):
    """
    Render a sentence template with actual data.

    Args:
        template: Template string from FactTypeTable.Sentence
        data: Dictionary with keys like 'Date', 'Place', 'Desc', etc.

    Returns:
        Rendered sentence string
    """
    result = template

    # 1. Process conditionals <?...>
    result = process_conditionals(result, data)

    # 2. Process choices <option1|option2>
    result = process_choices(result, data)

    # 3. Process optional sections < >
    result = process_optional_sections(result, data)

    # 4. Replace variables [variable] and [variable:modifier]
    result = replace_variables(result, data)

    # 5. Clean up whitespace
    result = clean_whitespace(result)

    return result

def process_conditionals(template, data):
    """Handle <?[var]|if_present|if_absent> patterns."""
    # Find all <?...> blocks
    # Evaluate condition
    # Replace with appropriate branch
    pass

def process_choices(template, data):
    """Handle <option1|option2> patterns based on context."""
    # Check for #Couple# markers (singular/plural)
    # Check person gender for pronouns
    # Select appropriate option
    pass

def process_optional_sections(template, data):
    """Handle < [var]> patterns - show only if var has value."""
    # Find all < > blocks
    # Check if variables inside have values
    # Keep or remove section
    pass

def replace_variables(template, data):
    """Replace [variable:modifier] with actual values."""
    # Find all [var] and [var:mod] patterns
    # Look up value in data
    # Apply modifier transformations
    # Substitute into template
    pass
```

---

## Modifier Implementation Examples

### Python: Apply Person Modifiers

```python
def apply_person_modifier(person_name, modifier, person_sex):
    """Apply modifier to person name."""

    if modifier == 'first':
        # Return given name only
        return person_name.split()[0]

    elif modifier == 'Age':
        # Calculate age from birth/death dates
        return calculate_age(person_name)

    elif modifier == 'Age:At:Caps':
        age = calculate_age(person_name)
        return f"At {age}"

    elif modifier == 'poss' or modifier == 'hisher':
        # Possessive pronoun
        return 'his' if person_sex == 0 else 'her'

    elif modifier == 'Poss':
        return 'His' if person_sex == 0 else 'Her'

    elif modifier == 'HeShe:CAPS':
        return 'HE' if person_sex == 0 else 'SHE'

    elif modifier == 'Casual':
        # Use given name
        return person_name.split()[0]

    # ... more modifiers

    return person_name
```

### Python: Process Optional Sections

```python
import re

def process_optional_sections(template, data):
    """Remove optional sections if variables are empty."""

    # Pattern: < [variable] optional text>
    pattern = r'<([^>]+)>'

    def should_include(match):
        content = match.group(1)

        # Find variables in this section
        vars_in_section = re.findall(r'\[([^\]]+)\]', content)

        # Keep section if any variable has a value
        for var in vars_in_section:
            var_name = var.split(':')[0]  # Remove modifiers
            if data.get(var_name):
                return content

        # All variables empty, remove section
        return ''

    result = re.sub(pattern, should_include, template)
    return result
```

### Python: Process Conditionals

```python
def process_conditionals(template, data):
    """Handle <?[var]|if_present|if_absent> patterns."""

    pattern = r'<\?([^|>]+)\|([^|>]+)(?:\|([^>]+))?>'

    def evaluate_condition(match):
        condition = match.group(1).strip()
        if_present = match.group(2)
        if_absent = match.group(3) or ''

        # Check for comparison: [Desc]=Inv
        if '=' in condition:
            var, value = condition.split('=')
            var_name = var.strip('[]')
            actual_value = data.get(var_name, '')
            return if_present if actual_value == value else if_absent

        # Check for empty condition (block conditional)
        if not condition.strip():
            # Show if_present if any fact data exists
            return if_present if data else if_absent

        # Standard conditional: <?[var]|...>
        var_name = condition.strip('[]').split(':')[0]
        has_value = bool(data.get(var_name))
        return if_present if has_value else if_absent

    result = re.sub(pattern, evaluate_condition, template)
    return result
```

---

## Common Template Patterns

### Pattern 1: Basic Event

```
[person] <verb>< [Date]>< [PlaceDetails]>< [Place]>.
```

Used for: Birth, Baptism, Burial, Cremation, etc.

### Pattern 2: Event with Cause

```
[person] <verb>< of [Desc]>< [Date]>< [PlaceDetails]>< [Place]>.
```

Used for: Death ("died of pneumonia")

### Pattern 3: Event with Age

```
[person] <verb>< [Date]>< [person:Age]>< [PlaceDetails]>< [Place]>.
```

Used for: Death, Census records

### Pattern 4: Couple Event

```
[couple] <#Couple#singular|plural> <verb>< [Date]>< [PlaceDetails]>< [Place]>.
```

Used for: Marriage, Divorce, Engagement

### Pattern 5: Conditional Description

```
<?[Desc]|[person] had [Desc]< [Date]>.|[person] had no <item>< [Date]>.>
```

Used for: Occupation, Property, Education

### Pattern 6: Document Citation

```
<?
|[person] <action> [date] in the <i>[desc]</i> [place]. It reads:

>
```

Used for: Obituaries, News articles, Letters

---

## Notes for AI Agents

1. **Templates are stored in FactTypeTable.Sentence** - one template per fact type

2. **Variables are case-sensitive** - `[person]` ≠ `[Person]`

3. **Whitespace matters** - Optional sections preserve internal spacing

4. **Gender comes from PersonTable.Sex** - 0=Male, 1=Female, 2=Unknown

5. **Age calculation requires birth date** - from separate fact, not always available

6. **Place modifiers affect hierarchy display**:
   - `:Full` = all levels
   - `:Short` = abbreviated
   - `:First` = first element only

7. **Couple context** - determined by number of principals in family fact

8. **Some templates use newlines** - preserve line breaks in output

9. **HTML tags are literal** - output may need HTML rendering

10. **Missing templates** - fact types with `[NEED TO DEFINE SENTENCE...]` need custom templates

---

## Related Documentation

- **RM11_Schema_Reference.md** - FactTypeTable structure
- **RM11_DataDef.yaml** - FactTypeTable field definitions
- **RM11_Date_Format.md** - Date encoding for [Date] variables
- **RM11_Place_Format.md** - Place structure for [Place] variables (TBD)

---

## Summary

RootsMagic's sentence template language provides a powerful, flexible system for generating narrative text from structured genealogical data. Key features include:

- **Variable substitution** with modifiers for formatting
- **Conditional logic** to handle missing data gracefully
- **Gender/number agreement** through choice expressions
- **Optional sections** that appear only when data is present
- **HTML formatting** for rich text output

Understanding this template language is essential for generating quality biographies, timelines, and narrative reports from RootsMagic databases.

---

**End of Document**
