"""
RMCitecraft - RootsMagic Census Citation Assistant

A desktop application for transforming FamilySearch census citations into
Evidence Explained format and automating census image management.
"""

__version__ = "0.1.0"
__author__ = "RMCitecraft Contributors"

# State abbreviations for short footnotes
# Traditional genealogy abbreviations, not USPS codes
STATE_ABBREVIATIONS = {
    "Alabama": "Ala.",
    "Alaska": "Alaska",
    "Arizona": "Ariz.",
    "Arkansas": "Ark.",
    "California": "Calif.",
    "Colorado": "Colo.",
    "Connecticut": "Conn.",
    "Delaware": "Del.",
    "District of Columbia": "D.C.",
    "Florida": "Fla.",
    "Georgia": "Ga.",
    "Hawaii": "Hawaii",
    "Idaho": "Idaho",
    "Illinois": "Ill.",
    "Indiana": "Ind.",
    "Iowa": "Iowa",
    "Kansas": "Kan.",
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
    "Nebraska": "Neb.",
    "Nevada": "Nev.",
    "New Hampshire": "N.H.",
    "New Jersey": "N.J.",
    "New Mexico": "N.M.",
    "New York": "N.Y.",
    "North Carolina": "N.C.",
    "North Dakota": "N.D.",
    "Ohio": "Oh.",
    "Oklahoma": "Okla.",
    "Oregon": "Ore.",
    "Pennsylvania": "Penn.",
    "Rhode Island": "R.I.",
    "South Carolina": "S.C.",
    "South Dakota": "S.D.",
    "Tennessee": "Tenn.",
    "Texas": "Tex.",
    "Utah": "Utah",
    "Vermont": "Vt.",
    "Virginia": "Va.",
    "Washington": "Wash.",
    "West Virginia": "W.Va.",
    "Wisconsin": "Wis.",
    "Wyoming": "Wyo.",
}

# Supported census years (1890 excluded - most records destroyed)
SUPPORTED_CENSUS_YEARS = [
    1790, 1800, 1810, 1820, 1830, 1840,
    1850, 1860, 1870, 1880,
    1900, 1910, 1920, 1930, 1940, 1950
]

# Confidence thresholds for extraction quality
CONFIDENCE_HIGH = 0.9  # Green indicator
CONFIDENCE_MEDIUM = 0.8  # Yellow indicator
# Below 0.8 = Low confidence (red indicator, requires review)
