# RootsMagic 11 Date Format Specification

This document describes the date field format used in RootsMagic 11 (RM11) database.

## Overview

RootsMagic uses a proprietary 24-character fixed-width format to store dates with various levels of precision, modifiers, and qualifiers. This format can represent:

- Complete and partial dates (with or without day, month, or year)
- Date ranges
- Directional modifiers (before, after, between, etc.)
- Date qualifiers (about, estimated, calculated, etc.)
- Qualitative certainty levels (certain, probable, possible, etc.)
- BC/AD dates
- Double dates (for calendar transitions)
- Quaker dates
- Free-text dates

## Format Structure

The date format consists of 24 positions with specific meanings:

```
D.+yyyymmdd..+yyyymmdd..
│││││││││││││││││││││││└─ Position 24: Second date qualifier (for ranges)
││││││││││││││││││││││└── Position 23: Second date double date indicator
│││││││││││││││││││└└──── Positions 21-22: Second date day (00-31)
││││││││││││││││└└──────── Positions 19-20: Second date month (00-12)
│││││││││││└└└└──────────── Positions 15-18: Second date year (0000-9999)
││││││││││└──────────────── Position 14: Second date era (+/-)
│││││││││└───────────────── Position 13: First date qualifier
││││││││└────────────────── Position 12: First date double date indicator
│││││└└──────────────────── Positions 10-11: First date day (00-31)
││││└└────────────────────── Positions 8-9: First date month (00-12)
│└└└└──────────────────────── Positions 4-7: First date year (0000-9999)
││────────────────────────── Position 3: First date era (+/-)
│└────────────────────────── Position 2: Date modifier
└─────────────────────────── Position 1: Date type
```

## Position Definitions

### Position 1: Date Type

Defines the fundamental type of date being stored.

| Character | Meaning | Description |
|-----------|---------|-------------|
| `.` | NULL | Empty/null date, all following positions are null |
| `D` | Standard Date | Non-Quaker standard or recognized date |
| `Q` | Quaker Date | Date in Quaker format |
| `T` | Text Date | Free-form text date (variable length follows) |

**Examples:**
- `.` - NULL date
- `D.+19000101..+00000000..` - Standard date: 1 Jan 1900
- `Q.+15880512..+00000000..` - Quaker date: 12da 5mo 1588
- `Tthe first Wednesday after the big fire in 1900` - Text date

### Position 2: Date Modifier

Specifies directional or range modifiers for the date.

| Character | Meaning | Keyword(s) |
|-----------|---------|------------|
| `.` | None | Complete or partial date without modifier |
| `-` | Range | Date range using "–" (en dash) |
| `A` | After | Aft |
| `B` | Before | Bef |
| `F` | From | From |
| `I` | Since | Since |
| `O` | Or | Or |
| `R` | Between/And | Bet...and |
| `S` | From/To | From...to |
| `T` | To | To |
| `U` | Until | Until |
| `Y` | By | By |

**Examples:**
- `D.+19000101..+00000000..` - Plain date: 1 Jan 1900
- `DB+19000101..+00000000..` - Bef 1 Jan 1900
- `DA+19000101..+00000000..` - Aft 1 Jan 1900
- `DR+19000101..+19000105..` - Bet 1 Jan 1900 and 5 Jan 1900
- `DO+19000101..+19000105..` - 1 Jan 1900 or 5 Jan 1900

### Position 3: First Date Era

Indicates whether the first date is BC or AD.

| Character | Meaning |
|-----------|---------|
| `+` | AD (Anno Domini) |
| `-` | BC (Before Christ) |

**Examples:**
- `D.+19000101..+00000000..` - 1 Jan 1900 AD
- `D.-19000101..+00000000..` - 1 Jan 1900 BC

### Positions 4-7: First Date Year

Four-digit year (0000-9999).

- `0000` if partial date without year specified (e.g., "1 Jan", "Jan")
- `yyyy` otherwise (e.g., `1900`, `2024`)

**Examples:**
- `D.+19000101..+00000000..` - Year 1900
- `D.+00000101..+00000000..` - No year specified (just "1 Jan")
- `D.+00000100..+00000000..` - No year specified (just "Jan")

### Positions 8-9: First Date Month

Two-digit month (00-12).

- `00` if partial date without month specified (e.g., "1900", "1 ??? 1900")
- `01` through `12` for January through December

**Examples:**
- `D.+19000101..+00000000..` - January (month 01)
- `D.+19000001..+00000000..` - Unknown month: "1 ??? 1900"
- `D.+19000000..+00000000..` - No month specified: "1900"

### Positions 10-11: First Date Day

Two-digit day (00-31).

- `00` if partial date without day specified (e.g., "Jan 1900", "1900", "Jan")
- `01` through `31` for specific days

**Examples:**
- `D.+19000101..+00000000..` - Day 1
- `D.+19000100..+00000000..` - No day specified: "Jan 1900"

### Position 12: First Date Double Date Indicator

Used for double dates during calendar transitions (Julian to Gregorian).

| Character | Meaning |
|-----------|---------|
| `/` | Double date (e.g., 1583/84) |
| `.` | Not a double date |

**Example:**
- `D.+15830101/.+00000000..` - 1 Jan 1583/84

### Position 13: First Date Qualifier

Date qualifiers and certainty modifiers.

| Character | Meaning | Display |
|-----------|---------|---------|
| `.` | None | No qualifier |
| `?` | Maybe | Maybe |
| `1` | Perhaps | Prhps |
| `2` | Apparently | Appar |
| `3` | Likely | Lkly |
| `4` | Possibly | Poss |
| `5` | Probably | Prob |
| `6` | Certainly | Cert |
| `A` | About | Abt |
| `C` | Circa | Ca |
| `E` | Estimated | Est |
| `L` | Calculated | Calc |
| `S` | Say | Say |

**Examples:**
- `D.+19000101.A+00000000..` - Abt 1 Jan 1900
- `D.+19000101.E+00000000..` - Est 1 Jan 1900
- `D.+19000101.5+00000000..` - Prob 1 Jan 1900
- `D.+19000101.?+00000000..` - Maybe 1 Jan 1900

### Position 14: Second Date Era

For date ranges only.

| Character | Meaning |
|-----------|---------|
| `+` | AD (for range) or N/A (for single dates) |
| `-` | BC (for range) |

### Positions 15-18: Second Date Year

Four-digit year for the second date in a range.

- `0000` if not a range
- `yyyy` for range end year

**Example:**
- `DR+19000101..+19000105..` - Range from 1900 to 1900

### Positions 19-20: Second Date Month

Two-digit month for the second date in a range.

- `00` if not a range
- `01` through `12` for range end month

**Example:**
- `DR+19000101..+19000105..` - Range ending in January (month 01)

### Positions 21-22: Second Date Day

Two-digit day for the second date in a range.

- `00` if not a range
- `01` through `31` for range end day

**Example:**
- `DR+19000101..+19000105..` - Range ending on day 5

### Position 23: Second Date Double Date Indicator

For double dates on the second date of a range.

| Character | Meaning |
|-----------|---------|
| `/` | Double date on range end |
| `.` | Not a double date |

### Position 24: Second Date Qualifier

Date qualifiers for the second date in a range.

Uses same values as Position 13:
- `.`, `?`, `1`-`6`, `A`, `C`, `E`, `L`, `S`

## Complete Examples

### Simple Dates

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| 1 Jan 1900 | `D.+19000101..+00000000..` | Complete date |
| Jan 1900 | `D.+19000100..+00000000..` | Month and year only |
| 1900 | `D.+19000000..+00000000..` | Year only |
| 1 Jan | `D.+00000101..+00000000..` | Day and month only |
| Jan | `D.+00000100..+00000000..` | Month only |
| 1 ??? 1900 | `D.+19000001..+00000000..` | Day and year, unknown month |

### BC Dates

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| 1 Jan 1900 BC | `D.-19000101..+00000000..` | BC date |

### Double Dates

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| 1 Jan 1583/84 | `D.+15830101/.+00000000..` | Calendar transition double date |

### Quaker Dates

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| 12da 5mo 1588 | `Q.+15880512..+00000000..` | Quaker date format |

### Directional Modifiers (Single Date)

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| Bef 1 Jan 1900 | `DB+19000101..+00000000..` | Before |
| By 1 Jan 1900 | `DY+19000101..+00000000..` | By |
| To 1 Jan 1900 | `DT+19000101..+00000000..` | To |
| Until 1 Jan 1900 | `DU+19000101..+00000000..` | Until |
| From 1 Jan 1900 | `DF+19000101..+00000000..` | From |
| Since 1 Jan 1900 | `DI+19000101..+00000000..` | Since |
| Aft 1 Jan 1900 | `DA+19000101..+00000000..` | After |

### Date Ranges

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| Bet 1 Jan 1900 and 5 Jan 1900 | `DR+19000101..+19000105..` | Between...and |
| From 1 Jan 1900 to 5 Jan 1900 | `DS+19000101..+19000105..` | From...to |
| 1 Jan 1900–5 Jan 1900 | `D-+19000101..+19000105..` | Range with en dash |
| 1 Jan 1900 or 5 Jan 1900 | `DO+19000101..+19000105..` | Alternativ e dates |

### Date Qualifiers

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| Abt 1 Jan 1900 | `D.+19000101.A+00000000..` | About |
| Est 1 Jan 1900 | `D.+19000101.E+00000000..` | Estimated |
| Calc 1 Jan 1900 | `D.+19000101.L+00000000..` | Calculated |
| Ca 1 Jan 1900 | `D.+19000101.C+00000000..` | Circa |
| Say 1 Jan 1900 | `D.+19000101.S+00000000..` | Say |

### Qualitative Modifiers

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| Cert 1 Jan 1900 | `D.+19000101.6+00000000..` | Certainly |
| Prob 1 Jan 1900 | `D.+19000101.5+00000000..` | Probably |
| Poss 1 Jan 1900 | `D.+19000101.4+00000000..` | Possibly |
| Lkly 1 Jan 1900 | `D.+19000101.3+00000000..` | Likely |
| Appar 1 Jan 1900 | `D.+19000101.2+00000000..` | Apparently |
| Prhps 1 Jan 1900 | `D.+19000101.1+00000000..` | Perhaps |
| Maybe 1 Jan 1900 | `D.+19000101.?+00000000..` | Maybe |

### Special Cases

| Display | Encoded Format | Description |
|---------|---------------|-------------|
| NULL | `.` | Empty/null date |
| the first Wednesday after the big fire in 1900 | `Tthe first Wednesday after the big fire in 1900` | Free-text date |

## Parsing Logic

### Pseudocode for Date Parser

```python
def parse_rm_date(date_string):
    if not date_string or date_string == '.':
        return {'type': 'null', 'display': 'NULL'}
    
    date_type = date_string[0]
    
    if date_type == 'T':
        return {
            'type': 'text',
            'text': date_string[1:],
            'display': date_string[1:]
        }
    
    if date_type in ['D', 'Q']:
        modifier = date_string[1]
        era1 = date_string[2]
        year1 = date_string[3:7]
        month1 = date_string[7:9]
        day1 = date_string[9:11]
        double1 = date_string[11]
        qualifier1 = date_string[12]
        era2 = date_string[13]
        year2 = date_string[14:18]
        month2 = date_string[18:20]
        day2 = date_string[20:22]
        double2 = date_string[22]
        qualifier2 = date_string[23] if len(date_string) > 23 else '.'
        
        # Build date components
        date1 = build_date(era1, year1, month1, day1, double1, qualifier1)
        
        # Check if this is a range
        if modifier in ['R', 'S', '-', 'O'] and year2 != '0000':
            date2 = build_date(era2, year2, month2, day2, double2, qualifier2)
            return format_date_range(modifier, date1, date2)
        elif modifier != '.':
            return format_modified_date(modifier, date1)
        else:
            return format_simple_date(date1, date_type == 'Q')
    
    return {'type': 'unknown', 'raw': date_string}
```

## Notes

- The format is **fixed-width 24 characters** for standard/Quaker dates
- Text dates are **variable length** starting with `T`
- All numeric fields use **zero-padding**
- The format supports **nested qualifiers** (qualifier on both dates in a range)
- **Partial dates** use `00` or `0000` for unspecified components
- The format is **case-sensitive**

## References

- Source: RootsMagic 11 Data Definition (RM11DataDef-V11_0_0-20250914.xlsx)
- Worksheet: "Date"
- Version: 11.0.0
- Date: 2025-09-14
