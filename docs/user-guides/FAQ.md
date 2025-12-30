---
priority: essential
topics: [faq, questions, help]
---

# Frequently Asked Questions

## General Questions

### What is RMCitecraft?

RMCitecraft is a tool that automates citation formatting and image management for US Federal Census records in RootsMagic genealogy databases. It extracts data from FamilySearch, formats citations according to *Evidence Explained* standards, and organizes census images.

### What RootsMagic versions are supported?

RMCitecraft works with RootsMagic 8, 9, 10, and 11. All versions use the same SQLite database format.

### Is RMCitecraft free?

Yes, RMCitecraft is open-source software released under the MIT license.

### Does RMCitecraft work on Windows?

Currently, RMCitecraft is macOS-only. Windows support is planned for a future release.

### Do I need programming experience?

Basic comfort with the command line is helpful for installation, but day-to-day use is through a graphical interface.

---

## Setup Questions

### Why do I need to start Chrome with special flags?

RMCitecraft uses Playwright to automate browser interactions. The `--remote-debugging-port=9222` flag enables the Chrome DevTools Protocol, which allows RMCitecraft to control the browser programmatically while using your existing FamilySearch login session.

### Can I use Safari or Firefox instead of Chrome?

No, RMCitecraft specifically uses Chrome's DevTools Protocol. Chrome (or Chromium-based browsers) is required.

### Why do I need a separate Chrome profile?

The `--user-data-dir` flag creates an isolated profile that:
- Keeps your regular browsing separate
- Stores your FamilySearch login persistently
- Prevents conflicts with existing extensions or settings

### Do I need an LLM API key?

An API key (Anthropic or OpenAI) is optional. It enables AI-powered census image transcription, which can automatically extract household data. Without it, you can still process citations manually.

---

## Database Questions

### Will RMCitecraft modify my RootsMagic database?

Yes, RMCitecraft writes formatted citations and media links to your database. **Always work on a copy** of your database, not your production file.

### How do I merge changes back to my main database?

After processing, you can:
1. Replace your production database with the working copy
2. Or use RootsMagic's import features to selectively merge changes

### What's this RMNOCASE error I keep seeing?

RootsMagic databases use a custom collation called RMNOCASE for case-insensitive sorting. RMCitecraft loads an ICU extension to provide this. If you see this error, you're using a direct SQLite connection instead of RMCitecraft's `connect_rmtree()` function.

### Can I use RMCitecraft with multiple databases?

Yes, but only one at a time. Change the `RM_DATABASE_PATH` in your `.env` file to switch databases.

---

## Citation Questions

### What citation style does RMCitecraft use?

RMCitecraft follows *Evidence Explained* by Elizabeth Shown Mills, the standard reference for genealogical citations. See the [Citation Style Guide](../reference/CITATION-STYLE-GUIDE.md) for details.

### Why are there three citation forms?

*Evidence Explained* recommends three forms:
- **Footnote**: Full citation for first reference
- **Short Footnote**: Abbreviated form for subsequent references
- **Bibliography**: Hierarchical format for source lists

### What source name format does RMCitecraft expect?

Sources should be named:
```
Fed Census: YYYY, State, County [citing details] Surname, GivenName
```

This is the format RootsMagic uses when accepting FamilySearch hints.

### Can RMCitecraft process non-census records?

Currently, RMCitecraft supports:
- US Federal Census (1790-1950)
- Find a Grave memorials

Other record types (vital records, military, etc.) are planned for future releases.

### What about slave schedules and mortality schedules?

Yes, RMCitecraft handles these special schedule types:
- Slave schedules (1850, 1860): Source name begins with `Fed Census Slave Schedule:`
- Mortality schedules (1850-1880): Source name begins with `Fed Census Mortality Schedule:`

---

## Processing Questions

### How does RMCitecraft identify incomplete citations?

A citation is "incomplete" if:
- It has a FamilySearch URL but no formatted footnote
- The footnote and short footnote are identical
- Required fields (like ED for 1900+ censuses) are missing

### What if FamilySearch doesn't have a field indexed?

You can manually enter missing fields (like ED or line number) while viewing the census image in RMCitecraft.

### Can I process citations without images?

Yes, image download is optional. You can format citations without downloading images, or add images later.

### What happens if I skip a citation?

Skipped citations remain in the "Incomplete" state and can be processed later.

### How do I resume an interrupted batch?

RMCitecraft automatically saves progress. Restart the application, go to Batch Processing, and click "Resume."

---

## Image Questions

### Where are census images stored?

Images are stored in year-specific folders:
```
~/Genealogy/RootsMagic/Files/Records - Census/YYYY Federal/
```

### What's the image naming convention?

```
YYYY, State, County - Surname, GivenName.ext
```
Example: `1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg`

### Can I change the image storage location?

Yes, set `RM_MEDIA_ROOT_DIRECTORY` in your `.env` file.

### What image formats are supported?

JPG, PNG, PDF, and TIFF files are supported.

### How much disk space do census images use?

Average census image: 300-500 KB. A collection of 1,000 images uses approximately 400 MB.

---

## Technical Questions

### What's the difference between the working database and census.db?

- **Working database** (`.rmtree`): Your RootsMagic data (copy)
- **census.db** (`~/.rmcitecraft/census.db`): RMCitecraft's extracted census data, including household members and transcriptions

### What's stored in ~/.rmcitecraft/?

```
~/.rmcitecraft/
├── batch_state.db      # Batch processing state (resume capability)
├── census.db           # Extracted census data and transcriptions
└── logs/               # Application logs
```

### Can I back up the RMCitecraft state?

Yes, copy the `~/.rmcitecraft/` directory. This preserves your batch progress and census extraction data.

### How do I completely reset RMCitecraft state?

```bash
rm -rf ~/.rmcitecraft/
```

This removes all saved state. Your RootsMagic database is not affected.

---

## Error Questions

### "Connection refused" when starting batch

Chrome isn't running with debugging enabled. Run:
```bash
~/start-chrome.sh
```

### "FamilySearch requires login"

Your session expired. Switch to the Chrome window and log into FamilySearch.

### "No citations found"

Check that:
1. Your source names follow the expected pattern
2. You're connected to the correct database
3. Citations for that year actually exist

### "RMNOCASE" error

You're using raw SQLite. Use RMCitecraft's connection function:
```python
from rmcitecraft.database.connection import connect_rmtree
```

---

## Support

### Where can I report bugs?

[GitHub Issues](https://github.com/miams/RMCitecraft/issues)

### Where's the documentation?

- User Guides: `docs/user-guides/`
- Reference: `docs/reference/`
- Architecture: `docs/architecture/`

### How can I contribute?

See `CONTRIBUTING.md` in the repository root (if available), or open a GitHub issue to discuss your contribution.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
