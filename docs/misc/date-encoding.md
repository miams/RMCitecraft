# RootsMagic Date Encoding Reference

RootsMagic uses a 24-character position-coded format for dates.

## Date Format Structure

### Standard Format
```
Position: 0         1         2
          012345678901234567890123
Format:   D.+YYYYMMDD..+00000000..
Example:  D.+18640615..+00000000..
```

### Position Map

| Positions | Field | Description |
|-----------|-------|-------------|
| 0 | Modifier | D=Date, T=Text, O=Other |
| 1 | Unused | Always `.` |
| 2 | Date Type | `+` = Standard, `-` = Before, `~` = About, etc. |
| 3-6 | Year | YYYY (4 digits) |
| 7-8 | Month | MM (01-12) |
| 9-10 | Day | DD (01-31) |
| 11-12 | Unused | Always `..` |
| 13 | Second Date Type | For date ranges |
| 14-17 | Second Year | For date ranges |
| 18-19 | Second Month | For date ranges |
| 20-21 | Second Day | For date ranges |
| 22-23 | Unused | Always `..` |

## Date Modifiers (Position 2)

| Code | Meaning | Example |
|------|---------|---------|
| `+` | Exact date | June 15, 1864 |
| `-` | Before | Before 1864 |
| `~` | About/Circa | About 1864 |
| `<` | Less than | Less than 1864 |
| `>` | Greater than | Greater than 1864 |
| `R` | Date range | 1864-1865 |

## Common Date Patterns

### Full Date
```
D.+18640615..+00000000..
└─┬─┘└──┬──┘
  │     └─ June 15, 1864
  └─ Standard date
```

### Year Only
```
D.+18640000..+00000000..
└─┬─┘└──┬──┘
  │     └─ 1864 (no month/day)
  └─ Standard date
```

### About/Circa
```
D.~18640000..+00000000..
└─┬─┘└──┬──┘
  │     └─ 1864
  └─ About/Circa
```

### Date Range
```
D.R18640101..+18650630..
└─┬─┘└──┬──┘  └──┬──┘
  │     │        └─ To: June 30, 1865
  │     └─ From: Jan 1, 1864
  └─ Range
```

### Before Date
```
D.-18640000..+00000000..
└─┬─┘└──┬──┘
  │     └─ 1864
  └─ Before
```

## Extracting Date Components

### Year Extraction (Most Common)

```python
def extract_year(date_string):
    """Extract year from RootsMagic date string."""
    if date_string and len(date_string) >= 7:
        return date_string[3:7]
    return None

# Example usage
date = "D.+18640615..+00000000.."
year = extract_year(date)  # Returns "1864"
```

### Full Date Parsing

```python
def parse_rm_date(date_string):
    """Parse RootsMagic date into components."""
    if not date_string or len(date_string) < 24:
        return None

    result = {
        'modifier': date_string[0],      # D, T, O
        'type': date_string[2],          # +, -, ~, R, etc.
        'year': date_string[3:7],
        'month': date_string[7:9],
        'day': date_string[9:11],
    }

    # For date ranges
    if result['type'] == 'R':
        result['end_type'] = date_string[13]
        result['end_year'] = date_string[14:18]
        result['end_month'] = date_string[18:20]
        result['end_day'] = date_string[20:22]

    return result

# Example usage
date = "D.+18640615..+00000000.."
parsed = parse_rm_date(date)
# Returns: {'modifier': 'D', 'type': '+', 'year': '1864', 'month': '06', 'day': '15'}
```

### Display Formatting

```python
def format_rm_date(date_string):
    """Format RootsMagic date for display."""
    parsed = parse_rm_date(date_string)
    if not parsed:
        return "Unknown"

    # Handle date types
    prefix = {
        '+': '',
        '-': 'Before ',
        '~': 'About ',
        '<': 'Less than ',
        '>': 'Greater than ',
        'R': ''
    }.get(parsed['type'], '')

    # Format the date
    year = parsed['year']
    month = parsed['month']
    day = parsed['day']

    if month == '00':
        date_str = year
    elif day == '00':
        date_str = f"{month}/{year}"
    else:
        date_str = f"{month}/{day}/{year}"

    # Handle ranges
    if parsed['type'] == 'R':
        end_year = parsed.get('end_year', '')
        end_month = parsed.get('end_month', '00')
        end_day = parsed.get('end_day', '00')

        if end_month == '00':
            end_str = end_year
        elif end_day == '00':
            end_str = f"{end_month}/{end_year}"
        else:
            end_str = f"{end_month}/{end_day}/{end_year}"

        return f"{date_str} - {end_str}"

    return f"{prefix}{date_str}"

# Examples
print(format_rm_date("D.+18640615..+00000000.."))  # "06/15/1864"
print(format_rm_date("D.~18640000..+00000000.."))  # "About 1864"
print(format_rm_date("D.R18640101..+18650630.."))  # "01/01/1864 - 06/30/1865"
```

## SortDate Field

EventTable also contains a `SortDate` field (BIGINT) used for sorting events chronologically.

```sql
-- Get events in chronological order
SELECT EventID, Date, SortDate
FROM EventTable
WHERE OwnerID = 1561
  AND OwnerType = 0
ORDER BY SortDate;
```

**Note:** SortDate is BIGINT, not INTEGER. It's typically an 18-19 digit number.

## Common SQL Patterns

### Find Events in Year Range

```sql
-- Extract year and filter
SELECT e.EventID, e.Date,
       CAST(SUBSTR(e.Date, 4, 4) AS INTEGER) as Year
FROM EventTable e
WHERE e.OwnerID = 1561
  AND e.OwnerType = 0
  AND CAST(SUBSTR(e.Date, 4, 4) AS INTEGER) BETWEEN 1850 AND 1860
ORDER BY e.Date;
```

### Find Events with Unknown Dates

```sql
SELECT e.EventID, e.EventType, ft.Name
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.OwnerID = 1561
  AND e.OwnerType = 0
  AND (e.Date IS NULL OR e.Date = '' OR e.Date = 'D.+00000000..+00000000..')
ORDER BY e.EventType;
```

### Calculate Age at Event

```python
def calculate_age_at_event(birth_date, event_date):
    """Calculate age at event from RootsMagic dates."""
    birth_year = extract_year(birth_date)
    event_year = extract_year(event_date)

    if birth_year and event_year:
        try:
            return int(event_year) - int(birth_year)
        except ValueError:
            return None
    return None

# Example
birth = "D.+18400315..+00000000.."  # March 15, 1840
census = "D.+19000601..+00000000.."  # June 1, 1900
age = calculate_age_at_event(birth, census)  # Returns 60
```

## Text Dates

Some dates may be stored as free-text (modifier='T'):

```
T.+text date value goes here..
```

For text dates:
- Cannot be sorted chronologically
- Cannot extract year reliably
- Display the text portion as-is

## Notes

1. **Always check length** before extracting date components
2. **Year is at positions 3-7** (most commonly used)
3. **Month/Day use 01-31** (not 1-31, always zero-padded)
4. **Empty dates** may be NULL, empty string, or all zeros
5. **SortDate is BIGINT**, not INTEGER
6. **Date ranges** use type 'R' and have both start and end dates
