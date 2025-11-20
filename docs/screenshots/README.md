# RMCitecraft Screenshots

This directory contains screenshots for documentation purposes.

## Capturing User Journey Screenshots

To capture screenshots for the User Journey Map documentation:

1. **Start RMCitecraft application**:
   ```bash
   uv run python -m rmcitecraft start
   ```

2. **Run the screenshot capture script**:
   ```bash
   uv run python scripts/capture_ui_screenshots.py
   ```

3. **Screenshots will be saved to**: `docs/screenshots/user_journey/`

## Screenshot List

### Main User Journey Screenshots

- `01_home_page.png` - Home page with navigation and system status
- `02_census_batch_empty.png` - Census Batch Processing tab (empty state)
- `03_census_batch_loaded.png` - Census Batch Processing with loaded queue
- `04_findagrave_empty.png` - Find a Grave Batch Processing tab (empty state)
- `05_citation_manager.png` - Citation Manager interface
- `06_dashboard.png` - Dashboard with monitoring components

### Less-Used Interfaces (Manual Capture)

These screenshots require manual capture during specific workflows:

- `07_place_validation_high_confidence.png` - Place Approval Dialog (high confidence gazetteer validation)
- `08_place_validation_low_confidence.png` - Place Approval Dialog (low confidence, requires user review)

**To capture Place Validation screenshots**:
1. Load a Find a Grave batch with memorials containing new cemetery locations
2. Click "Process" button
3. When Place Approval Dialog appears, take screenshot
4. Test both high-confidence and low-confidence scenarios

## Screenshot Guidelines

- **Resolution**: 1920x1080 (standard desktop)
- **Format**: PNG
- **File size**: Aim for < 500 KB (use compression if needed)
- **Content**: Capture full window, no cropping
- **Test data**: Use sample data from `data/Iiams.rmtree`

## Updating Screenshots

When UI changes require screenshot updates:

1. Update the relevant screenshots using the capture script or manual capture
2. Verify all screenshot references in documentation still work
3. Commit updated screenshots with descriptive commit message

## Notes

- Screenshots show the application running on macOS
- UI may differ slightly on other platforms (though RMCitecraft is macOS-only)
- Screenshots use sample genealogy data from the Iiams family tree
- Sensitive personal information has been replaced with sample data where applicable
