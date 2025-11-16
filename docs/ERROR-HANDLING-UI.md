# Error Handling & Display System

## Overview

RMCitecraft now has a persistent error logging and display system that makes errors visible, copyable, and easier to debug.

## Features

### 1. Persistent Error Log
- **Floating Bug Button**: Bottom-right corner of the screen
- **Badge Counter**: Shows number of errors (red) or warnings (orange)
- **Click to Expand**: Opens detailed error panel

### 2. Error Panel
- **Persistent Display**: Errors don't disappear until manually dismissed
- **Detailed Information**:
  - Timestamp
  - Context (which part of the app had the error)
  - Error message
  - Expandable details (stack traces, etc.)
- **Copy Functionality**:
  - Copy individual errors
  - Copy all errors at once
- **Searchable History**: Up to 100 most recent errors/warnings

### 3. Notification + Logging
- **Toast Notifications**: Still appear for immediate feedback
- **Automatic Logging**: All errors are automatically logged to the panel
- **Configurable Timeout**:
  - Critical errors: Never dismiss (timeout=0)
  - Normal errors: 10 seconds
  - Warnings: 5 seconds

## How It Works

### For Users

**When an error occurs:**
1. You'll see a toast notification at the top of the screen
2. The bug button (🐛) appears in the bottom-right with a red badge
3. Click the bug button to see full error details
4. Click "Copy" to copy the error message for reporting
5. Click "Clear" to dismiss all errors

**Error Panel Features:**
- **Expandable Details**: Click "Details" to see full stack trace
- **Context Labels**: Know which feature had the issue
- **Timestamp**: See when each error occurred
- **Copy Individual**: Copy one error at a time
- **Copy All**: Export entire error log
- **Persistent**: Errors stay until you clear them

### For Developers

**Using the Error Service:**

```python
from rmcitecraft.ui.components.error_panel import (
    show_error_notification,
    show_warning_notification
)

# Show an error with details
try:
    # Some operation
    pass
except Exception as e:
    show_error_notification(
        message="Failed to save citation",
        details=str(e),  # Full error message
        context="Citation Manager",  # Where it happened
        timeout=0  # Never dismiss (0 = permanent)
    )

# Show a warning
show_warning_notification(
    message="Missing enumeration district",
    details="Citation may be incomplete",
    context="Citation Parser",
    timeout=5  # Dismiss after 5 seconds
)
```

**Direct Access to Error Log:**

```python
from rmcitecraft.services.error_log import get_error_log_service

error_service = get_error_log_service()

# Add error
error_service.add_error("Something went wrong", details="...", context="...")

# Get errors
errors = error_service.get_entries(level="error", limit=10)

# Export as text
text = error_service.export_text()

# Clear all
error_service.clear()

# Get counts
error_count = error_service.get_error_count()
warning_count = error_service.get_warning_count()
```

## Error Levels

### Error (Red)
- **When**: Critical failures that prevent operations
- **Examples**:
  - Failed to save to database
  - LLM parsing failed
  - File system errors
- **Display**: Red icon, red badge on bug button
- **Default Timeout**: 0 (never dismiss)

### Warning (Orange)
- **When**: Non-critical issues or missing data
- **Examples**:
  - Missing optional fields
  - Deprecated features used
  - Configuration issues
- **Display**: Orange icon, orange badge
- **Default Timeout**: 5 seconds

### Info (Blue)
- **When**: Informational messages for debugging
- **Examples**:
  - Processing started
  - Configuration loaded
- **Display**: Blue icon
- **Default Timeout**: 5 seconds

## Implementation Details

### Error Log Service
**File**: `src/rmcitecraft/services/error_log.py`
- Singleton service
- In-memory storage (up to 100 entries)
- Callback system for UI updates
- Export to text format

### Error Panel Component
**File**: `src/rmcitecraft/ui/components/error_panel.py`
- Floating bug button (bottom-right)
- Expandable panel with scroll
- Copy functionality
- NiceGUI-based UI

### Integration
**File**: `src/rmcitecraft/main.py`
- Error panel added to main UI (line 154)
- Available on all tabs
- Persistent across navigation

### Updated Components
**File**: `src/rmcitecraft/ui/tabs/citation_manager.py`
- Critical error handlers updated to use new system
- Errors now include full context and details
- Stack traces captured for debugging

## Testing

### Test Error Display
1. **Restart RMCitecraft**:
   ```bash
   rmcitecraft restart
   ```

2. **Trigger an error** (e.g., try to save a citation with invalid data)

3. **Check the bug button** appears in bottom-right corner

4. **Click the bug button** to see the error panel

5. **Click "Copy"** on an error - should copy to clipboard

6. **Click "Copy All"** - should export all errors

7. **Click "Clear"** - errors should be removed

### Test Persistence
1. Trigger an error
2. Navigate to different tabs
3. Error panel button should still show badge
4. Errors should remain until manually cleared

## Benefits

### For Users
- ✅ **Never lose errors**: No more "it disappeared before I could read it"
- ✅ **Easy reporting**: Copy/paste errors to share with support
- ✅ **Context awareness**: Know exactly where the problem occurred
- ✅ **History**: Review multiple errors at once

### For Developers
- ✅ **Centralized logging**: All errors in one place
- ✅ **Debugging**: Full stack traces available
- ✅ **User feedback**: Users can easily share error details
- ✅ **Patterns**: See multiple errors to identify patterns

## Future Enhancements

- [ ] Save error log to file
- [ ] Send error reports to developers
- [ ] Filter errors by context/level
- [ ] Search errors by keyword
- [ ] Export as JSON/CSV
- [ ] Error statistics dashboard
