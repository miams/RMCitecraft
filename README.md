# RMCitecraft

Census Citation Assistant for RootsMagic

## Getting Started

### Installation

RMCitecraft requires Python 3.11+ and UV package manager.

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install RMCitecraft
uv sync
```

### Running the Application

```bash
# Show version and last updated timestamp
rmcitecraft version

# Check if application is running
rmcitecraft status

# Start in foreground mode (interactive)
rmcitecraft start

# Start in background mode (daemon)
rmcitecraft start -d

# Stop the application
rmcitecraft stop

# Restart (stop + start in background)
rmcitecraft restart

# Show help
rmcitecraft help
```

### Version Information

The CLI always displays the current version and last code update timestamp:

```
RMCitecraft v0.1.0
Last updated: 2025-10-25 16:59:28
```

---

<H1>Objective</H1>

The objective is for a desktop application support Rootsmagic with census processing.  Specifically in two areas.

- In census records, replace placeholder FamilySearch footnote, short footnote and bibiography entries, with real, <i>Evidence Explained</i> compliant entries.  In some instances, additional data will need to be gathered by the user, for instance when the Enumeration District is not present.  In such situations, the application should provide a UI with a prompt, requesting the missing information, and display the webpage of the associated URL from FamilySearch, assisting the user with gathering and inputing the data.
- When a census image is not included for a census in RootsMagic, the application should display the webpage of the associated URL from FamilySearch, and monitor a download file folder.  When an image is downloaded to monitored file folder location, the following actions occur:
    A) The file is renamed using a standard schema.
    B) The file is moved to Rootsmagic artifact sub-folder approriate for that census record.
    C) Rootsmagic database is updated
  - Media Type: Image
  - Filename: as appropriate
  - Caption:  as appropriate
  - Tag: linking to the citation
  - Tag: linking to the census event

The RootsMagic database use SQLite.  Python is a good option.  This will run a Macbook M3 Pro.  I would like a modern, UI, with a very good UX experience.

<H1>Data Fields</H1>

- ## Existing RootsMagic Fields.

​	**RM Source Name:**
​	**RM Family Search Entry:**

- ## **Application Generated Fields**

​	**RM Footnote:**
​	**RM Short Footnote:**
​	**RM Bibliography:**

<H1>Citation Examples</H1>

**RM Source Name:**  
Fed Census: 1900, Ohio, Noble [citing sheet 3B, family 57] Ijams, Ella

**RM Family Search Entry:** 
"United States Census, 1900," database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015), Ella Ijams, Olive Township Caldwell village, Noble, Ohio, United States; citing sheet 3B, family 57, NARA microfilm publication T623 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,241,311.

**RM Footnote:** 
1900 U.S. census, Noble County, Ohio, population schedule, Olive Township Caldwell village, enumeration district (ED) 95, sheet 3B, family 57, Ella Ijams; imaged, "1900 United States Federal Census," <i>FamilySearch</i> (https://familysearch.org/ark:/61903/1:1:MM6X-FGZ : accessed 24 July 2015).

**RM Short Footnote:**
1900 U.S. census, Noble Co., Oh., pop. sch., Olive Township, E.D. 95, sheet 3B, Ella Ijams.

**RM Bibliography:**
U.S. Ohio. Noble County. 1900 U.S Census. Population Schedule. Imaged. "1900 United States Federal Census". <i>FamilySearch</i> https://www.familysearch.org/ark:/61903/1:1:MM6X-FGZ : 2015.

---

**RM Source Name:** 
Fed Census: 1910, Maryland, Baltimore [citing enumeration district (ED) ED 214, sheet 3B] Ijams, William H.

**RM Family Search Entry:** 
"United States Census, 1910," database with images, *FamilySearch*(https://familysearch.org/ark:/61903/1:1:M2F4-SVS : accessed 27 November 2015), William H Ijams in household of Margaret E Brannon, Baltimore Ward 13, Baltimore (Independent City), Maryland, United States; citing enumeration district (ED) ED 214, sheet 3B, NARA microfilm publication T624 (Washington, D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,374,570.

**RM Footnote:** 
1910 U.S. census, Baltimore City, Maryland, population schedule, Baltimore Ward 13, enumeration district (ED) 214, sheet 3B, family 52, William H. Ijams; imaged, "1910 United States Federal Census," <i>FamilySearch</i> (https://www.familysearch.org/ark:/61903/1:1:M2F4-SV9 : accessed 27 November 2015).

**RM Short Footnote:**
1910 U.S. census, Baltimore City, Md., pop. sch., Baltimore Ward 13, E.D. 214, sheet 3B, William H. Ijams.

**RM Bibliography:**
U.S. Maryland. Baltimore City. 1910 U.S Census. Population Schedule. Imaged. "1910 United States Federal Census". <i>FamilySearch</i> https://www.familysearch.org/ark:/61903/1:1:M2F4-SV9 : 2015.

---





IGNORE EVERYTHING BELOW THIS LINE.  THIS IS WORK IN PROGRESS

**RM Source Name:**
Fed Census: 1920, California, Los Angeles [citing sheet 11A, family 250] Ijams, William F.

**RM Family Search Entry:**
"United States Census, 1920," database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:MHQX-8QQ : accessed 28 July 2015), William F Ijams, Los Angeles Assembly District 61, Los Angeles, California, United States; citing sheet 11A, family 250, NARA microfilm publication T625 (Washington D.C.: National Archives and Records Administration, n.d.); FHL microfilm 1,820,105.

**RM Footnote:**

**RM Short Footnote:**
**RM Bibliography:**



---

**Current Family Search Entry:**
**RM Source Name:**
**RM Family Search Entry:**
**RM Footnote:**
**RM Short Footnote:**
**RM Bibliography:**




   "United States, Census, 1930", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:X3MM-CX5 : Fri Mar 08 08:10:13 UTC 2024), Entry for William H Ijams and Dorothy Ijams, 1930.


   "United States, Census, 1940", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:VYLP-MHZ : Tue Jan 21 20:16:52 UTC 2025), Entry for William A Ijams and Edwin G Ijams, 1940.


   "United States, Census, 1950", FamilySearch (https://www.familysearch.org/ark:/61903/1:1:6XLR-BM85 : Tue Mar 19 07:39:27 UTC 2024), Entry for Edward W Ratekin and Mary L Ratekin, 15 April 1950.



2)  Processing a downloaded census image.  It is a two step process.  
    A) rename the downloaded file, to a structured filename:

    census year, State, County - Surname, GivenName.jpg


Examples are:
  1940, Texas, Milam - Iiams, Frank W..jpg
  1940, Washington, Benton - Fox, Harvey.jpg
  1940, Washington, Clark - Iams, Elizabeth.jpg
  1940, Washington, King - Osterholm, Vendla.jpg

  B) Move the renamed image into the correct directory in "/Users/miams/Genealogy/RootsMagic/Files/Records - Census"  Below is the directory structure.

➜  Records - Census tree -d
.
├── 1790 Federal
├── 1800 Federal
├── 1810 Federal
├── 1820 Federal
│   └── metadata
├── 1830 Federal
├── 1840 Federal
├── 1850 Federal
├── 1850 Federal Slave Schedule
├── 1855 New York
├── 1860 Federal
├── 1860 Federal Slave Schedule
├── 1865 New York
├── 1870 Federal
├── 1875 New York
├── 1880 Federal
├── 1885 Colorado
├── 1885 Iowa
├── 1885 New Jersey
├── 1890 Federal
├── 1890 Federal Veterans and Widows Schedule
├── 1895 Iowa
├── 1900 Federal
├── 1910 Federal
├── 1920 Federal
├── 1925 Iowa
├── 1930 Federal
├── 1940 Federal
├── 1945 Florida
├── 1950 Federal
└── Federal Mortality Schedule 1850-1885
    ├── 1850 Mortality
    ├── 1860 Mortality
    ├── 1870 Mortality
    └── 1880 Mortality
