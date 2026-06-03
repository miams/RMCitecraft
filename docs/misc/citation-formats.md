# Evidence Explained Citation Formats by Census Year

Templates for the three citation strings (Footnote / ShortFootnote /
Bibliography) that go into `SourceTable.Fields` BLOB, by census year. Based on
Elizabeth Shown Mills, *Evidence Explained*, chapter 6.

## Encoding rules (apply to all years)

The strings as stored in the BLOB are XML `<Value>` content, so:
- `"` → `&quot;`
- `<` → `&lt;`
- `>` → `&gt;`
- `&` → `&amp;`

Italics in the rendered citation:
- `<i>FamilySearch</i>` → stored as `&lt;i&gt;FamilySearch&lt;/i&gt;`
- Italicize: the database/website name on first reference, the database
  publisher of digital images.

URL note: include the full ARK URL and an access date. Project default access
date format: `accessed <D> <Month> <YYYY>` (e.g. "accessed 3 June 2026").

State abbreviation in ShortFootnote uses traditional postal style with periods
(`Co.`, `Pa.`, `N.M.`, `Calif.`, `Ohio` no period because it's already short),
**not** the two-letter USPS code.

---

## 1940 Census (standard format)

Reference example from this project: `SourceID 12721` (Berks Co PA), `12744` (Santa Fe NM).

### Source Name
```
Fed Census: 1940, <State>, <County> [ED <state-ed>, sheet <N>-<A>, line <N>] <Surname>, <Given>
```
Example: `Fed Census: 1940, New Mexico, Santa Fe [ED 25-20A, sheet 12-A, line 5] Iams, John Willis`

### Footnote
```
1940 U.S. census, <County> County, <State>, population schedule, <City/Township>,
enumeration district (ED) <state-ed>, sheet <N>-<A>, line <N>, <Full Name>;
imaged, "United States, Census, 1940," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```
Example:
> *1940 U.S. census, Santa Fe County, New Mexico, population schedule, Santa Fe, enumeration district (ED) 25-20A, sheet 12-A, line 5, John Willis Iams; imaged, "United States, Census, 1940," FamilySearch (https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3 : accessed 3 June 2026).*

### ShortFootnote
```
1940 U.S. census, <County abbr> Co., <State abbr>., <City/Township>, E.D. <state-ed>, sheet <N>-<A>, line <N>, <Full Name>.
```
Example:
> *1940 U.S. census, Santa Fe Co., N.M., Santa Fe, E.D. 25-20A, sheet 12-A, line 5, John Willis Iams.*

### Bibliography
```
U.S. <State>. <County> County. 1940 U.S. Census. Imaged. "United States, Census, 1940." <i>FamilySearch</i>. <ARK> : <YYYY>.
```
Example:
> *U.S. New Mexico. Santa Fe County. 1940 U.S. Census. Imaged. "United States, Census, 1940." FamilySearch. https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3 : 2026.*

### Population schedule note for 1940
Some 1940 templates in this project omit "population schedule" when the city
name carries the information unambiguously. Match the most recent same-year
source in the database for consistency. (When in doubt: keep it — it never
hurts and matches Mills.)

---

## 1950 Census (standard format)

Reference example: `SourceID 12717` (Sherman Imes, Franklin Co OH).

The 1950 schedule uses **stamp number** (printed page stamp) instead of sheet number.

### Source Name
```
Fed Census: 1950, <State>, <County> [ED <state-ed>, stamp <N>, line <N>] <Surname>, <Given>
```
or, if you have sheet number instead of stamp:
```
Fed Census: 1950, <State>, <County> [ED <state-ed>, sheet <N>, line <N>] <Surname>, <Given>
```

### Footnote
```
1950 U.S. census, <County> County, <State>, <City/Township>, enumeration district (ED) <state-ed>, stamp <N>, line <N>, <Full Name>;
imaged, "United States, Census, 1950," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```

### ShortFootnote
```
1950 U.S. census, <County abbr> Co., <State>, <City>, E.D. <state-ed>, stamp <N>, line <N>, <Full Name>.
```

### Bibliography
```
U.S. <State>. <County> County. 1950 U.S. Census. Population Schedule. Imaged. "United States, Census, 1950." <i>FamilySearch</i>. <ARK> : <YYYY>.
```
Note: 1950 Bibliography **adds "Population Schedule."** before "Imaged." compared to 1940. Match the existing project convention.

---

## 1950 Census (experimental sample format)

Special format used for ~5% of the population using individual cards (Form
P-2 / P-8). The cards are photographed in stacks, so the top edge with the ED
stamp is often visible but the card body has handwritten entries.

### Differences from standard 1950
- Sheet number is meaningless (cards aren't on schedule pages).
- Use **stamp only** (the household / dwelling serial number stamped on the card; e.g. `15379`).
- The FamilySearch index leaves "Supervisor District" blank → ED is not exposed
  in the indexed fields. Read it from the image, or **ask the user**.

### Source Name
```
Fed Census: 1950, <State>, <County> [ED <state-ed>, stamp <N>] <Surname>, <Given>
```
Example: `Fed Census: 1950, Ohio, Franklin [ED 94-30, stamp 15379] Iams, John Willis`

### Footnote
```
1950 U.S. census, <County> County, <State>, <City>, enumeration district (ED) <state-ed>, stamp <N>, <Full Name>;
imaged, "United States, Census, 1950," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```
Example:
> *1950 U.S. census, Franklin County, Ohio, Columbus, enumeration district (ED) 94-30, stamp 15379, John Willis Iams; imaged, "United States, Census, 1950," FamilySearch (https://www.familysearch.org/ark:/61903/1:1:6JKY-W4CB : accessed 3 June 2026).*

### ShortFootnote
```
1950 U.S. census, <County abbr> Co., <State>, <City>, E.D. <state-ed>, stamp <N>, <Full Name>.
```
Example:
> *1950 U.S. census, Franklin Co., Ohio, Columbus, E.D. 94-30, stamp 15379, John Willis Iams.*

### Bibliography
Same as standard 1950.

---

## 1930 and 1920 Censuses

Same shape as 1940 — ED, sheet, line. Difference is the database name string
that goes after `imaged,`:

| Year | Database name (italicized literal) | Repository |
|------|------------------------------------|------------|
| 1900 | `"United States Census, 1900"` | FamilySearch |
| 1910 | `"United States Census, 1910"` | FamilySearch |
| 1920 | `"United States Census, 1920"` | FamilySearch |
| 1930 | `"United States Census, 1930"` | FamilySearch |
| 1940 | `"United States, Census, 1940"` | FamilySearch (note the comma) |
| 1950 | `"United States, Census, 1950"` | FamilySearch (note the comma) |

The 1940/1950 entries use a Title-Case version with a comma; earlier years
do not. Verify the exact string by searching existing same-year sources:

```sql
SELECT CAST(Fields AS TEXT) FROM SourceTable
WHERE Name LIKE 'Fed Census: <YEAR>%' LIMIT 1;
```

---

## 1880 Census

- ED introduced for the first time.
- "Page" rather than "sheet" (or use both; standard is the stamped page).
- Line number same as later years.

### Source Name
```
Fed Census: 1880, <State>, <County> [ED <ed-num>, page <N>, line <N>] <Surname>, <Given>
```

### Footnote
```
1880 U.S. census, <County> County, <State>, population schedule, <City/Township>, enumeration district (ED) <N>, page <N>, dwelling <N>, family <N>, line <N>, <Full Name>;
imaged, "United States Census, 1880," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```

Include `dwelling <N>, family <N>` when shown — they were standard fields
through 1930.

---

## 1850-1870 Censuses

- No ED.
- Sheet (or "page" for 1860), dwelling number, family number, line.

### Footnote 1850/1870
```
1850 U.S. census, <County> County, <State>, population schedule, <City/Township>, sheet <N>, dwelling <N>, family <N>, line <N>, <Full Name>;
imaged, "United States Census, 1850," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```

### Footnote 1860 (uses "page" not "sheet")
```
1860 U.S. census, <County> County, <State>, population schedule, <City/Township>, page <N>, family <N>, <Full Name>;
imaged, "United States Census, 1860," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```

---

## 1790-1840 Censuses

- Head of household only — no individual names beyond the head.
- No "population schedule" terminology — there were no separate schedules.
- Tally columns (free white males by age bracket, etc.).
- Page number is the structural identifier.

### Footnote
```
<YEAR> U.S. census, <County> County, <State>, <City/Township>, page <N>, <Head of Household>;
imaged, "United States Census, <YEAR>," <i>FamilySearch</i> (<ARK> : accessed <Date>).
```

For non-head household members (wife, children), the **head of household** is
who you cite — they are the named entry. Their relatives are inferred from age
bracket counts.

---

## Place name formatting in citations

| Context | Format |
|---------|--------|
| Footnote | `<County> County, <State>` (full state name) |
| ShortFootnote | `<County abbr> Co., <State abbr>.` (traditional postal abbr.) |
| Bibliography | `U.S. <State>. <County> County.` |
| Source Name | `<State>, <County>` (Mills-style, in the bracketed locator) |

### County abbreviations (common ones to know)

Most counties have no standard abbreviation — drop nothing, just use the full
name in the ShortFootnote (e.g., "Greene Co.", "Wood Co.").

For longer county names, drop a final article: "Anne Arundel" → "Anne Arundel" (no
shortening); "Saint Louis" → "St. Louis"; "Mount Pleasant" township → "Mt. Pleasant".

### State abbreviations (traditional, with periods)

| State | Abbr. | State | Abbr. |
|-------|-------|-------|-------|
| Alabama | Ala. | Montana | Mont. |
| Alaska | Alaska | Nebraska | Nebr. |
| Arizona | Ariz. | Nevada | Nev. |
| Arkansas | Ark. | New Hampshire | N.H. |
| California | Calif. | New Jersey | N.J. |
| Colorado | Colo. | New Mexico | N.M. |
| Connecticut | Conn. | New York | N.Y. |
| Delaware | Del. | North Carolina | N.C. |
| Florida | Fla. | North Dakota | N.D. |
| Georgia | Ga. | Ohio | Ohio |
| Hawaii | Hawaii | Oklahoma | Okla. |
| Idaho | Idaho | Oregon | Ore. |
| Illinois | Ill. | Pennsylvania | Pa. |
| Indiana | Ind. | Rhode Island | R.I. |
| Iowa | Iowa | South Carolina | S.C. |
| Kansas | Kans. | South Dakota | S.D. |
| Kentucky | Ky. | Tennessee | Tenn. |
| Louisiana | La. | Texas | Tex. |
| Maine | Maine | Utah | Utah |
| Maryland | Md. | Vermont | Vt. |
| Massachusetts | Mass. | Virginia | Va. |
| Michigan | Mich. | Washington | Wash. |
| Minnesota | Minn. | West Virginia | W.Va. |
| Mississippi | Miss. | Wisconsin | Wis. |
| Missouri | Mo. | Wyoming | Wyo. |

### Caption (MultimediaTable.Caption) uses USPS two-letter

The image Caption field uses the modern two-letter USPS code, no period:
`Census: 1940 Fed Census - Santa Fe, NM`. This is project convention, not
Evidence Explained.

---

## Worked end-to-end example

**Input:** FamilySearch ARK `https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3` for John Willis Iams, 1940 census, Santa Fe, NM, ED 25-20A, sheet 12-A, line 5.

**Generated strings:**

Source Name:
```
Fed Census: 1940, New Mexico, Santa Fe [ED 25-20A, sheet 12-A, line 5] Iams, John Willis
```

Footnote (as displayed):
```
1940 U.S. census, Santa Fe County, New Mexico, population schedule, Santa Fe,
enumeration district (ED) 25-20A, sheet 12-A, line 5, John Willis Iams;
imaged, "United States, Census, 1940," FamilySearch
(https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3 : accessed 3 June 2026).
```

Footnote (as stored in Fields BLOB):
```
1940 U.S. census, Santa Fe County, New Mexico, population schedule, Santa Fe, enumeration district (ED) 25-20A, sheet 12-A, line 5, John Willis Iams; imaged, &quot;United States, Census, 1940,&quot; &lt;i&gt;FamilySearch&lt;/i&gt; (https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3 : accessed 3 June 2026).
```

ShortFootnote (as displayed):
```
1940 U.S. census, Santa Fe Co., N.M., Santa Fe, E.D. 25-20A, sheet 12-A, line 5, John Willis Iams.
```

Bibliography (as displayed):
```
U.S. New Mexico. Santa Fe County. 1940 U.S. Census. Imaged.
"United States, Census, 1940." FamilySearch.
https://www.familysearch.org/ark:/61903/1:1:KMRL-VR3 : 2026.
```
