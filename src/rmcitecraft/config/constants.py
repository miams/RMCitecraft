"""Constants for census years, folder mappings, and state abbreviations."""


# Valid US Federal Census years (1790-1950, every 10 years)
CENSUS_YEARS: list[int] = list(range(1790, 1960, 10))

# Census year template ranges
CENSUS_YEAR_RANGES = {
    "1790-1840": list(range(1790, 1850, 10)),
    "1850-1880": list(range(1850, 1890, 10)),
    "1890": [1890],
    "1900-1950": list(range(1900, 1960, 10)),
}

# Folder mappings for census years and schedule types
FOLDER_MAPPINGS: dict[str, str] = {
    # Standard federal census
    "1790_federal": "1790 Federal",
    "1800_federal": "1800 Federal",
    "1810_federal": "1810 Federal",
    "1820_federal": "1820 Federal",
    "1830_federal": "1830 Federal",
    "1840_federal": "1840 Federal",
    "1850_federal": "1850 Federal",
    "1860_federal": "1860 Federal",
    "1870_federal": "1870 Federal",
    "1880_federal": "1880 Federal",
    "1890_federal": "1890 Federal",
    "1900_federal": "1900 Federal",
    "1910_federal": "1910 Federal",
    "1920_federal": "1920 Federal",
    "1930_federal": "1930 Federal",
    "1940_federal": "1940 Federal",
    "1950_federal": "1950 Federal",
    # Slave schedules
    "1850_slave": "1850 Federal Slave Schedule",
    "1860_slave": "1860 Federal Slave Schedule",
    # Mortality schedules
    "1850_mortality": "Federal Mortality Schedule 1850-1885/1850 Mortality",
    "1860_mortality": "Federal Mortality Schedule 1850-1885/1860 Mortality",
    "1870_mortality": "Federal Mortality Schedule 1850-1885/1870 Mortality",
    "1880_mortality": "Federal Mortality Schedule 1850-1885/1880 Mortality",
    # Veterans schedule
    "1890_veterans": "1890 Federal Veterans and Widows Schedule",
}

# US State abbreviations (traditional style for Evidence Explained citations)
# Reference: Mills, Elizabeth Shown. Evidence Explained, 4th Edition.
# Note: These are NOT postal codes (PA → Pa., OH → Ohio, etc.)
STATE_ABBREVIATIONS: dict[str, str] = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    "Connecticut": "Conn.",
    "Delaware": "Del.",
    "Florida": "Fla.",
    "Georgia": "Ga.",
    "Hawaii": "Hawaii",
    "Idaho": "Idaho",
    "Illinois": "Ill.",
    "Indiana": "Ind.",
    "Iowa": "Iowa",
    "Kansas": "Kans.",
    "Kentucky": "Ky.",
    "Louisiana": "La.",
    "Maine": "Maine",
    "Maryland": "Md.",
    "Massachusetts": "Mass.",
    "Michigan": "Mich.",
    "Minnesota": "Minn.",
    "Mississippi": "Miss.",
    "Missouri": "Mo.",
    "Montana": "Mont.",
    "Nebraska": "Nebr.",
    "Nevada": "Nev.",
    "New Hampshire": "N.H.",
    "New Jersey": "N.J.",
    "New Mexico": "N.Mex.",
    "New York": "N.Y.",
    "North Carolina": "N.C.",
    "North Dakota": "N.Dak.",
    "Ohio": "Oh.",
    "Oklahoma": "Okla.",
    "Oregon": "Oreg.",
    "Pennsylvania": "Pa.",
    "Rhode Island": "R.I.",
    "South Carolina": "S.C.",
    "South Dakota": "S.Dak.",
    "Tennessee": "Tenn.",
    "Texas": "Tex.",
    "Utah": "Utah",
    "Vermont": "Vt.",
    "Virginia": "Va.",
    "Washington": "Wash.",
    "West Virginia": "W.Va.",
    "Wisconsin": "Wis.",
    "Wyoming": "Wyo.",
    # Historical territories and districts
    "District of Columbia": "D.C.",
    "Dakota Territory": "Dakota Terr.",
    "Indian Territory": "Indian Terr.",
    "Nebraska Territory": "Nebr. Terr.",
    "New Mexico Territory": "N.Mex. Terr.",
    "Oklahoma Territory": "Okla. Terr.",
    "Washington Territory": "Wash. Terr.",
}

# Locality type abbreviations for short footnotes (Evidence Explained style)
# Reference: Mills, Elizabeth Shown. Evidence Explained, 4th Edition.
LOCALITY_TYPE_ABBREVIATIONS: dict[str, str] = {
    "Township": "Twp.",
    "City": "City",  # Cities not abbreviated
    "Village": "Vill.",
    "Borough": "Boro.",
    "Town": "Town",  # Towns not abbreviated
    "Parish": "Par.",
    "District": "Dist.",
    "Precinct": "Prec.",
    "Ward": "Ward",  # Wards not abbreviated (numbered)
    "Hundred": "Hund.",
    "Independent City": "Indep. City",
}

# Schedule types
SCHEDULE_TYPES = {
    "population": "Population",
    "slave": "Slave",
    "mortality": "Mortality",
    "veterans": "Veterans and Widows",
}

# Census years that require Enumeration District (ED)
ED_REQUIRED_YEARS = list(range(1880, 1960, 10))
