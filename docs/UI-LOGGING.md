# UI Logging Guide

## IMPORTANT: Use Only error_log_service

RMCitecraft has **ONE** logging service for UI messages:

- **`error_log_service`** - Displays in the Error & Warning Log (bug button in UI)

## Do NOT Use

- ~~`message_log`~~ - This is a legacy service and should NOT be used

## How to Log UI Messages

### Option 1: Direct (Current Method)

```python
from rmcitecraft.services.error_log import get_error_log_service

error_log = get_error_log_service()

# Log error
error_log.add_error("Error message", context="Find a Grave Batch")

# Log warning
error_log.add_warning("Warning message", context="Find a Grave Batch")

# Log info
error_log.add_info("Info message", context="Find a Grave Batch")
```

### Option 2: Simplified Helper (Recommended for Future)

```python
from rmcitecraft.services.ui_logging import log_error, log_warning, log_info, log_success

# Log error (shows in panel + notification)
log_error("Error message", context="Find a Grave Batch")

# Log warning (shows in panel + notification)
log_warning("Warning message", context="Find a Grave Batch")

# Log info (shows in panel only, no notification by default)
log_info("Info message", context="Find a Grave Batch")

# Log success (shows in panel + positive notification)
log_success("Success message", context="Find a Grave Batch")

# Disable notification for any message
log_warning("Warning message", context="Find a Grave Batch", notify=False)
```

## Rule: If it flashes on screen, it must be in the error log

Any `ui.notify()` call should have a corresponding error_log entry:

```python
# CORRECT
error_msg = f"Database write failed for {item.full_name}: {error}"
ui.notify(error_msg, type="negative")
self.error_log.add_error(error_msg, context="Find a Grave Batch")

# OR using helper (recommended)
log_error(f"Database write failed for {item.full_name}: {error}", context="Find a Grave Batch")

# WRONG - notification without log entry
ui.notify("Error occurred", type="negative")  # User can't review later!
```

## Context Names

Use consistent context names across the app:
- "Find a Grave Batch"
- "Citation Manager"
- "Image Processing"
- etc.

## Migration Plan

1. **Immediate**: Use `error_log_service` directly (current method)
2. **Future**: Migrate to `ui_logging` helpers for consistency
3. **Eventually**: Deprecate and remove `message_log` service
