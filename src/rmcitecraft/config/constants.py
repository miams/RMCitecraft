"""Constants for census years, folder mappings, and state abbreviations."""

from typing import Dict, List

# Valid US Federal Census years (1790-1950, every 10 years)
CENSUS_YEARS: List[int] = list(range(1790, 1960, 10))

# Census year template ranges
CENSUS_YEAR_RANGES = {
    "1790-1840": list(range(1790, 1850, 10)),
    "1850-1880": list(range(1850, 1890, 10)),
    "1890": [1890],
    "1900-1950": list(range(1900, 1960, 10)),
}

# Folder mappings for census years and schedule types
FOLDER_MAPPINGS: Dict[str, str] = {
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

# US State abbreviations (standard 2-letter postal codes)
STATE_ABBREVIATIONS: Dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    # Historical territories and districts
    "District of Columbia": "DC",
    "Dakota Territory": "DT",
    "Indian Territory": "IT",
    "Nebraska Territory": "NT",
    "New Mexico Territory": "NMT",
    "Oklahoma Territory": "OT",
    "Washington Territory": "WT",
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
