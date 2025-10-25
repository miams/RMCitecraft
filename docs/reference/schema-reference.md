# RootsMagic 11 Schema Reference

This document provides a comprehensive reference for the RootsMagic 11 SQLite database schema, organized by functional area.

## Overview

The RootsMagic 11 database consists of **31 tables** organized into functional categories:

- **Core Entities**: 4 tables
- **Events and Facts**: 4 tables
- **Sources and Citations**: 4 tables
- **Places**: 3 tables
- **Multimedia**: 2 tables
- **Research Management**: 4 tables
- **External Services**: 2 tables
- **DNA and Health**: 2 tables
- **Relationships**: 2 tables
- **System**: 4 tables

## Database Characteristics

- **Database Type**: SQLite 3
- **Character Encoding**: UTF-8
- **Case Sensitivity**: Custom collation (RMNOCASE) for case-insensitive text fields
- **Date Storage**: TEXT (encoded format) and FLOAT (Julian day for sorting)
- **Modification Tracking**: UTCModDate field in all tables
- **Privacy Support**: IsPrivate flags in applicable tables
- **Proof Standards**: Proof fields for evidence quality tracking

## Key Concepts

### OwnerType/OwnerID Pattern
Many linking tables use polymorphic associations:
- **OwnerType**: Integer enum identifying the entity type
- **OwnerID**: Foreign key to the appropriate table based on OwnerType

Common OwnerType values:
- `0` = Person
- `1` = Family
- `2` = Event
- `3` = Source
- `4` = Citation
- `5` = Place
- `6` = Task
- `7` = Name
- etc.

### BLOB Fields
Structured data stored as XML or binary. All BLOBs use UTF-8 encoding with BOM (EFBBBF).

**Documented BLOB Structures:**
- **SourceTable.Fields** - Template field values (see RM11_BLOB_SourceFields.md)
- **SourceTemplateTable.FieldDefs** - Field definitions (see RM11_BLOB_SourceTemplateFieldDefs.md)
- **CitationTable.Fields** - Citation field values (see RM11_BLOB_CitationFields.md)

**Application Data (not genealogical):**
- **ConfigTable.DataRec** - Application configuration settings
- **PayloadTable.DataRec** - UI metadata (saved searches, groups, prompts)
- **MultimediaTable.Thumbnail** - Image thumbnails

### Date Fields
Two-part system:
- **Date** (TEXT): Encoded date string (see RM11_Date_Format.md)
- **SortDate** (BIGINT): Sortable integer for date ordering

### Modification Tracking
All tables include:
- **UTCModDate** (FLOAT): Coordinated Universal Time as Julian day

## Tables by Category

## Core Entities

### PersonTable

0 = No Parents,\nAny other value = FamilyTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| PersonID | INTEGER | PK | Record Identification Number (RIN) (e.g., 1,2,3,...) |
| UniqueID | TEXT |  | Unique Identification Number assigned to person (e.g., 36 Character\nHexidecimal) |
| Sex | INTEGER |  | 0 = Male, 1 = Female, 2 = Unknown (e.g., 0,1,2) |
| ParentID | INTEGER |  | FK: 0 = No Parents, Any other value = FamilyTable.FamilyID If person has more than 1 set of parents, ... (e.g., 0,1,2,3,...) |
| SpouseID | INTEGER |  | FK: 0 = No Spouse, Any other value = FamilyTable.FamilyID If person has more than 1 spouse, then valu... (e.g., 0,1,2,3,...) |
| Color | INTEGER |  | Set Color for Color Set 1, from Color Coding window: 0 = None,  1 = Red,  2 = Lime,  3 = Blue,  4... (e.g., 0-27) |
| Color1 | INTEGER |  | Color Set 2, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color2 | INTEGER |  | Color Set 3, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color3 | INTEGER |  | Color Set 4, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color4 | INTEGER |  | Color Set 5, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color5 | INTEGER |  | Color Set 6, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color6 | INTEGER |  | Color Set 7, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color7 | INTEGER |  | Color Set 8, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color8 | INTEGER |  | Color Set 9, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Color9 | INTEGER |  | Color Set 10, from Color Coding window: See PersonTable.Color for values (e.g., 0-27) |
| Relate1 | INTEGER |  | Relate1, number of generations from this person to Most Recent Common Ancestor with the person ch... (e.g., 0-999) |
| Relate2 | INTEGER |  | Relate2, number of generations from the person chosen via Tools > Set Relationships to the Most R... (e.g., 0,1,2,3,...) |
| Flags | INTEGER |  | Prefix description added to Set Relationship display as defined by Relate1/Relate2 calculation: 0... (e.g., 0-10) |
| Living | INTEGER |  | Living, from Edit Person window: 0 = Deceased,  1 = Living (e.g., 0,1) |
| IsPrivate | INTEGER |  | Not Implementd (e.g., 0.0) |
| Proof | INTEGER |  | Not implemented (e.g., 0.0) |
| Bookmark | INTEGER |  | Bookmark, from Sidebar Bookmarks view: 0 = Not Bookmarked, 1 = Bookmarked (e.g., 0,1) |
| Note | TEXT |  | Note field from Edit Person screen, Person Fact. User Interface supports line breaks and formatti... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### FamilyTable

Links to PersonID in the PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| FamilyID | INTEGER | PK | Family Identification Number (e.g., 1, 2, 3...) |
| FatherID | INTEGER |  | FK: Links to PersonID in the PersonTable (e.g., 1, 2, 3...) |
| MotherID | INTEGER |  | FK: Links to PersonID in the PersonTable (e.g., 1, 2, 3...) |
| ChildID | INTEGER |  | FK: Links to PersonTable.PersonID of Child last active as the root person in Pedigree view, 0 = No Ch... (e.g., 0, 1, 2,...) |
| HusbOrder | INTEGER |  | Husband Order, from People View, Edit Menu, Rearrange Spouses: 0 if never rearranged (e.g., 0, 1, 2,...) |
| WifeOrder | INTEGER |  | Wife Order, from People View, Edit Menu, Rearrange Spouses: 0 if never rearranged (e.g., 0, 1, 2,...) |
| IsPrivate | INTEGER |  | Not Implemented (e.g., 0.0) |
| Proof | INTEGER |  | Proof, from Spouse Fact in Edit Person window: 0 = [blank],  1 = Proven,  2 = Disproven,  3 = Dis... (e.g., 0, 1, 2, 3) |
| SpouseLabel | INTEGER |  | Not Implemented (e.g., 0.0) |
| FatherLabel | INTEGER |  | Father Label, from Spouse Fact in Edit Person window: 0 = Father 1 = Husband 2 = Partner 99 = Other (e.g., 0, 1, 2, 99) |
| MotherLabel | INTEGER |  | Mother Label, from Spouse Fact in Edit Person window: 0 = Mother 1 = Wife 2 = Partner 99 = Other (e.g., 0, 1, 2, 99) |
| SpouseLabelStr | TEXT |  | Not Implemented |
| FatherLabelStr | TEXT |  | Spouse Fact, from Edit Person window: User defined text when FatherLabel=99 (e.g., User Defined) |
| MotherLabelStr | TEXT |  | Spouse Fact, from Edit Person window: User defined text when MotherLabel=99 (e.g., User Defined) |
| Note | TEXT |  | Note for Spouse Fact, from Edit Person window: User Interface supports line breaks and formatting... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### ChildTable

Record number in childtable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record number in childtable (e.g., 1,2,3...) |
| ChildID | INTEGER |  | FK: Link to PersonID in PersonTable (e.g., 1,2,3...) |
| FamilyID | INTEGER |  | FK: Link to FamilyID in FamilyTable (e.g., 1,2,3...) |
| RelFather | INTEGER |  | Relationship to Father as defined in Parents section of Edit Person:  0 = Birth, 1 = Adopted,  2 ... (e.g., 0,1,2,...) |
| RelMother | INTEGER |  | Relationship to Mother as defined in Parents section of Edit Person:  (Values same as RelFather) (e.g., 0,1,2,...) |
| ChildOrder | INTEGER |  | When number of Children=1: 0 = Child added to family with Add Father or Add Mother action, 1000 =... (e.g., 0,1,2,3,...) |
| IsPrivate | INTEGER |  | Not Implemented (e.g., 0.0) |
| ProofFather | INTEGER |  | Set by Proof listbox in Parents pane of Edit Persons.  0 - Blank,  1 - Proven,  2 - Disproven,  3... (e.g., 0,1,2,3) |
| ProofMother | INTEGER |  | Set by Proof listbox in Parents pane of Edit Persons.  0 - Blank,  1 - Proven,  2 - Disproven,  3... (e.g., 0,1,2,3) |
| Note | TEXT |  | Not Implemented (e.g., Blank) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### NameTable

Link to PersonTable. See **RM11_Name_Display_Logic.md** for name selection rules and context-aware display logic.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| NameID | INTEGER | PK | Values: 1, 2, 3… |
| OwnerID | INTEGER |  | FK: Link to PersonTable.PersonID (aka Record Identification Number - RIN).   A single OwnerID can hav... (e.g., 1, 2, 3…) |
| Surname | TEXT | Collate: RMNOCASE | Surname (e.g., User Defined) |
| Given | TEXT | Collate: RMNOCASE | Given name (e.g., User Defined) |
| Prefix | TEXT | Collate: RMNOCASE | Name prefix, e.g., Dr., Rev., Lord, Lady... (e.g., User Defined) |
| Suffix | TEXT | Collate: RMNOCASE | Name suffix, e.g., Jr., Sr., III, ... (e.g., User Defined) |
| Nickname | TEXT | Collate: RMNOCASE | Nickname (e.g., User Defined) |
| NameType | INTEGER |  | 0 - Null 1 - AKA 2 - Birth 3 - Immigrant 4 - Maiden 5 - Married 6 - Nickname 7 - Other Spelling (e.g., 0-7) |
| Date | TEXT |  | Date, from Alternate Name Fact. (e.g., Position coded string or free text) |
| SortDate | BIGINT |  | Sort Date for Name Fact, from Edit Person window: The Sort Date forces the Name fact into a posit... (e.g., 19 digit number) |
| IsPrimary | INTEGER |  | 1 = Name is listed in the Primary Name fact, 0 = Alternate Name, Editable by selecting the Primar... (e.g., 0,1) |
| IsPrivate | INTEGER |  | Private checkbox in Edit Person Alternate Name Fact edit pane:   0 = NOT selected (default),  1 =... (e.g., 0,1) |
| Proof | INTEGER |  | Set by Proof listbox in Edit Person Name Fact edit pane.  0 = Blank (default),  1 = Proven,  2 = ... (e.g., 0,1,2,3) |
| Sentence | TEXT |  | Customized sentence template for this Alternate Name,  entered in Edit Person Alternate Name Cust... (e.g., Sentence Template Language) |
| Note | TEXT |  | Note for Name Fact, from Edit Person window: User Interface upports line breaks and formatting tags. (e.g., User Defined) |
| BirthYear | INTEGER |  | Year extracted from EventTable.Date for Birth FactType for Person (e.g., Blank or\n4-digits) |
| DeathYear | INTEGER |  | Year extracted from EventTable.Date for Death FactType for Person (e.g., Blank or\n4-digits) |
| Display | INTEGER |  | Not implemented (e.g., 0.0) |
| Language | TEXT |  | Not implemented (e.g., Blank) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |
| SurnameMP | TEXT |  | Version of User Defined NameTable.Surname |
| GivenMP | TEXT |  | Version of User Defined NameTable.Surname |
| NicknameMP | TEXT |  | Version of User Defined NameTable.Surname |

## Events and Facts

### EventTable

Link to FactTypeID in FactTypeTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| EventID | INTEGER | PK | Event Identification Number (e.g., 1,2,3...) |
| EventType | INTEGER |  | FK: Link to FactTypeID in FactTypeTable (e.g., 1,2,3...) |
| OwnerType | INTEGER |  | 0 = Person, 1 = Family (e.g., 0,1) |
| OwnerID | INTEGER |  | FK: Link based on OwnerType: 0 = PersonID in PersonTable, 1 =  FamilyID in FamilyTable (e.g., 1,2,3...) |
| FamilyID | INTEGER |  | FK: Link based on OwnerType: 0 = not applicable or not assigned to event, Else = FamilyID in FamilyTa... (e.g., 0,1,2,...) |
| PlaceID | INTEGER |  | FK: 0 if no Place has been assigned to event,  else PlaceID in PlaceTable (e.g., 0,1,2,...) |
| SiteID | INTEGER |  | FK: 0 if no Place Details assigned to event,  else PlaceID (of Place Details) in PlaceTable (e.g., 0,1,2,...) |
| Date | TEXT |  | [See Date sheet for additional details.] (e.g., Position coded string or free text) |
| SortDate | BIGINT |  | Number representing a user entered date that forces an event into a position relative to other ev... (e.g., 18 digits) |
| IsPrimary | INTEGER |  | Primary checkbox in Edit Person Fact pane: 0 = Not checked (default), 1 = Checked. (Used to suppr... (e.g., 0,1) |
| IsPrivate | INTEGER |  | Private checkbox in Edit Person Fact pane: 0 = Not checked (default), 1 = Checked. (Used to optio... (e.g., 0,1) |
| Proof | INTEGER |  | Proof listbox in Edit Person Fact pane: 0 = Blank,  1 = Proven,  2 = Proven False,  3 = Disputed (e.g., 0,1,2,3) |
| Status | INTEGER |  | 0 (default), Else = status of LDS events: e.g. 1-Submitted, 8-DNS, 12-Cleared (e.g., 0-12) |
| Sentence | TEXT |  | Customised sentence for this event.  User Interface supports line breaks and formatting tags. (e.g., Sentence Template Language) |
| Details | TEXT |  | Content of Description field in Edit Person Fact pane. Plain text (no XML). See RM11_EventTable_Details.md (e.g., User Defined) |
| Note | TEXT |  | Content of Note in Edit Person Fact Pane.  User Interface supports line breaks and formatting tags. (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### FactTypeTable

Defines event and fact types. See **RM11_FactTypes.md** for complete enumeration of 65 built-in types organized into 11 categories (Vital, Religious, Military, Life Events, Legal, etc.).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| FactTypeID | INTEGER | PK | Fact Type Identification Number: Built-in < 1000 (65 types),  User-defined >= 1000 (e.g., 1,2,3...) |
| OwnerType | INTEGER |  | Owner Type: 0 = Individual (52 types), 1 = Family (13 types) (e.g., 0,1) |
| Name | TEXT | Collate: RMNOCASE | Name, from Edit Fact Type window (e.g., Birth, Death, Marriage, Census) |
| Abbrev | TEXT |  | Abbreviation, from Edit Fact Type window (e.g., Built-in or User Defined) |
| GedcomTag | TEXT |  | GEDCOM Tag = \EVEN\ for some built-in and all user defined Fact Types  (e.g., BIRT, DEAT, MARR, CENS) |
| UseValue | INTEGER |  | \Use description field\ checkbox: 0 = No, 1 = Yes (indicates EventTable.Details is used) (e.g., 0,1) |
| UseDate | INTEGER |  | \Use date field\ checkbox, from Edit Fact Type window: 0 = No (unchecked) 1 = Yes (checked) (e.g., 0,1) |
| UsePlace | INTEGER |  | \Use place field\ checkbox, from Edit Fact Type window: 0 = No (unchecked) 1 = Yes (checked) (e.g., 0,1) |
| Sentence | TEXT |  | Sentence template for this role, from Edit Role Type window for Role name of Principal. See RM11_Sentence_Templates.md (e.g., Sentence Template Language) |
| Flags | INTEGER |  | 6-bit position-coded number for Include settings for Fact Type. (e.g., -1 to -63) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### WitnessTable

Event Identification Number, linking to EventID of EventTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| WitnessID | INTEGER | PK | Witness Identification Number (e.g., 1,2,3,...) |
| EventID | INTEGER |  | FK: Event Identification Number, linking to EventID of EventTable (e.g., 1,2,3,...) |
| PersonID | INTEGER |  | FK: Person that the fact has been shared with: 0 = This person is NOT in RM database, Else, PersonTab... (e.g., 0,1,2,3,...) |
| WitnessOrder | INTEGER |  | Not Implemented (e.g., 0.0) |
| Role | INTEGER |  | FK: Role, from Edit shared event screen, Links to RoleID in RoleTable (e.g., 1,2,3,...) |
| Sentence | TEXT |  | From Edit Person window of person that the fact has been shared with: Blank (Default) = Role Sent... (e.g., Sentence Template Language) |
| Note | TEXT |  | Note, from Edit Witness pane of Edit Person window for person that the fact has been shared with.... (e.g., User Defined) |
| Given | TEXT | Collate: RMNOCASE | From Edit Witness pane of Edit Person window for person that the fact has been shared with: Blank... (e.g., User Defined) |
| Surname | TEXT | Collate: RMNOCASE | From Edit Witness pane of Edit Person window for person that the fact has been shared with: Blank... (e.g., User Defined) |
| Prefix | TEXT | Collate: RMNOCASE | Not Implemented |
| Suffix | TEXT | Collate: RMNOCASE | Not Implemented |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### RoleTable

Event Type, links to FactTypeID in FactTypeTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RoleID | INTEGER | PK | RoleIDs = 1 – 58  are pre-defined in built-in Fact Types (e.g., 1,2,3,…) |
| RoleName | TEXT | Collate: RMNOCASE | Role name, from Edit Role Type window. Displays with fact in Edit Person window when a fact is sh... (e.g., Built-in or\nUser Defined) |
| EventType | INTEGER |  | FK: Event Type, links to FactTypeID in FactTypeTable (e.g., 1,2,3,…) |
| RoleType | INTEGER |  | Not Implemented (e.g., 0.0) |
| Sentence | TEXT |  | Sentence template for this role, from Edit Fact Type/Edit Role Type screen. User Interface suppor... (e.g., Sentence Template Language) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Sources and Citations

### SourceTable

Template Identification Number:\n0 = Free-Form, \nElse, links to TemplateID in SourceTemplateTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| SourceID | INTEGER | PK | Source Identification Number (e.g., 1,2,3,...) |
| Name | TEXT | Collate: RMNOCASE | Source Name, from Edit Source pane or Edit Citation pane (e.g., User Defined) |
| RefNumber | TEXT |  | Source Ref#, from Edit Source pane or Edit Citation pane (e.g., User Defined) |
| ActualText | TEXT |  | Source Text, from Edit Source pane or Edit Citation pane (e.g., User Defined) |
| Comments | TEXT |  | Source Comment,  from Edit Source pane or Edit Citation pane (e.g., User Defined) |
| IsPrivate | INTEGER |  | Not Implemented (e.g., 0.0) |
| TemplateID | INTEGER |  | FK: Template Identification Number: 0 = Free-Form,  Else, links to TemplateID in SourceTemplateTable (e.g., 0,1,2,3,...) |
| Fields | BLOB |  | Master Source Field \Names\  (from Source template) and \Values\ (from Edit Source pane).  For Fr... (e.g., XML) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### SourceTemplateTable

Template Name, from Source Template window.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| TemplateID | INTEGER | PK | Template Identification Number: 1 - 439 = Built-In (See Source Template window),  10,000+ = User-... (e.g., 1,2,3,…) |
| Name | TEXT | Collate: RMNOCASE | Template Name, from Source Template window. Only user-defined templates are editable. (e.g., Built-in or\nUser Defined) |
| Description | TEXT |  | Description Details, from Source Template Description window. Only user-defined templates are edi... (e.g., Built-in or\nUser Defined) |
| Favorite | INTEGER |  | 0 = Not a Favorite (Default), 1 = Template starred as Favorite from Select Source Type screen of ... (e.g., 0,1) |
| Category | TEXT |  | Category Details, from Source Template Description window. Only user-defined templates are editable. (e.g., Built-in or\nUser Defined) |
| Footnote | TEXT |  | Footnote Template, from Source Templates window. User Interface supports line breaks and formatti... (e.g., Built-in or\nUser Defined) |
| ShortFootnote | TEXT |  | Short Footnote Template, from Source Template window. User Interface supports line breaks and for... (e.g., Built-in or\nUser Defined) |
| Bibliography | TEXT |  | Bibliography Template, from Source Template window. User Interface supports line breaks and forma... (e.g., Built-in or\nUser Defined) |
| FieldDefs | BLOB |  | From Source Template Field window: Field Name, Display Name, Field Type, Brief hint, Long hint, a... (e.g., XML) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### CitationTable

Link to SourceID of SourceTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| CitationID | INTEGER | PK | Citation Identification Number (e.g., 1,2,3...) |
| SourceID | INTEGER |  | FK: Link to SourceID of SourceTable (e.g., 1,2,3...) |
| Comments | TEXT |  | Detail Comment from Edit Citation pane. User Interface supports line breaks and formatting tags. (e.g., User Defined) |
| ActualText | TEXT |  | Research Note from Edit Citation pane. User Interface supports line breaks and formatting tags. (e.g., User Defined) |
| RefNumber | TEXT |  | Detail Ref# from Edit Citation pane. (e.g., User Defined) |
| Footnote | TEXT |  | Value from Customize Footnote window, overrides sentence template output. User Interface supports... (e.g., User Defined) |
| ShortFootnote | TEXT |  | Value from Customize Footnote window, overrides sentence template output. User Interface supports... (e.g., User Defined) |
| Bibliography | TEXT |  | Value from Customize Footnote window, overrides sentence template output. User Interface supports... (e.g., User Defined) |
| Fields | BLOB |  | Citation Detail field “Names” (from Source template) and “Values” (from Edit Citation pane) (e.g., XML) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |
| CitationName | TEXT | Collate: RMNOCASE | If left blank, field value is auto generated as the concatenation of all Citation Detail fields s... (e.g., User Defined) |

### CitationLinkTable

Link to CitationTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | Link identification number (e.g., 1,2,3,...) |
| CitationID | INTEGER |  | FK: Link to CitationTable.CitationID (e.g., 1,2,3,...) |
| OwnerType | INTEGER |  |  0 = Person,  1 = Family,  2 = Event,  6 = Task,  7 = Name, 19 = Association (e.g., 0,1,2,6,7,19) |
| OwnerID | INTEGER |  | FK: Link to Primary Key of table based on OwnerType:  0 = PersonTable.PersonID,  1 = FamilyTable.Fami... |
| SortOrder | INTEGER |  | Not Implemented: Null = Legacy data, 0 =  New table entry (e.g., Null, or\n0) |
| Quality | TEXT |  | 3-Character Quality of this information:  1st = (Info): P = Primary, S = Secondary,~ = Don't know... (e.g., [PS~]{DIN~][OX~]) |
| IsPrivate | INTEGER |  | Not Implemented (e.g., 0.0) |
| Flags | INTEGER |  | Not Implemented (e.g., 0.0) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Places

### PlaceTable

Hierarchical place names using comma-delimited format. See **RM11_Place_Format.md** for hierarchy specification, parsing rules, and coordinate system.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| PlaceID | INTEGER | PK | Place Identification Number |
| PlaceType | INTEGER |  | 0 = Place, from Edit Person screen for a fact,  1 = LDS Temples, Built-In,  2 = Place details, fr... (e.g., 0,1,2) |
| Name | TEXT | Collate: RMNOCASE | Place Name from Edit Place pane of Places window or the Fact Edit pane of Edit Person window (Pla... (e.g., Built-in or\nUser Defined) |
| Abbrev | TEXT |  | Abbreviated place name, from Edit Place pane of Places window (PlaceType = 0 and 2),  Pre-defined... (e.g., Built-in or\nUser Defined) |
| Normalized | TEXT |  | Standardized place name from Edit Place pane of Places window (PlaceType = 0 and 2),  Pre-defined... (e.g., Built-in or\nUser Defined) |
| Latitude | INTEGER |  | Latitude in decimal degrees stored as an integer (ie multiplied by 1e7). Pre-defined for LDS Temp... (e.g., 0,\n8-9 Digit Integer) |
| Longitude | INTEGER |  | Longitude in decimal degrees stored as an integer (ie multiplied by 1e7). Pre-defined for LDS Tem... (e.g., 0,\n8-9 Digit Integer) |
| LatLongExact | INTEGER |  | Values: 0,1 |
| MasterID | INTEGER |  | FK: 0 for PlaceType = 0,1 PlaceID of Place, for PlaceType = 2 (Place Detail) (e.g., 0,1,2,3,...) |
| Note | TEXT |  | Place note, from Edit screen for PlaceType = 0 and 2.  User Interface supports line breaks and fo... (e.g., User Defined) |
| Reverse | TEXT | Collate: RMNOCASE | Calculated field containing the reverse order of the comma-delimeted fields in the PlaceTable.Nam... (e.g., Built-in or\nUser Defined) |
| fsID | INTEGER |  |  |
| anID | INTEGER |  |  |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### AddressTable

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| AddressID | INTEGER | PK | Address Identification Number (e.g., 1,2,3...) |
| AddressType | INTEGER |  | 0 = Person or Family, 1 = Repository (e.g., 0,1) |
| Name | TEXT | Collate: RMNOCASE | Name, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Street1 | TEXT |  | Street address [first line], from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Street2 | TEXT |  | Street address [second line], from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| City | TEXT |  | City, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| State | TEXT |  | State, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Zip | TEXT |  | Postal Code, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Country | TEXT |  | Country, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Phone1 | TEXT |  | Phone, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Phone2 | TEXT |  | Cell phone, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Fax | TEXT |  | Fax, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Email | TEXT |  | Email, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| URL | TEXT |  | Website, from Edit Address pane or Edit Repository pane.  (e.g., User Defined) |
| Latitude | INTEGER |  | Not implemented (e.g., User Defined) |
| Longitude | INTEGER |  | Not implemented (e.g., User Defined) |
| Note | TEXT |  | Note, from Edit Address pane or Edit Repository pane.  User Interface supports line breaks and fo... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### AddressLinkTable

Links to AddressID in AddressTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | Link Identification Number, sequentially ordered (e.g., 1,2,3...) |
| OwnerType | INTEGER |  | 0 = Person (Address of Person Fact from Edit Person Window), 1 = Family (Address of Spouse / Pare... (e.g., 0,1,3,6) |
| AddressID | INTEGER |  | FK: Links to AddressID in AddressTable (e.g., 1,2,3...) |
| OwnerID | INTEGER |  | FK: Link based on OwnerType: 0 = PersonTable.PersonID, 1 = FamilyTable.FamilyID, 3 = SourceTable.Sour... (e.g., 1,2,3...) |
| AddressNum | INTEGER |  | Values: 0.0 |
| Details | TEXT |  | Not Implemented (e.g., Blank) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Multimedia

### MultimediaTable

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| MediaID | INTEGER | PK | Media Identification Number |
| MediaType | INTEGER |  | Media Type, from Add Media Item screen  1 = Image,  2 = File,  3 = Sound,  4 = Video (e.g., 1,2,3,4) |
| MediaPath | TEXT |  | Relative file path of Media File, extracted from Filename field in Add Media window or Edit Media... (e.g., User Defined) |
| MediaFile | TEXT | Collate: RMNOCASE | File name, extracted from Filename field in Add Media window or Edit Media pane (e.g., User Defined) |
| URL | TEXT |  | Not implemented (e.g., Blank) |
| Thumbnail | BLOB |  | Thumbnail (e.g., ?PNG) |
| Caption | TEXT | Collate: RMNOCASE | Caption, from Add Media window or Edit Media pane (e.g., User Defined) |
| RefNumber | TEXT | Collate: RMNOCASE | Reference Number, from Add Media window or Edit Media pane (e.g., User Defined) |
| Date | TEXT |  | Date, from Media Properties screen.  (e.g., Position coded string or free text) |
| SortDate | BIGINT |  | Values: 12,15, or 19\ndigit number |
| Description | TEXT |  | Description, from Add Media window or Edit Media pane.  User Interface supports line breaks and f... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### MediaLinkTable

Media Identification Number, links to MediaID of MultimediaTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | Link Identification Number |
| MediaID | INTEGER |  | FK: Media Identification Number, links to MediaID of MultimediaTable (e.g., 1,2,3,…) |
| OwnerType | INTEGER |  | Owner Type: 0 = Person (Person Fact),  1 = Family (Spouse or Parents Fact) 2 = Event,  3 = Source... (e.g., 0,1,2,3,…) |
| OwnerID | INTEGER |  | FK: Link based on OwnerType: 0 = PersonTable.PersonID,  1 = FamilyTable.FamilyID, 2 = EventTable.Even... (e.g., 1,2,3,…) |
| IsPrimary | INTEGER |  | Primary Photo checkbox, from the Edit Media pane: 0 = Not checked (default), 1 = Checked. (Determ... (e.g., 0,1) |
| Include1 | INTEGER |  | Include in Scrapbook, from the Edit Media pane: 0 = Do Not Include (unchecked) 1 = Include (checked) (e.g., 0,1) |
| Include2 | INTEGER |  | Not implemented (e.g., 0.0) |
| Include3 | INTEGER |  | Not implemented (e.g., 0.0) |
| Include4 | INTEGER |  | Not implemented (e.g., 0.0) |
| SortOrder | INTEGER |  | Sort Order, from Media Album view in Edit Person window: 0 = (Default) Order by MediaLinkTable.Li... (e.g., 0,1,2,3,…) |
| RectLeft | INTEGER |  | Not implemented (e.g., 0.0) |
| RectTop | INTEGER |  | Not implemented (e.g., 0.0) |
| RectRight | INTEGER |  | Not implemented (e.g., 0.0) |
| RectBottom | INTEGER |  | Not implemented (e.g., 0.0) |
| Comments | TEXT |  | Media Tag Comment, from Add Media Tag window. (Select Tags from Edit Media pane of Media window, ... (e.g., Blank or\nUser Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Research Management

### TaskTable

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| TaskID | INTEGER | PK | Task Identification Number (e.g., 1,2,3,...) |
| TaskType | INTEGER |  | From Add Task window or Edit Task pane: 0 = Blank, 1 = Research,  2 = ToDo,  3 = Correspondence (e.g., 0,1,2,3) |
| RefNumber | TEXT |  | Reference #, from Add Task window or Edit Task pane. (e.g., User Defined) |
| Name | TEXT | Collate: RMNOCASE | Name, from Add Task window or Edit Task pane.  (e.g., User Defined) |
| Status | INTEGER |  | Status, From Add Task window or Edit Task pane: 0 = New, 1 = In Progress, 2 = Completed, 3 = On h... (e.g., 0,1,2,3,4,5) |
| Priority | INTEGER |  | From Add Task window or Edit Task pane: 0 = Priority 1 (Highest), 1 = Priority 2 (Very High), 2 =... (e.g., 0,1,2,3,4,5,6,7) |
| Date1 | TEXT |  | Start Date, from Edit Task screen. [See Date sheet for additional details.]  (e.g., Position coded string or free text) |
| Date2 | TEXT |  | Last Edit Date, from Edit Task screen. [See Date sheet for additional details.]  (e.g., Position coded string or free text) |
| Date3 | TEXT |  | End Date, from Edit Task screen. [See Date sheet for additional details.]  (e.g., Position coded string or free text) |
| SortDate1 | BIGINT |  | Values: 0 or\n19 digit number |
| SortDate2 | BIGINT |  | Values: 0 or\n19 digit number |
| SortDate3 | BITINT |  | Values: 0 or\n19 digit number |
| Filename | TEXT |  | File name and path, from Add Task window or Edit Task pane.  (e.g., User Defined) |
| Details | TEXT |  | Details, from Add Task window or Edit Task pane.  User Interface supports line breaks and formatt... (e.g., User Defined) |
| Results | TEXT |  | Results, from Add Task window or Edit Task pane.  User Interface supports line breaks and formatt... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |
| Exclude | INTEGER |  | From Filter Tasks window: 0 = Display Task in list (default), 1= Filter from Task list (e.g., 0,1) |

### TaskLinkTable

Links to TaskID in TaskTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | Link Identification Number (e.g., 1,2,3,...) |
| TaskID | INTEGER |  | FK: Links to TaskID in TaskTable (e.g., 1,2,3,...) |
| OwnerType | INTEGER |  | 0 = Person, 1 = Family, 2 = Event, 5 = Place,  7 = Name,  14 = Place Detail,  18 = Folder,  19 = ... (e.g., 0,1,2,5,7,14,18,19) |
| OwnerID | INTEGER |  | FK: Link based on OwnerType: 0 = PersonTable.PersonID, 1 = FamilyTable.FamilyID, 2 = EventTable.Event... (e.g., 1,2,3,...) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### GroupTable

Links to PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1,2,3,...) |
| GroupID | INTEGER |  | 1 = Results of Person Search from Search menu, 2 = Results of Person Search - Advanced from Searc... (e.g., 1,2, 1001,1002,1003,...) |
| StartID | INTEGER |  | FK: Links to PersonTable.PersonID, Starting Number of consecutively-numbered PersonIDs (e.g., 1,2,3,...) |
| EndID | INTEGER |  | FK: Links to PersonTable.PersonID, Ending Number of consecutively-numbered PersonIDs (e.g., 1,2,3,...) |
| UTCModDate | FLOAT |  | Not implemented (e.g., Null) |

### TagTable

If TagValue >1000, links to GroupTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| TagID | INTEGER | PK | Tag Identification Number (e.g., 1,2,3,...) |
| TagType | INTEGER |  | 0 = Group, 1 = Folder (e.g., 0,1) |
| TagValue | INTEGER |  | FK: If TagValue >1000, links to GroupTable.GroupID Else, incremental placeholder for Task Folders. (e.g., 1,2,3,...) |
| TagName | TEXT | Collate: RMNOCASE | Name of Group or Task Folder (e.g., User Defined) |
| Description | TEXT |  | Description of Task Folder, Blank for Groups. (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## External Services

### AncestryTable

Link based on LinkType:\n0 = PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | LinkID Identification Number (e.g., 1,2,3...) |
| LinkType | INTEGER |  | 0 = Person,  4 = Citation,  11 = Media (e.g., 0, 4, 11) |
| rmID | INTEGER |  | FK: Link based on LinkType: 0 = PersonTable.PersonID,  4 = CitationTable.CitationID,  11 = MultiMedia... (e.g., 1,2,3...) |
| anID | TEXT |  | Person = [d]{12}:[d]{4}:[d]{9} - e.g.: 121212121212:1030:123456789, Citation, origin RM = [d]:900... (e.g., Formatted string) |
| Modified | INTEGER |  | For LinkType=0 (Person): 0 = No modification detected or 'Mark as not changed' button has been se... (e.g., 0, 1) |
| anVersion | TEXT |  | Hex code where LinkType=0 (Person),  Otherwise NULL (e.g., Null or Hex String) |
| anDate | FLOAT |  | Values: 0.0 |
| Status | INTEGER |  | Values: 0.0 |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |
| TreeID | TEXT |  | Not Implemented (e.g., Blank) |

### FamilySearchTable

Link based on LinkType:\n0 = PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | LinkID Identification Number (e.g., 1,2,3...) |
| LinkType | INTEGER |  | 0 = Person (e.g., 0.0) |
| rmID | INTEGER |  | FK: Link based on LinkType: 0 = PersonTable.PersonID (e.g., 1,2,3...) |
| fsID | TEXT |  | FamilySearch ID from FamilySearch Family Tree connection (e.g., 1,2,3...) |
| Modified | INTEGER |  | 0 = Default, 1 = Mismatch exists between FamilySearch and RM record details (Event date, place, e... (e.g., 0,1) |
| fsVersion | TEXT |  | FamilySearch Version |
| fsDate | FLOAT |  | Values: 0.0 |
| Status | INTEGER |  | 0 = Default, Person Record initially created in RM db 4 = Person Record initially imported from F... (e.g., 0,4) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |
| TreeID | TEXT |  | Not Implemented (e.g., Blank) |

## DNA and Health

### DNATable

Person 1, from the DNA Match view of Edit Person Window.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1, 2, 3…) |
| ID1 | INTEGER |  | FK: Person 1, from the DNA Match view of Edit Person Window.  Links to PersonTable.PersonID. (e.g., 1, 2, 3…) |
| ID2 | INTEGER |  | FK: Person 2, from the DNA Match view of Edit Person Window.  Links to PersonTable.PersonID. (e.g., 1, 2, 3…) |
| Label1 | TEXT |  | Label 1, from the DNA Match view of Edit Person Window.   (e.g., User Defined) |
| Label2 | TEXT |  | Label 2, from the DNA Match view of Edit Person Window.   (e.g., User Defined) |
| DNAProvider | INTEGER |  | Provider, from the DNA Match view of Edit Person Window: 1 = 23andMe, 2 = Ancestry, 3 = Family Tr... (e.g., 1-6, 998, 999) |
| SharedCM | FLOAT |  | Shared Centimorgans (cM), from the DNA Match view of Edit Person Window. (e.g., User Defined,\n0-4000) |
| SharedPercent | FLOAT |  | Shared Percentage, from the DNA Match view of Edit Person Window. (e.g., User Defined,\n0-100) |
| LargeSeg | FLOAT |  | Largest Segment (cM), from the DNA Match view of Edit Person Window. (e.g., User Defined,\n0-500) |
| SharedSegs | INTEGER |  | Shared Segments, from the DNA Match view of Edit Person Window. (e.g., User Defined,\n0-100) |
| Date | TEXT |  | [See Date sheet for additional details.] (e.g., Position coded string or free text) |
| Relate1 | INTEGER |  | Relate1, the number of generations between Person 1 (DNATable.ID1) and the Most Recent Common Anc... (e.g., 0-999) |
| Relate2 | INTEGER |  | Relate2, the number of generations between Person 2 (DNATable.ID2) and the Most Recent Common Anc... (e.g., 0,1,2,...) |
| CommonAnc | INTEGER |  | FK: Most Recent Common Ancestor (MRCA) of Person1 and Person2 of the DNA Match. Link to Primary Key o... (e.g., 0,1,2,...) |
| CommonAncType | INTEGER |  | Common Ancestor Type. When DNATable.CommonAnc > 0:  0 = Single MRCA (ie Half Relationship) identi... (e.g., 0,1) |
| Verified | INTEGER |  | Not Implemented (e.g., 0.0) |
| Note | TEXT |  | DNA Note, from the DNA Match view of Edit Person Window.   User Interface supports line breaks an... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### HealthTable

Links to PersonID in the PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1,2,3,…) |
| OwnerID | INTEGER |  | FK: Links to PersonID in the PersonTable (e.g., 1,2,3,…) |
| Condition | INTEGER |  | Condition, from the Health Condition view of the Edit Person window: 1= Infectious and parasitic ... (e.g., 1-20, 999) |
| SubCondition | TEXT |  | Details, from the Health Condition view of the Edit Person window. (e.g., User Defined) |
| Date | FLOAT |  | [See Date sheet for additional details.] (e.g., Position coded string or free text) |
| Note | TEXT |  | Health Note, from the Health Condition view of the Edit Person window. User Interface supports li... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Relationships

### FANTable

Link to PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| FanID | INTEGER | PK | RecordID for Friends, Associations, Neighbours links in support of the Association fact type.  (e.g., 1,2,3,...) |
| ID1 | INTEGER |  | FK: Link to PersonTable.PersonID for node1 of association (e.g., 1,2,3,...) |
| ID2 | INTEGER |  | FK: Link to PersonTable.PersonID for node2 of association (e.g., 1,2,3,...) |
| FanTypeID | INTEGER |  | FK: Link to FANTypeTable.FanTypeID (e.g., 1,2,3,...) |
| PlaceID | INTEGER |  | FK: 0 = Place Blank, Else, link to PlaceTable.PlaceID for PlaceType=0 (e.g., 0,1,2,3,...) |
| SiteID | INTEGER |  | FK: 0 = Place Blank, Else, link to PlaceTable.PlaceID for PlaceType=2 (e.g., 0,1,2,3,...) |
| Date | TEXT |  | Date, from Associations. [See Date sheet for additional details.] (e.g., Position coded string or free text) |
| SortDate | BIGINT |  | Number representing a user entered date that forces an event into a position relative to other ev... (e.g., 18 digits) |
| Description | TEXT |  | Description, from Association pane of Edit Person window.  (e.g., User Defined) |
| Note | TEXT |  | Note, from Association pane of Edit Person window. User Interface supports line breaks and format... (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### FANTypeTable

Role2 name (see FANTableType.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| FANTypeID | INTEGER | PK |  Association ID (e.g., 1-15, 999) |
| Name | TEXT | Collate: RMNOCASE | Association Type, based on FANTypeID: 1 = Friends 2 = Neighbors  3 = Employment  4 = Education  5... (e.g., 1-15, 999) |
| Role1 | TEXT |  | Role 1 and Role2 Names, based on FANTypeID: 1 = Friend / Friend  2 = Neighbor / Neighbor  3 = Emp... (e.g., 1-15, 999) |
| Role2 | TEXT |  | Role2 name (see FANTableType.Role1 above) (e.g., 1-15, 999) |
| Sentence1 | TEXT |  | Template for Role1 (e.g., Sentence Template Language) |
| Sentence2 | TEXT |  | Template for Role2 (e.g., Sentence Template Language) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## System

### ConfigTable

Title - See Row 5 of ConfigTable Tab.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1, 2, 3...) |
| RecType | INTEGER |  | Record Type: 1 = Database Configuration settings 3 = Custom Report settings, from Publish menu 4 ... (e.g., 1, 2, 3...) |
| Title | TEXT |  | Title - See Row 5 of ConfigTable Tab (e.g., Built-in or\nUser Defined) |
| DataRec | BLOB |  | Data Record - See Row 40 of ConfigTable Tab (e.g., XML code) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### ExclusionTable

Identification Number 1, based on ExclusionType:\n1 = PersonTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1, 2, 3...) |
| ExclusionType | INTEGER |  | Exclusion Type: 1 = Person member of \Not a duplicate list\, from Merge Duplicates tool, 2 = Pers... (e.g., 1,2) |
| ID1 | INTEGER |  | FK: Identification Number 1, based on ExclusionType: 1 = PersonTable.PersonID of Person 1 from potent... (e.g., 1, 2, 3...) |
| ID2 | INTEGER |  | FK: Identification Number 2, based on ExclusionType: 1 = PersonTable.PersonID of Person 2 from potent... (e.g., Built in) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### PayloadTable

Link based on RecType:\n1 = \0\ (not used),\n2 = GroupTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| RecID | INTEGER | PK | Record Identification Number (e.g., 1,2,3,...) |
| RecType | INTEGER |  | 3 = Saved Task Filter, 4 = Saved Search, 5 = Saved Group (e.g., 3,4,5) |
| OwnerType | INTEGER |  | 8 = Saved Search, 20 = Saved Group (e.g., 8,20) |
| OwnerID | INTEGER |  | FK: Link based on RecType: 1 = \0\ (not used), 2 = GroupTable.GroupID, 3 = \0\ (not used) (e.g., 0,1,2,3,...) |
| Title | TEXT |  | Saved Name of Search or Group (e.g., User Defined) |
| DataRec | BLOB |  | Saved Criteria for Search or Group (e.g., XML) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

### URLTable

Owner Identification, link based on OwnerType:\n3 = SourceTable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| LinkID | INTEGER | PK | Link or WebTag Identification Number (e.g., 1,2,3,...) |
| OwnerType | INTEGER |  | Owner Type: 3 = Source, 4 = Citation, 5 = Place, 6 = Task, 14 = Place Details (e.g., 3,4,5,6,14) |
| OwnerID | INTEGER |  | FK: Owner Identification, link based on OwnerType: 3 = SourceTable.SourceID, 4 = CitationTable.Citati... (e.g., 1,2,3,...) |
| LinkType | INTEGER |  | Not Implemented (e.g., 0.0) |
| Name | TEXT |  | Name, from Edit Web Tag window (e.g., User Defined) |
| URL | TEXT |  | URL, from Edit Web Tag window (e.g., User Defined) |
| Note | TEXT |  | Note, from Edit Web Tag window.  User Interface supports line breaks and formatting tags (e.g., User Defined) |
| UTCModDate | FLOAT |  | Coordinated Universal Time from system, modified:  SELECT julianday('now') - 2415018.5 (e.g., [d]{5}.[d]{10}\ne.g.: 44993.9143704283) |

## Indexes

The database includes extensive indexing for performance:

### AddressTable

- `idxAddressName` (on Name)

### AncestryTable

- `idxLinkAncestryRmId` (on rmID)
- `idxLinkAncestryanID` (on anID)

### ChildTable

- `idxChildID` (on ChildID)
- `idxChildFamilyID` (on FamilyID)
- `idxChildOrder` (on ChildOrder)

### CitationLinkTable

- `idxCitationLinkOwnerID` (on OwnerID)

### CitationTable

- `idxCitationSourceID` (on SourceID)
- `idxCitationName` (on CitationName)

### ConfigTable

- `idxRecType` (on RecType)

### DNATable

- `idxDnaId1` (on ID1)
- `idxDnaId2` (on ID2)

### EventTable

- `idxOwnerEvent` (on OwnerID,EventType)
- `idxOwnerDate` (on OwnerID,SortDate)

### ExclusionTable

- `idxExclusionIndex` (UNIQUE on ExclusionType,
  ID1,
  ID2)

### FANTable

- `idxFanId1` (on ID1)
- `idxFanId2` (on ID2)

### FANTypeTable

- `idxFANTypeName` (on Name)

### FactTypeTable

- `idxFactTypeName` (on Name)
- `idxFactTypeAbbrev` (on Abbrev)
- `idxFactTypeGedcomTag` (on GedcomTag)

### FamilySearchTable

- `idxLinkRmId` (on rmID)
- `idxLinkfsID` (on fsID)

### FamilyTable

- `idxFamilyFatherID` (on FatherID)
- `idxFamilyMotherID` (on MotherID)

### HealthTable

- `idxHealthOwnerId` (on OwnerID)

### MediaLinkTable

- `idxMediaOwnerID` (on OwnerID)

### MultimediaTable

- `idxMediaFile` (on MediaFile)
- `idxMediaURL` (on URL)

### NameTable

- `idxNameOwnerID` (on OwnerID)
- `idxSurname` (on Surname)
- `idxGiven` (on Given)
- `idxSurnameGiven` (on Surname,
  Given,
  BirthYear,
  DeathYear)
- `idxNamePrimary` (on IsPrimary)
- `idxSurnameMP` (on SurnameMP)
- `idxGivenMP` (on GivenMP)
- `idxSurnameGivenMP` (on SurnameMP,
  GivenMP,
  BirthYear,
  DeathYear)

### PayloadTable

- `idxPayloadType` (on RecType)

### PlaceTable

- `idxPlaceName` (on Name)
- `idxReversePlaceName` (on Reverse)
- `idxPlaceAbbrev` (on Abbrev)

### RoleTable

- `idxRoleEventType` (on EventType)

### SourceTable

- `idxSourceName` (on Name)

### SourceTemplateTable

- `idxSourceTemplateName` (on Name)

### TagTable

- `idxTagType` (on TagType)

### TaskLinkTable

- `idxTaskOwnerID` (on OwnerID)

### TaskTable

- `idxTaskName` (on Name)

### WitnessTable

- `idxWitnessEventID` (on EventID)
- `idxWitnessPersonID` (on PersonID)

## Common Query Patterns

### Finding a Person by Name

```sql
SELECT p.PersonID, n.Surname, n.Given, n.BirthYear, n.DeathYear
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID
WHERE n.IsPrimary = 1
  AND n.Surname = 'Smith'
  AND n.Given LIKE 'John%';
```

### Getting Person's Events

```sql
SELECT e.EventID, ft.Name as EventType, e.Date, e.Details
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.OwnerType = 0
  AND e.OwnerID = 123
ORDER BY e.SortDate;
```

### Finding Person's Family

```sql
-- Get person's parents
SELECT f.FamilyID, f.FatherID, f.MotherID
FROM FamilyTable f
WHERE f.FamilyID = (SELECT ParentID FROM PersonTable WHERE PersonID = 123);

-- Get person's children
SELECT c.ChildID, p.PersonID
FROM ChildTable c
JOIN PersonTable p ON c.ChildID = p.PersonID
WHERE c.FamilyID IN (SELECT SpouseID FROM PersonTable WHERE PersonID = 123);
```

### Retrieving Citations for an Event

```sql
SELECT c.CitationID, c.CitationName, s.Name as SourceName
FROM CitationLinkTable cl
JOIN CitationTable c ON cl.CitationID = c.CitationID
JOIN SourceTable s ON c.SourceID = s.SourceID
WHERE cl.OwnerType = 2  -- Event
  AND cl.OwnerID = 456;
```

### Finding Media for a Person

```sql
SELECT m.MediaID, m.MediaFile, m.Caption, m.Description
FROM MediaLinkTable ml
JOIN MultimediaTable m ON ml.MediaID = m.MediaID
WHERE ml.OwnerType = 0  -- Person
  AND ml.OwnerID = 123
  AND ml.IsPrimary = 1;
```

## Related Documentation

### Core Schema References
- **RM11_Date_Format.md** - Date field encoding specification (24-character format)
- **RM11_Relationships.md** - Relationship calculation (Relate1, Relate2, Flags)
- **RM11DataDef.yaml** - Detailed field definitions with enumerations
- **RM11_schema_annotated.sql** - SQL schema with inline comments
- **RM11_schema.json** - JSON Schema for validation

### BLOB Structure Documentation
- **RM11_BLOB_SourceFields.md** - SourceTable.Fields XML structure
- **RM11_BLOB_SourceTemplateFieldDefs.md** - SourceTemplateTable.FieldDefs XML structure
- **RM11_BLOB_CitationFields.md** - CitationTable.Fields XML structure

### Event and Fact Documentation
- **RM11_FactTypes.md** - All 65 built-in fact types categorized
- **RM11_Sentence_Templates.md** - Sentence template language (reference)
- **RM11_EventTable_Details.md** - EventTable.Details field patterns

### Place and Name Documentation
- **RM11_Place_Format.md** - Place hierarchy and parsing specification
- **RM11_Name_Display_Logic.md** - Name selection and display rules

### Data Quality and Queries
- **RM11_Data_Quality_Rules.md** - 24 validation rules across 6 categories
- **RM11_Query_Patterns.md** - 15 optimized query patterns with examples

### Output Generation
- **RM11_Timeline_Construction.md** - TimelineJS3 timeline generation
- **RM11_Biography_Best_Practices.md** - Biography writing guidelines

## Metadata

- **Source**: RootsMagic 11 Data Definition
- **Source File**: RM11DataDef-V11_0_0-20250914.xlsx
- **Version**: 11.0.0
- **Date**: 2025-09-14
- **Database Type**: SQLite 3
- **Total Tables**: 31
- **Total Indexes**: 49
