---
priority: reference
topics: [database, census, citation, batch, ui]
---

# Census Image Workflow Guide

**For**: RMCitecraft Users
**Version**: 1.0
**Last Updated**: 2025-01-29

## Overview

This guide explains how RMCitecraft automates the process of downloading, organizing, and linking census images from FamilySearch to your RootsMagic database.

### What Gets Automated

✅ **Downloading** census images from FamilySearch
✅ **Renaming** files with standardized names
✅ **Organizing** images into year-specific folders
✅ **Linking** images to census events
✅ **Linking** images to citations

### What You Do

👤 **Extract citation** from FamilySearch (1 click)
👤 **Review and save** citation data (1 click)
👤 **Download missing images** for existing citations (1 click)

---

## Workflow 1: New Citation with Image (Most Common)

### Step-by-Step

**1. Visit FamilySearch Census Page**

Open the census record in your browser:
```
https://familysearch.org/ark:/61903/1:1:XXXX-XXX
```

**2. Click "Extract Citation" in Browser Extension**

The extension button appears in your browser toolbar. One click extracts:
- Person name
- Census year and location
- Enumeration district, sheet, family numbers
- FamilySearch URL
- **Census image (automatic download)**

**3. Citation Appears in RMCitecraft**

Open RMCitecraft → **Pending Citations** tab

You'll see:
```
┌─────────────────────────────────────────────────┐
│  1930 Census - Jesse Dorsey Iams                │
│  Tulsa, Oklahoma                                 │
│  🖼️ Image: ⏳ Downloading...                    │
│  [Process]                                       │
└─────────────────────────────────────────────────┘
```

**4. Wait for Image (Optional - work on other citations)**

The image downloads in the background. When ready:
```
┌─────────────────────────────────────────────────┐
│  1930 Census - Jesse Dorsey Iams                │
│  Tulsa, Oklahoma                                 │
│  🖼️ Image: ✅ Ready                              │
│  [Process] [View Image]                          │
└─────────────────────────────────────────────────┘
```

**5. Click "Process" to Review**

A dialog opens with:
- **Left side**: Citation data and any missing fields
- **Right side**: Census image at 275% zoom (perfect for reading)

Fill in any missing fields while looking at the image.

**6. Click "Save to RootsMagic"**

One click:
- Formats citation (Footnote, Short Footnote, Bibliography)
- Saves to RootsMagic database
- Links image to census event
- Links image to citation

**✅ Done! Citation and image are both saved and linked.**

---

## Workflow 2: Download Image for Existing Citation

### When to Use

You have citations in RootsMagic but no images linked to them.

### How to Identify Missing Images

**In Citation Manager Tab**:
```
┌─────────────────────────────────────────────────┐
│  📋 1930 Census Citations                        │
│                                                  │
│  ⚠️  Jesse Dorsey Iams (No image) [Download]    │
│  ✅ Frank W Iiams (Image linked)                │
│  ⚠️  George B Iams (No image) [Download]        │
└─────────────────────────────────────────────────┘
```

### Step-by-Step

**1. Click [Download] Next to Citation**

**2. System Opens FamilySearch Page**

Your browser opens the FamilySearch URL from the citation.

**3. Extension Auto-Downloads Image**

The image downloads automatically (no action needed).

**4. RMCitecraft Processes Image**

- Detects downloaded file
- Renames: `1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg`
- Moves to: `~/Genealogy/RootsMagic/Files/Records - Census/1930 Federal/`
- Links to existing citation and census event

**5. Status Updates**

```
┌─────────────────────────────────────────────────┐
│  ✅ Jesse Dorsey Iams (Image linked)            │
└─────────────────────────────────────────────────┘
```

**✅ Done! Image is now linked to the existing citation.**

---

## Workflow 3: Bulk Download Missing Images

### When to Use

You have many citations without images and want to download them all at once.

### Step-by-Step

**1. Open Image Manager Tab**

Navigate to: **Image Manager** tab in RMCitecraft

**2. Review Missing Images**

```
┌──────────────────────────────────────────────────────┐
│  Image Manager - Missing Census Images              │
│                                                      │
│  Found 127 citations with missing images            │
│                                                      │
│  Filter: [Census Year ▾] [Person ▾] [Status ▾]     │
└──────────────────────────────────────────────────────┘
```

**3. Filter (Optional)**

- **By Year**: Show only 1930 census (10 images)
- **By Person**: Show only "Jesse Dorsey Iams" (3 images)
- **By Status**: Show only "Missing" (exclude failed)

**4. Select Citations**

```
┌──────────────────────────────────────────────────────┐
│  [✓] 1920 - Jesse D Iams     Tulsa, OK      🔗URL   │
│  [✓] 1930 - Jesse D Iams     Tulsa, OK      🔗URL   │
│  [✓] 1950 - Jesse D Iams     Tulsa, OK      🔗URL   │
│  [ ] 1910 - George B Iams    Greene, PA     🔗URL   │
└──────────────────────────────────────────────────────┘
```

Click checkboxes to select specific citations, or:
- **[Select All]** - Select all visible (filtered) citations
- **[Deselect All]** - Clear all selections

**5. Click [Download Selected]**

Button shows count: `[Download Selected Images (3)]`

**6. Monitor Progress**

```
┌──────────────────────────────────────────────────────┐
│  Downloading images...                               │
│  ████████░░░░░░░░░░░░ 2 of 3 complete                │
│                                                      │
│  ✅ 1920 - Jesse D Iams (linked)                    │
│  ✅ 1930 - Jesse D Iams (linked)                    │
│  ⏳ 1950 - Jesse D Iams (downloading...)            │
└──────────────────────────────────────────────────────┘
```

**7. Review Results**

```
┌──────────────────────────────────────────────────────┐
│  Download Complete                                   │
│  ✅ 3 images successfully downloaded and linked      │
│  ⚠️  0 failed                                        │
└──────────────────────────────────────────────────────┘
```

**✅ Done! All selected images are downloaded and linked.**

---

## Where Images Are Stored

### Directory Structure

RMCitecraft organizes images by census year:

```
~/Genealogy/RootsMagic/Files/
└── Records - Census/
    ├── 1790 Federal/
    ├── 1800 Federal/
    ├── ...
    ├── 1920 Federal/
    │   └── 1920, Pennsylvania, Greene - Iams, George B.jpg
    ├── 1930 Federal/
    │   └── 1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg
    ├── 1940 Federal/
    │   └── 1940, Texas, Milam - Iiams, Frank W..jpg
    └── 1950 Federal/
```

### Filename Format

```
YYYY, State, County - Surname, GivenName.ext
```

**Examples**:
- `1930, Oklahoma, Tulsa - Iams, Jesse Dorsey.jpg`
- `1940, Texas, Milam - Iiams, Frank W..jpg`
- `1920, Pennsylvania, Greene - Iams, George B.jpg`

**Why this format?**
- **Sortable** by year automatically
- **Searchable** by name or location
- **Consistent** across all census records
- **Compatible** with RootsMagic's media management

---

## Viewing Images in RMCitecraft

### During Citation Processing

Images appear automatically at **275% zoom** in the citation processing dialog:

```
┌─────────────────────────────────────────────────────┐
│  Left: Citation Fields    │  Right: Census Image    │
│  ┌──────────────────────┐ │ ┌──────────────────────┐│
│  │ Name: [____________] │ │ │                      ││
│  │ ED: [_____________]  │ │ │  [Census Image       ││
│  │ Sheet: [__________]  │ │ │   at 275% zoom]      ││
│  │                      │ │ │                      ││
│  │ Fill missing fields  │ │ │  Scroll to view      ││
│  │ while viewing image  │ │ │  household details   ││
│  └──────────────────────┘ │ └──────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Zoom Controls**:
- **[+]** / **[-]** buttons
- Preset levels: **100%**, **150%**, **200%**, **275%**
- Mouse wheel (if enabled)

**Pan Controls**:
- **Arrow buttons** (up, down, left, right)
- **Center** button (return to top-left)
- **Drag** image with mouse

**Current Position Display**:
```
Zoom: 275% | X=450px, Y=120px
```
Shows exactly where you are in the image (useful for noting default positions).

### In RootsMagic

Images are linked to:
1. **Census Event** (appears in person's timeline)
2. **Citation** (appears in citation details)

To view in RootsMagic:
- Open person → Events → Census event → Click image icon
- Open citation → Sources → Click image icon

---

## Troubleshooting

### Image Not Downloading

**Problem**: Status shows "⏳ Downloading..." for more than 2 minutes

**Solutions**:
1. **Check browser extension**: Make sure it's installed and enabled
2. **Check FamilySearch login**: Extension needs you to be logged into FamilySearch
3. **Check network**: Ensure internet connection is working
4. **Retry**: Click "Download Image" button again

### Image Download Failed

**Problem**: Status shows "⚠️ Failed"

**Common Causes**:
- FamilySearch page requires login
- Image not available (restricted or removed)
- Network timeout
- Browser blocked download

**Solutions**:
1. **Click [Retry]**: Try downloading again
2. **Manual download**: Click "View FamilySearch Page" → right-click image → "Save Image As..."
3. **Drag and drop**: Download manually, then drag file into RMCitecraft

### Wrong Image Downloaded

**Problem**: Image doesn't match the citation

**Why it happens**:
- Multiple FamilySearch tabs open
- Downloaded wrong person's image

**Solution**:
1. Delete wrong image from RootsMagic (unlink from citation)
2. Close all FamilySearch tabs
3. Open correct FamilySearch page
4. Download again

### Image Not Appearing in Citation Dialog

**Problem**: Processed citation but image doesn't show

**Check**:
1. **Image Manager tab**: Verify image was processed successfully
2. **RootsMagic**: Check if image is linked to the person's census event
3. **File system**: Navigate to census folder, verify file exists

**Solution**:
- Re-process the pending citation
- Or manually link image in RootsMagic

### Duplicate Images

**Problem**: Same census image downloaded multiple times

**RMCitecraft handles this**:
- Detects duplicates automatically
- Links existing image to new citation
- Deletes duplicate download
- Shows message: "Using existing image for this person/year"

---

## Best Practices

### 1. Process Citations in Batches

✅ Extract 10-20 citations from FamilySearch
✅ Let images download in background
✅ Process all citations in one session
✅ Images will be ready as you work through citations

### 2. Use Filters in Image Manager

✅ Download images by census year (e.g., all 1930 first)
✅ Download images by family (e.g., all "Iams" family)
✅ Prioritize recent additions (sort by "Date Added")

### 3. Keep FamilySearch Tab Open

✅ Leave one FamilySearch tab open while working
✅ Extension can download from background tabs
✅ Faster downloads (no new page loads)

### 4. Verify Image Quality

✅ Check image is readable before saving
✅ Zoom to 275% to verify text is legible
✅ If image is poor quality, download higher resolution from FamilySearch

### 5. Regular Backups

✅ Back up your RootsMagic database regularly
✅ Census images folder: `~/Genealogy/RootsMagic/Files/Records - Census/`
✅ Consider cloud backup for images (large files)

---

## FAQ

### Q: Can I change the zoom level default?

**A**: Currently defaults to 275%. In future versions, you'll be able to set custom zoom and position preferences per census year.

### Q: What if I don't have the browser extension?

**A**: You can still use RMCitecraft! Manual workflow:
1. Download census image from FamilySearch (right-click → Save Image As...)
2. Drag image onto citation in RMCitecraft
3. System will auto-rename and organize

### Q: Can I download images for non-census records?

**A**: Currently supports census only. Future versions will support:
- Birth/death certificates
- Marriage records
- Military records
- Other genealogical documents

### Q: Where are original filenames stored?

**A**: Original filenames are not preserved. Images are renamed to standardized format. If you need to track originals, note them in the citation's "RefNumber" field.

### Q: Can I organize images differently?

**A**: The directory structure follows RootsMagic conventions and Evidence Explained standards. Custom organization will be supported in future versions.

### Q: What image formats are supported?

**A**: RMCitecraft supports:
- **JPG/JPEG** (most common from FamilySearch)
- **PNG** (screenshots)
- **PDF** (document scans)
- **TIFF** (high-resolution archives)

### Q: How much disk space do census images use?

**A**: Average census image: **300-500 KB**
- 100 census images: ~40 MB
- 1,000 census images: ~400 MB
- 10,000 census images: ~4 GB

Plan storage accordingly for large family trees.

---

## Keyboard Shortcuts (Future)

*Coming in future versions*:

| Action | Shortcut |
|--------|----------|
| Download image | `Ctrl/Cmd + D` |
| View image | `Ctrl/Cmd + I` |
| Zoom in | `Ctrl/Cmd + +` |
| Zoom out | `Ctrl/Cmd + -` |
| Reset zoom | `Ctrl/Cmd + 0` |
| Pan left | `←` |
| Pan right | `→` |
| Pan up | `↑` |
| Pan down | `↓` |

---

## Getting Help

### In-App Help

- **Hover tooltips**: Hover over any button for explanation
- **Status messages**: Watch status bar for progress updates
- **Error messages**: Click "Details" for troubleshooting steps

### Documentation

- **Full Architecture**: `docs/architecture/IMAGE-MANAGEMENT-ARCHITECTURE.md`
- **Developer Guide**: `docs/project/IMAGE-IMPLEMENTATION-PLAN.md`
- **General Help**: Press `F1` in RMCitecraft

### Support

- **GitHub Issues**: https://github.com/yourusername/RMCitecraft/issues
- **Discussions**: https://github.com/yourusername/RMCitecraft/discussions
- **Email**: support@rmcitecraft.com (coming soon)

---

## Document Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-29 | Initial user guide |

