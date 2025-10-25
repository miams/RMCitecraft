-- RootsMagic 11 Database Schema (Annotated)
-- Version: 11.0.0
-- Date: 2025-09-14
-- Source: RM11DataDef-V11_0_0-20250914.xlsx
--
-- This is an enhanced version of the RootsMagic 11 SQLite schema with
-- inline documentation including field descriptions, typical values,
-- constraints, and foreign key relationships.
--
-- Conventions:
--   - FK: Foreign Key reference
--   - PK: Primary Key
--   - Enum values shown as: 0=Value1, 1=Value2, etc.
--   - Typical values shown in comments
--

-- ============================================================================
-- AddressLinkTable
-- ============================================================================
CREATE TABLE AddressLinkTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Link Identification Number, sequentially ordered
  OwnerType INTEGER, -- Type: Integer | Values: 0,1,3,6 | 0 = Person (Address of Person Fact from Edit Person Window), 1 = Family (Addr...
  AddressID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Links to AddressID in AddressTable
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link based on OwnerType: 0 = PersonTable.PersonID, 1 = FamilyTable.FamilyID, ...
  AddressNum INTEGER, -- Type: Integer | Values: 0.0
  Details TEXT, -- Type: Text | Values: Blank | Not Implemented
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- AddressTable
-- ============================================================================
CREATE TABLE AddressTable(
  AddressID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Address Identification Number
  AddressType INTEGER, -- Type: Integer | Values: 0,1 | 0 = Person or Family, 1 = Repository
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Name, from Edit Address pane or Edit Repository pane. 
  Street1 TEXT, -- Type: Text | Values: User Defined | Street address [first line], from Edit Address pane or Edit Repository pane. 
  Street2 TEXT, -- Type: Text | Values: User Defined | Street address [second line], from Edit Address pane or Edit Repository pane. 
  City TEXT, -- Type: Text | Values: User Defined | City, from Edit Address pane or Edit Repository pane. 
  State TEXT, -- Type: Text | Values: User Defined | State, from Edit Address pane or Edit Repository pane. 
  Zip TEXT, -- Type: Text | Values: User Defined | Postal Code, from Edit Address pane or Edit Repository pane. 
  Country TEXT, -- Type: Text | Values: User Defined | Country, from Edit Address pane or Edit Repository pane. 
  Phone1 TEXT, -- Type: Text | Values: User Defined | Phone, from Edit Address pane or Edit Repository pane. 
  Phone2 TEXT, -- Type: Text | Values: User Defined | Cell phone, from Edit Address pane or Edit Repository pane. 
  Fax TEXT, -- Type: Text | Values: User Defined | Fax, from Edit Address pane or Edit Repository pane. 
  Email TEXT, -- Type: Text | Values: User Defined | Email, from Edit Address pane or Edit Repository pane. 
  URL TEXT, -- Type: Text | Values: User Defined | Website, from Edit Address pane or Edit Repository pane. 
  Latitude INTEGER, -- Type: Integer | Values: User Defined | Not implemented
  Longitude INTEGER, -- Type: Integer | Values: User Defined | Not implemented
  Note TEXT, -- Type: Text | Values: User Defined | Note, from Edit Address pane or Edit Repository pane.  User Interface support...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- AncestryTable
-- ============================================================================
CREATE TABLE AncestryTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | LinkID Identification Number
  LinkType INTEGER, -- Type: Integer | Values: 0, 4, 11 | 0 = Person,  4 = Citation,  11 = Media
  rmID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link based on LinkType: 0 = PersonTable.PersonID,  4 = CitationTable.Citation...
  anID TEXT, -- Type: Text | Values: Formatted string | Person = [d]{12}:[d]{4}:[d]{9} - e.g.: 121212121212:1030:123456789, Citation,...
  Modified INTEGER, -- Type: Integer | Values: 0, 1 | For LinkType=0 (Person): 0 = No modification detected or 'Mark as not changed...
  anVersion TEXT, -- Type: Text | Values: Null or Hex String | Hex code where LinkType=0 (Person),  Otherwise NULL
  anDate FLOAT, -- Type: Float | Values: 0.0
  Status INTEGER, -- Type: Integer | Values: 0.0
  UTCModDate FLOAT , -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
  TreeID TEXT -- Type: Text | Values: Blank | Not Implemented
);

-- ============================================================================
-- ChildTable
-- ============================================================================
CREATE TABLE ChildTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Record number in childtable
  ChildID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link to PersonID in PersonTable
  FamilyID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link to FamilyID in FamilyTable
  RelFather INTEGER, -- Type: Integer | Values: 0,1,2,... | Relationship to Father as defined in Parents section of Edit Person:  0 = Bir...
  RelMother INTEGER, -- Type: Integer | Values: 0,1,2,... | Relationship to Mother as defined in Parents section of Edit Person:  (Values...
  ChildOrder INTEGER, -- Type: Integer | Values: 0,1,2,3,... | When number of Children=1: 0 = Child added to family with Add Father or Add M...
  IsPrivate INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  ProofFather INTEGER, -- Type: Integer | Values: 0,1,2,3 | Set by Proof listbox in Parents pane of Edit Persons.  0 - Blank,  1 - Proven...
  ProofMother INTEGER, -- Type: Integer | Values: 0,1,2,3 | Set by Proof listbox in Parents pane of Edit Persons.  0 - Blank,  1 - Proven...
  Note TEXT, -- Type: Text | Values: Blank | Not Implemented
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- CitationLinkTable
-- ============================================================================
CREATE TABLE CitationLinkTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Link identification number
  CitationID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Link to CitationTable.CitationID
  OwnerType INTEGER, -- Type: Integer | Values: 0,1,2,6,7,19 |  0 = Person,  1 = Family,  2 = Event,  6 = Task,  7 = Name, 19 = Association
  OwnerID INTEGER, -- Type: Integer | FK | Link to Primary Key of table based on OwnerType:  0 = PersonTable.PersonID,  ...
  SortOrder INTEGER, -- Type: Integer | Values: Null, or\n0 | Not Implemented: Null = Legacy data, 0 =  New table entry
  Quality TEXT, -- Type: Text | Values: [PS~]{DIN~][OX~] | 3-Character Quality of this information:  1st = (Info): P = Primary, S = Seco...
  IsPrivate INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Flags INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- ConfigTable
-- ============================================================================
CREATE TABLE ConfigTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1, 2, 3... | Record Identification Number
  RecType INTEGER, -- Type: Integer | Values: 1, 2, 3... | Record Type: 1 = Database Configuration settings 3 = Custom Report settings, ...
  Title TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Title - See Row 5 of ConfigTable Tab
  DataRec BLOB, -- Type: Blob | Values: XML code | Data Record - See Row 40 of ConfigTable Tab
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- EventTable
-- ============================================================================
CREATE TABLE EventTable(
  EventID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Event Identification Number
  EventType INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link to FactTypeID in FactTypeTable
  OwnerType INTEGER, -- Type: Integer | Values: 0,1 | 0 = Person, 1 = Family
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link based on OwnerType: 0 = PersonID in PersonTable, 1 =  FamilyID in Family...
  FamilyID INTEGER, -- Type: Integer | FK | Values: 0,1,2,... | Link based on OwnerType: 0 = not applicable or not assigned to event, Else = ...
  PlaceID INTEGER, -- Type: Integer | FK | Values: 0,1,2,... | 0 if no Place has been assigned to event,  else PlaceID in PlaceTable
  SiteID INTEGER, -- Type: Integer | FK | Values: 0,1,2,... | 0 if no Place Details assigned to event,  else PlaceID (of Place Details) in ...
  Date TEXT, -- Type: Text | Values: Position coded string or free text | [See Date sheet for additional details.]
  SortDate BIGINT, -- Type: BigInt | Values: 18 digits | Number representing a user entered date that forces an event into a position ...
  IsPrimary INTEGER, -- Type: Integer | Values: 0,1 | Primary checkbox in Edit Person Fact pane: 0 = Not checked (default), 1 = Che...
  IsPrivate INTEGER, -- Type: Integer | Values: 0,1 | Private checkbox in Edit Person Fact pane: 0 = Not checked (default), 1 = Che...
  Proof INTEGER, -- Type: Integer | Values: 0,1,2,3 | Proof listbox in Edit Person Fact pane: 0 = Blank,  1 = Proven,  2 = Proven F...
  Status INTEGER, -- Type: Integer | Values: 0-12 | 0 (default), Else = status of LDS events: e.g. 1-Submitted, 8-DNS, 12-Cleared
  Sentence TEXT, -- Type: Text | Values: Sentence Template Language | Customised sentence for this event.  User Interface supports line breaks and ...
  Details TEXT, -- Type: Text | Values: User Defined | Content of Description field in Edit Person Fact pane
  Note TEXT, -- Type: Text | Values: User Defined | Content of Note in Edit Person Fact Pane.  User Interface supports line break...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- ExclusionTable
-- ============================================================================
CREATE TABLE ExclusionTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1, 2, 3... | Record Identification Number
  ExclusionType INTEGER, -- Type: Integer | Values: 1,2 | Exclusion Type: 1 = Person member of \Not a duplicate list\, from Merge Dupli...
  ID1 INTEGER, -- Type: Integer | FK | Values: 1, 2, 3... | Identification Number 1, based on ExclusionType: 1 = PersonTable.PersonID of ...
  ID2 INTEGER, -- Type: Integer | FK | Values: Built in | Identification Number 2, based on ExclusionType: 1 = PersonTable.PersonID of ...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- FactTypeTable
-- ============================================================================
CREATE TABLE FactTypeTable(
  FactTypeID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Fact Type Identification Number: Built-in < 1000,  User-defined > = 1000
  OwnerType INTEGER, -- Type: Integer | Values: 0,1 | Owner Type: 0 = Individual, 1 = Family
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: Built-in or\nUser Defined | Name, from Edit Fact Type window
  Abbrev TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Abbreviation, from Edit Fact Type window
  GedcomTag TEXT, -- Type: Text | Values: Character string | GEDCOM Tag = \EVEN\ for some built-in and all user defined Fact Types 
  UseValue INTEGER, -- Type: Integer | Values: 0,1 | \Use description field\ checkbox, from Edit Fact Type window: 0 = No (uncheck...
  UseDate INTEGER, -- Type: Integer | Values: 0,1 | \Use date field\ checkbox, from Edit Fact Type window: 0 = No (unchecked) 1 =...
  UsePlace INTEGER, -- Type: Integer | Values: 0,1 | \Use place field\ checkbox, from Edit Fact Type window: 0 = No (unchecked) 1 ...
  Sentence TEXT, -- Type: Text | Values: Sentence Template Language | Sentence template for this role, from Edit Role Type window for Role name of ...
  Flags INTEGER, -- Type: Integer | Values: -1 to -63 | 6-bit position-coded number for Include settings for Fact Type.
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- FamilySearchTable
-- ============================================================================
CREATE TABLE FamilySearchTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | LinkID Identification Number
  LinkType INTEGER, -- Type: Integer | Values: 0.0 | 0 = Person
  rmID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link based on LinkType: 0 = PersonTable.PersonID
  fsID TEXT, -- Type: Text | Values: 1,2,3... | FamilySearch ID from FamilySearch Family Tree connection
  Modified INTEGER, -- Type: Integer | Values: 0,1 | 0 = Default, 1 = Mismatch exists between FamilySearch and RM record details (...
  fsVersion TEXT, -- Type: Text | Values: 18 digit integer, \n40-45 char hexadecimal + '-GZIP' | FamilySearch Version
  fsDate FLOAT, -- Type: Float | Values: 0.0
  Status INTEGER, -- Type: Integer | Values: 0,4 | 0 = Default, Person Record initially created in RM db 4 = Person Record initi...
  UTCModDate FLOAT , -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
  TreeID TEXT -- Type: Text | Values: Blank | Not Implemented
);

-- ============================================================================
-- FamilyTable
-- ============================================================================
CREATE TABLE FamilyTable(
  FamilyID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1, 2, 3... | Family Identification Number
  FatherID INTEGER, -- Type: Integer | FK | Values: 1, 2, 3... | Links to PersonID in the PersonTable
  MotherID INTEGER, -- Type: Integer | FK | Values: 1, 2, 3... | Links to PersonID in the PersonTable
  ChildID INTEGER, -- Type: Integer | FK | Values: 0, 1, 2,... | Links to PersonTable.PersonID of Child last active as the root person in Pedi...
  HusbOrder INTEGER, -- Type: Integer | Values: 0, 1, 2,... | Husband Order, from People View, Edit Menu, Rearrange Spouses: 0 if never rea...
  WifeOrder INTEGER, -- Type: Integer | Values: 0, 1, 2,... | Wife Order, from People View, Edit Menu, Rearrange Spouses: 0 if never rearra...
  IsPrivate INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Proof INTEGER, -- Type: Integer | Values: 0, 1, 2, 3 | Proof, from Spouse Fact in Edit Person window: 0 = [blank],  1 = Proven,  2 =...
  SpouseLabel INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  FatherLabel INTEGER, -- Type: Integer | Values: 0, 1, 2, 99 | Father Label, from Spouse Fact in Edit Person window: 0 = Father 1 = Husband ...
  MotherLabel INTEGER, -- Type: Integer | Values: 0, 1, 2, 99 | Mother Label, from Spouse Fact in Edit Person window: 0 = Mother 1 = Wife 2 =...
  SpouseLabelStr TEXT, -- Type: Text | Not Implemented
  FatherLabelStr TEXT, -- Type: Text | Values: User Defined | Spouse Fact, from Edit Person window: User defined text when FatherLabel=99
  MotherLabelStr TEXT, -- Type: Text | Values: User Defined | Spouse Fact, from Edit Person window: User defined text when MotherLabel=99
  Note TEXT, -- Type: Text | Values: User Defined | Note for Spouse Fact, from Edit Person window: User Interface supports line b...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- GroupTable
-- ============================================================================
CREATE TABLE GroupTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Record Identification Number
  GroupID INTEGER, -- Type: Integer | Values: 1,2, 1001,1002,1003,... | 1 = Results of Person Search from Search menu, 2 = Results of Person Search -...
  StartID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Links to PersonTable.PersonID, Starting Number of consecutively-numbered Pers...
  EndID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Links to PersonTable.PersonID, Ending Number of consecutively-numbered PersonIDs
  UTCModDate FLOAT -- Type: Float | Values: Null | Not implemented
);

-- ============================================================================
-- MediaLinkTable
-- ============================================================================
CREATE TABLE MediaLinkTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Link Identification Number
  MediaID INTEGER, -- Type: Integer | FK | Values: 1,2,3,… | Media Identification Number, links to MediaID of MultimediaTable
  OwnerType INTEGER, -- Type: Integer | Values: 0,1,2,3,… | Owner Type: 0 = Person (Person Fact),  1 = Family (Spouse or Parents Fact) 2 ...
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3,… | Link based on OwnerType: 0 = PersonTable.PersonID,  1 = FamilyTable.FamilyID,...
  IsPrimary INTEGER, -- Type: Integer | Values: 0,1 | Primary Photo checkbox, from the Edit Media pane: 0 = Not checked (default), ...
  Include1 INTEGER, -- Type: Integer | Values: 0,1 | Include in Scrapbook, from the Edit Media pane: 0 = Do Not Include (unchecked...
  Include2 INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  Include3 INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  Include4 INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  SortOrder INTEGER, -- Type: Integer | Values: 0,1,2,3,… | Sort Order, from Media Album view in Edit Person window: 0 = (Default) Order ...
  RectLeft INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  RectTop INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  RectRight INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  RectBottom INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  Comments TEXT, -- Type: Text | Values: Blank or\nUser Defined | Media Tag Comment, from Add Media Tag window. (Select Tags from Edit Media pa...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- MultimediaTable
-- ============================================================================
CREATE TABLE MultimediaTable(
  MediaID INTEGER PRIMARY KEY, -- Type: Integer | PK | Media Identification Number
  MediaType INTEGER, -- Type: Integer | Values: 1,2,3,4 | Media Type, from Add Media Item screen  1 = Image,  2 = File,  3 = Sound,  4 ...
  MediaPath TEXT, -- Type: Text | Values: User Defined | Relative file path of Media File, extracted from Filename field in Add Media ...
  MediaFile TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | File name, extracted from Filename field in Add Media window or Edit Media pane
  URL TEXT, -- Type: Text | Values: Blank | Not implemented
  Thumbnail BLOB, -- Type: Blob | Values: ?PNG | Thumbnail
  Caption TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Caption, from Add Media window or Edit Media pane
  RefNumber TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Reference Number, from Add Media window or Edit Media pane
  Date TEXT, -- Type: Text | Values: Position coded string or free text | Date, from Media Properties screen. 
  SortDate BIGINT, -- Type: BigInt | Values: 12,15, or 19\ndigit number
  Description TEXT, -- Type: Text | Values: User Defined | Description, from Add Media window or Edit Media pane.  User Interface suppor...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- NameTable
-- ============================================================================
CREATE TABLE NameTable(
  NameID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1, 2, 3…
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1, 2, 3… | Link to PersonTable.PersonID (aka Record Identification Number - RIN).   A si...
  Surname TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Surname
  Given TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Given name
  Prefix TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Name prefix, e.g., Dr., Rev., Lord, Lady...
  Suffix TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Name suffix, e.g., Jr., Sr., III, ...
  Nickname TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Nickname
  NameType INTEGER, -- Type: Integer | Values: 0-7 | 0 - Null 1 - AKA 2 - Birth 3 - Immigrant 4 - Maiden 5 - Married 6 - Nickname ...
  Date TEXT, -- Type: Text | Values: Position coded string or free text | Date, from Alternate Name Fact.
  SortDate BIGINT, -- Type: BigInt | Values: 19 digit number | Sort Date for Name Fact, from Edit Person window: The Sort Date forces the Na...
  IsPrimary INTEGER, -- Type: Integer | Values: 0,1 | 1 = Name is listed in the Primary Name fact, 0 = Alternate Name, Editable by ...
  IsPrivate INTEGER, -- Type: Integer | Values: 0,1 | Private checkbox in Edit Person Alternate Name Fact edit pane:   0 = NOT sele...
  Proof INTEGER, -- Type: Integer | Values: 0,1,2,3 | Set by Proof listbox in Edit Person Name Fact edit pane.  0 = Blank (default)...
  Sentence TEXT, -- Type: Text | Values: Sentence Template Language | Customized sentence template for this Alternate Name,  entered in Edit Person...
  Note TEXT, -- Type: Text | Values: User Defined | Note for Name Fact, from Edit Person window: User Interface upports line brea...
  BirthYear INTEGER, -- Type: Integer | Values: Blank or\n4-digits | Year extracted from EventTable.Date for Birth FactType for Person
  DeathYear INTEGER, -- Type: Integer | Values: Blank or\n4-digits | Year extracted from EventTable.Date for Death FactType for Person
  Display INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  Language TEXT, -- Type: Text | Values: Blank | Not implemented
  UTCModDate FLOAT, -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
  SurnameMP TEXT, -- Type: Text | Version of User Defined NameTable.Surname
  GivenMP TEXT, -- Type: Text | Version of User Defined NameTable.Surname
  NicknameMP TEXT -- Type: Text | Version of User Defined NameTable.Surname
);

-- ============================================================================
-- PlaceTable
-- ============================================================================
CREATE TABLE PlaceTable(
  PlaceID INTEGER PRIMARY KEY, -- Type: Integer | PK | Place Identification Number
  PlaceType INTEGER, -- Type: Integer | Values: 0,1,2 | 0 = Place, from Edit Person screen for a fact,  1 = LDS Temples, Built-In,  2...
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: Built-in or\nUser Defined | Place Name from Edit Place pane of Places window or the Fact Edit pane of Edi...
  Abbrev TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Abbreviated place name, from Edit Place pane of Places window (PlaceType = 0 ...
  Normalized TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Standardized place name from Edit Place pane of Places window (PlaceType = 0 ...
  Latitude INTEGER, -- Type: Integer | Values: 0,\n8-9 Digit Integer | Latitude in decimal degrees stored as an integer (ie multiplied by 1e7). Pre-...
  Longitude INTEGER, -- Type: Integer | Values: 0,\n8-9 Digit Integer | Longitude in decimal degrees stored as an integer (ie multiplied by 1e7). Pre...
  LatLongExact INTEGER, -- Type: Integer | Values: 0,1
  MasterID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | 0 for PlaceType = 0,1 PlaceID of Place, for PlaceType = 2 (Place Detail)
  Note TEXT, -- Type: Text | Values: User Defined | Place note, from Edit screen for PlaceType = 0 and 2.  User Interface support...
  Reverse TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: Built-in or\nUser Defined | Calculated field containing the reverse order of the comma-delimeted fields i...
  fsID INTEGER, -- Type: Integer
  anID INTEGER, -- Type: Integer
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- RoleTable
-- ============================================================================
CREATE TABLE RoleTable(
  RoleID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,… | RoleIDs = 1 – 58  are pre-defined in built-in Fact Types
  RoleName TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: Built-in or\nUser Defined | Role name, from Edit Role Type window. Displays with fact in Edit Person wind...
  EventType INTEGER, -- Type: Integer | FK | Values: 1,2,3,… | Event Type, links to FactTypeID in FactTypeTable
  RoleType INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Sentence TEXT, -- Type: Text | Values: Sentence Template Language | Sentence template for this role, from Edit Fact Type/Edit Role Type screen. U...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- SourceTable
-- ============================================================================
CREATE TABLE SourceTable(
  SourceID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Source Identification Number
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Source Name, from Edit Source pane or Edit Citation pane
  RefNumber TEXT, -- Type: Text | Values: User Defined | Source Ref#, from Edit Source pane or Edit Citation pane
  ActualText TEXT, -- Type: Text | Values: User Defined | Source Text, from Edit Source pane or Edit Citation pane
  Comments TEXT, -- Type: Text | Values: User Defined | Source Comment,  from Edit Source pane or Edit Citation pane
  IsPrivate INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  TemplateID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | Template Identification Number: 0 = Free-Form,  Else, links to TemplateID in ...
  Fields BLOB, -- Type: Blob | Values: XML | Master Source Field \Names\  (from Source template) and \Values\ (from Edit S...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- SourceTemplateTable
-- ============================================================================
CREATE TABLE SourceTemplateTable(
  TemplateID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,… | Template Identification Number: 1 - 439 = Built-In (See Source Template windo...
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: Built-in or\nUser Defined | Template Name, from Source Template window. Only user-defined templates are e...
  Description TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Description Details, from Source Template Description window. Only user-defin...
  Favorite INTEGER, -- Type: Integer | Values: 0,1 | 0 = Not a Favorite (Default), 1 = Template starred as Favorite from Select So...
  Category TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Category Details, from Source Template Description window. Only user-defined ...
  Footnote TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Footnote Template, from Source Templates window. User Interface supports line...
  ShortFootnote TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Short Footnote Template, from Source Template window. User Interface supports...
  Bibliography TEXT, -- Type: Text | Values: Built-in or\nUser Defined | Bibliography Template, from Source Template window. User Interface supports l...
  FieldDefs BLOB, -- Type: Blob | Values: XML | From Source Template Field window: Field Name, Display Name, Field Type, Brie...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- TagTable
-- ============================================================================
CREATE TABLE TagTable(
  TagID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Tag Identification Number
  TagType INTEGER, -- Type: Integer | Values: 0,1 | 0 = Group, 1 = Folder
  TagValue INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | If TagValue >1000, links to GroupTable.GroupID Else, incremental placeholder ...
  TagName TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Name of Group or Task Folder
  Description TEXT, -- Type: Text | Values: User Defined | Description of Task Folder, Blank for Groups.
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- TaskLinkTable
-- ============================================================================
CREATE TABLE TaskLinkTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Link Identification Number
  TaskID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Links to TaskID in TaskTable
  OwnerType INTEGER, -- Type: Integer | Values: 0,1,2,5,7,14,18,19 | 0 = Person, 1 = Family, 2 = Event, 5 = Place,  7 = Name,  14 = Place Detail, ...
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Link based on OwnerType: 0 = PersonTable.PersonID, 1 = FamilyTable.FamilyID, ...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- TaskTable
-- ============================================================================
CREATE TABLE TaskTable(
  TaskID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Task Identification Number
  TaskType INTEGER, -- Type: Integer | Values: 0,1,2,3 | From Add Task window or Edit Task pane: 0 = Blank, 1 = Research,  2 = ToDo,  ...
  RefNumber TEXT, -- Type: Text | Values: User Defined | Reference #, from Add Task window or Edit Task pane.
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | Name, from Add Task window or Edit Task pane. 
  Status INTEGER, -- Type: Integer | Values: 0,1,2,3,4,5 | Status, From Add Task window or Edit Task pane: 0 = New, 1 = In Progress, 2 =...
  Priority INTEGER, -- Type: Integer | Values: 0,1,2,3,4,5,6,7 | From Add Task window or Edit Task pane: 0 = Priority 1 (Highest), 1 = Priorit...
  Date1 TEXT, -- Type: Text | Values: Position coded string or free text | Start Date, from Edit Task screen. [See Date sheet for additional details.] 
  Date2 TEXT, -- Type: Text | Values: Position coded string or free text | Last Edit Date, from Edit Task screen. [See Date sheet for additional details.] 
  Date3 TEXT, -- Type: Text | Values: Position coded string or free text | End Date, from Edit Task screen. [See Date sheet for additional details.] 
  SortDate1 BIGINT, -- Type: BigInt | Values: 0 or\n19 digit number
  SortDate2 BIGINT, -- Type: BigInt | Values: 0 or\n19 digit number
  SortDate3 BITINT, -- Type: BigInt | Values: 0 or\n19 digit number
  Filename TEXT, -- Type: Text | Values: User Defined | File name and path, from Add Task window or Edit Task pane. 
  Details TEXT, -- Type: Text | Values: User Defined | Details, from Add Task window or Edit Task pane.  User Interface supports lin...
  Results TEXT, -- Type: Text | Values: User Defined | Results, from Add Task window or Edit Task pane.  User Interface supports lin...
  UTCModDate FLOAT, -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
  Exclude INTEGER -- Type: Integer | Values: 0,1 | From Filter Tasks window: 0 = Display Task in list (default), 1= Filter from ...
);

-- ============================================================================
-- URLTable
-- ============================================================================
CREATE TABLE URLTable(
  LinkID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Link or WebTag Identification Number
  OwnerType INTEGER, -- Type: Integer | Values: 3,4,5,6,14 | Owner Type: 3 = Source, 4 = Citation, 5 = Place, 6 = Task, 14 = Place Details
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Owner Identification, link based on OwnerType: 3 = SourceTable.SourceID, 4 = ...
  LinkType INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Name TEXT, -- Type: Text | Values: User Defined | Name, from Edit Web Tag window
  URL TEXT, -- Type: Text | Values: User Defined | URL, from Edit Web Tag window
  Note TEXT, -- Type: Text | Values: User Defined | Note, from Edit Web Tag window.  User Interface supports line breaks and form...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- WitnessTable
-- ============================================================================
CREATE TABLE WitnessTable(
  WitnessID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Witness Identification Number
  EventID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Event Identification Number, linking to EventID of EventTable
  PersonID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | Person that the fact has been shared with: 0 = This person is NOT in RM datab...
  WitnessOrder INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Role INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Role, from Edit shared event screen, Links to RoleID in RoleTable
  Sentence TEXT, -- Type: Text | Values: Sentence Template Language | From Edit Person window of person that the fact has been shared with: Blank (...
  Note TEXT, -- Type: Text | Values: User Defined | Note, from Edit Witness pane of Edit Person window for person that the fact h...
  Given TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | From Edit Witness pane of Edit Person window for person that the fact has bee...
  Surname TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: User Defined | From Edit Witness pane of Edit Person window for person that the fact has bee...
  Prefix TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Not Implemented
  Suffix TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Not Implemented
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- FANTypeTable
-- ============================================================================
CREATE TABLE FANTypeTable(
  FANTypeID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1-15, 999 |  Association ID
  Name TEXT COLLATE RMNOCASE, -- Type: Text Collate RMNOCASE | Values: 1-15, 999 | Association Type, based on FANTypeID: 1 = Friends 2 = Neighbors  3 = Employme...
  Role1 TEXT, -- Type: Text | Values: 1-15, 999 | Role 1 and Role2 Names, based on FANTypeID: 1 = Friend / Friend  2 = Neighbor...
  Role2 TEXT, -- Type: Text | Values: 1-15, 999 | Role2 name (see FANTableType.Role1 above)
  Sentence1 TEXT, -- Type: Text | Values: Sentence Template Language | Template for Role1
  Sentence2 TEXT, -- Type: Text | Values: Sentence Template Language | Template for Role2
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- FANTable
-- ============================================================================
CREATE TABLE FANTable(
  FanID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | RecordID for Friends, Associations, Neighbours links in support of the Associ...
  ID1 INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Link to PersonTable.PersonID for node1 of association
  ID2 INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Link to PersonTable.PersonID for node2 of association
  FanTypeID INTEGER, -- Type: Integer | FK | Values: 1,2,3,... | Link to FANTypeTable.FanTypeID
  PlaceID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | 0 = Place Blank, Else, link to PlaceTable.PlaceID for PlaceType=0
  SiteID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | 0 = Place Blank, Else, link to PlaceTable.PlaceID for PlaceType=2
  Date TEXT, -- Type: Text | Values: Position coded string or free text | Date, from Associations. [See Date sheet for additional details.]
  SortDate BIGINT, -- Type: BigInT | Values: 18 digits | Number representing a user entered date that forces an event into a position ...
  Description TEXT, -- Type: Text | Values: User Defined | Description, from Association pane of Edit Person window. 
  Note TEXT, -- Type: Text | Values: User Defined | Note, from Association pane of Edit Person window. User Interface supports li...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- PayloadTable
-- ============================================================================
CREATE TABLE PayloadTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Record Identification Number
  RecType INTEGER, -- Type: Integer | Values: 3,4,5 | 3 = Saved Task Filter, 4 = Saved Search, 5 = Saved Group
  OwnerType INTEGER, -- Type: Integer | Values: 8,20 | 8 = Saved Search, 20 = Saved Group
  OwnerID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | Link based on RecType: 1 = \0\ (not used), 2 = GroupTable.GroupID, 3 = \0\ (n...
  Title TEXT, -- Type: Text | Values: User Defined | Saved Name of Search or Group
  DataRec BLOB, -- Type: Blob | Values: XML | Saved Criteria for Search or Group
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- CitationTable
-- ============================================================================
CREATE TABLE CitationTable(
  CitationID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3... | Citation Identification Number
  SourceID INTEGER, -- Type: Integer | FK | Values: 1,2,3... | Link to SourceID of SourceTable
  Comments TEXT, -- Type: Text | Values: User Defined | Detail Comment from Edit Citation pane. User Interface supports line breaks a...
  ActualText TEXT, -- Type: Text | Values: User Defined | Research Note from Edit Citation pane. User Interface supports line breaks an...
  RefNumber TEXT, -- Type: Text | Values: User Defined | Detail Ref# from Edit Citation pane.
  Footnote TEXT, -- Type: Text | Values: User Defined | Value from Customize Footnote window, overrides sentence template output. Use...
  ShortFootnote TEXT, -- Type: Text | Values: User Defined | Value from Customize Footnote window, overrides sentence template output. Use...
  Bibliography TEXT, -- Type: Text | Values: User Defined | Value from Customize Footnote window, overrides sentence template output. Use...
  Fields BLOB, -- Type: Blob | Values: XML | Citation Detail field “Names” (from Source template) and “Values” (from Edit ...
  UTCModDate FLOAT, -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
  CitationName TEXT COLLATE RMNOCASE -- Type: Text Collate RMNOCASE | Values: User Defined | If left blank, field value is auto generated as the concatenation of all Cita...
);

-- ============================================================================
-- PersonTable
-- ============================================================================
CREATE TABLE PersonTable(
  PersonID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,... | Record Identification Number (RIN)
  UniqueID TEXT, -- Type: Text | Values: 36 Character\nHexidecimal | Unique Identification Number assigned to person
  Sex INTEGER, -- Type: Integer | Values: 0,1,2 | 0 = Male, 1 = Female, 2 = Unknown
  ParentID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | 0 = No Parents, Any other value = FamilyTable.FamilyID If person has more tha...
  SpouseID INTEGER, -- Type: Integer | FK | Values: 0,1,2,3,... | 0 = No Spouse, Any other value = FamilyTable.FamilyID If person has more than...
  Color INTEGER, -- Type: Integer | Values: 0-27 | Set Color for Color Set 1, from Color Coding window: 0 = None,  1 = Red,  2 =...
  Color1 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 2, from Color Coding window: See PersonTable.Color for values
  Color2 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 3, from Color Coding window: See PersonTable.Color for values
  Color3 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 4, from Color Coding window: See PersonTable.Color for values
  Color4 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 5, from Color Coding window: See PersonTable.Color for values
  Color5 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 6, from Color Coding window: See PersonTable.Color for values
  Color6 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 7, from Color Coding window: See PersonTable.Color for values
  Color7 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 8, from Color Coding window: See PersonTable.Color for values
  Color8 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 9, from Color Coding window: See PersonTable.Color for values
  Color9 INTEGER, -- Type: Integer | Values: 0-27 | Color Set 10, from Color Coding window: See PersonTable.Color for values
  Relate1 INTEGER, -- Type: Integer | Values: 0-999 | Relate1, number of generations from this person to Most Recent Common Ancesto...
  Relate2 INTEGER, -- Type: Integer | Values: 0,1,2,3,... | Relate2, number of generations from the person chosen via Tools > Set Relatio...
  Flags INTEGER, -- Type: Integer | Values: 0-10 | Prefix description added to Set Relationship display as defined by Relate1/Re...
  Living INTEGER, -- Type: Integer | Values: 0,1 | Living, from Edit Person window: 0 = Deceased,  1 = Living
  IsPrivate INTEGER, -- Type: Integer | Values: 0.0 | Not Implementd
  Proof INTEGER, -- Type: Integer | Values: 0.0 | Not implemented
  Bookmark INTEGER, -- Type: Integer | Values: 0,1 | Bookmark, from Sidebar Bookmarks view: 0 = Not Bookmarked, 1 = Bookmarked
  Note TEXT, -- Type: Text | Values: User Defined | Note field from Edit Person screen, Person Fact. User Interface supports line...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- DNATable
-- ============================================================================
CREATE TABLE DNATable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1, 2, 3… | Record Identification Number
  ID1 INTEGER, -- Type: Integer | FK | Values: 1, 2, 3… | Person 1, from the DNA Match view of Edit Person Window.  Links to PersonTabl...
  ID2 INTEGER, -- Type: Integer | FK | Values: 1, 2, 3… | Person 2, from the DNA Match view of Edit Person Window.  Links to PersonTabl...
  Label1 TEXT, -- Type: Text | Values: User Defined | Label 1, from the DNA Match view of Edit Person Window.  
  Label2 TEXT, -- Type: Text | Values: User Defined | Label 2, from the DNA Match view of Edit Person Window.  
  DNAProvider INTEGER, -- Type: Integer | Values: 1-6, 998, 999 | Provider, from the DNA Match view of Edit Person Window: 1 = 23andMe, 2 = Anc...
  SharedCM FLOAT, -- Type: Float | Values: User Defined,\n0-4000 | Shared Centimorgans (cM), from the DNA Match view of Edit Person Window.
  SharedPercent FLOAT, -- Type: Float | Values: User Defined,\n0-100 | Shared Percentage, from the DNA Match view of Edit Person Window.
  LargeSeg FLOAT, -- Type: Float | Values: User Defined,\n0-500 | Largest Segment (cM), from the DNA Match view of Edit Person Window.
  SharedSegs INTEGER, -- Type: Integer | Values: User Defined,\n0-100 | Shared Segments, from the DNA Match view of Edit Person Window.
  Date TEXT, -- Type: Text | Values: Position coded string or free text | [See Date sheet for additional details.]
  Relate1 INTEGER, -- Type: Integer | Values: 0-999 | Relate1, the number of generations between Person 1 (DNATable.ID1) and the Mo...
  Relate2 INTEGER, -- Type: Integer | Values: 0,1,2,... | Relate2, the number of generations between Person 2 (DNATable.ID2) and the Mo...
  CommonAnc INTEGER, -- Type: Integer | FK | Values: 0,1,2,... | Most Recent Common Ancestor (MRCA) of Person1 and Person2 of the DNA Match. L...
  CommonAncType INTEGER, -- Type: Integer | Values: 0,1 | Common Ancestor Type. When DNATable.CommonAnc > 0:  0 = Single MRCA (ie Half ...
  Verified INTEGER, -- Type: Integer | Values: 0.0 | Not Implemented
  Note TEXT, -- Type: Text | Values: User Defined | DNA Note, from the DNA Match view of Edit Person Window.   User Interface sup...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- HealthTable
-- ============================================================================
CREATE TABLE HealthTable(
  RecID INTEGER PRIMARY KEY, -- Type: Integer | PK | Values: 1,2,3,… | Record Identification Number
  OwnerID INTEGER, -- Type: Integer | FK | Values: 1,2,3,… | Links to PersonID in the PersonTable
  Condition INTEGER, -- Type: Integer | Values: 1-20, 999 | Condition, from the Health Condition view of the Edit Person window: 1= Infec...
  SubCondition TEXT, -- Type: Text | Values: User Defined | Details, from the Health Condition view of the Edit Person window.
  Date FLOAT, -- Type: Float | Values: Position coded string or free text | [See Date sheet for additional details.]
  Note TEXT, -- Type: Text | Values: User Defined | Health Note, from the Health Condition view of the Edit Person window. User I...
  UTCModDate FLOAT -- Type: Float | Values: [d]{5}.[d]{10}\ne.g.: 44993.9143704283 | Coordinated Universal Time from system, modified:  SELECT julianday('now') - ...
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX idxAddressName ON AddressTable(Name);
CREATE INDEX idxLinkAncestryRmId ON AncestryTable(rmID);
CREATE INDEX idxLinkAncestryanID ON AncestryTable(anID);
CREATE INDEX idxChildID ON ChildTable(ChildID);
CREATE INDEX idxChildFamilyID ON ChildTable(FamilyID);
CREATE INDEX idxChildOrder ON ChildTable(ChildOrder);
CREATE INDEX idxCitationLinkOwnerID ON CitationLinkTable(OwnerID);
CREATE INDEX idxRecType ON ConfigTable(RecType);
CREATE INDEX idxOwnerEvent ON EventTable(OwnerID,EventType);
CREATE INDEX idxOwnerDate ON EventTable(OwnerID,SortDate);
CREATE UNIQUE INDEX idxExclusionIndex ON ExclusionTable(
  ExclusionType,
  ID1,
  ID2
);
CREATE INDEX idxFactTypeName ON FactTypeTable(Name);
CREATE INDEX idxFactTypeAbbrev ON FactTypeTable(Abbrev);
CREATE INDEX idxFactTypeGedcomTag ON FactTypeTable(GedcomTag);
CREATE INDEX idxLinkRmId ON FamilySearchTable(rmID);
CREATE INDEX idxLinkfsID ON FamilySearchTable(fsID);
CREATE INDEX idxFamilyFatherID ON FamilyTable(FatherID);
CREATE INDEX idxFamilyMotherID ON FamilyTable(MotherID);
CREATE INDEX idxMediaOwnerID ON MediaLinkTable(OwnerID);
CREATE INDEX idxMediaFile ON MultimediaTable(MediaFile);
CREATE INDEX idxMediaURL ON MultimediaTable(URL);
CREATE INDEX idxNameOwnerID ON NameTable(OwnerID);
CREATE INDEX idxSurname ON NameTable(Surname);
CREATE INDEX idxGiven ON NameTable(Given);
CREATE INDEX idxSurnameGiven ON NameTable(
  Surname,
  Given,
  BirthYear,
  DeathYear
);
CREATE INDEX idxNamePrimary ON NameTable(IsPrimary);
CREATE INDEX idxSurnameMP ON NameTable(SurnameMP);
CREATE INDEX idxGivenMP ON NameTable(GivenMP);
CREATE INDEX idxSurnameGivenMP ON NameTable(
  SurnameMP,
  GivenMP,
  BirthYear,
  DeathYear
);
CREATE INDEX idxPlaceName ON PlaceTable(Name);
CREATE INDEX idxReversePlaceName ON PlaceTable(Reverse);
CREATE INDEX idxPlaceAbbrev ON PlaceTable(Abbrev);
CREATE INDEX idxRoleEventType ON RoleTable(EventType);
CREATE INDEX idxSourceName ON SourceTable(Name);
CREATE INDEX idxSourceTemplateName ON SourceTemplateTable(Name);
CREATE INDEX idxTagType ON TagTable(TagType);
CREATE INDEX idxTaskOwnerID ON TaskLinkTable(OwnerID);
CREATE INDEX idxTaskName ON TaskTable(Name);
CREATE INDEX idxWitnessEventID ON WitnessTable(EventID);
CREATE INDEX idxWitnessPersonID ON WitnessTable(PersonID);
CREATE INDEX idxFANTypeName ON FANTypeTable(Name);
CREATE INDEX idxFanId1 ON FANTable(ID1);
CREATE INDEX idxFanId2 ON FANTable(ID2);
CREATE INDEX idxPayloadType ON PayloadTable(RecType);
CREATE INDEX idxCitationSourceID ON CitationTable(SourceID);
CREATE INDEX idxCitationName ON CitationTable(CitationName);
CREATE INDEX idxDnaId1 ON DNATable(ID1);
CREATE INDEX idxDnaId2 ON DNATable(ID2);
CREATE INDEX idxHealthOwnerId ON HealthTable(OwnerID);
