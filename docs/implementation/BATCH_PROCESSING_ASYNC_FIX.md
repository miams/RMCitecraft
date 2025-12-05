---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Batch Processing - Async Context Fix

**Date**: November 6, 2025
**Issue**: RuntimeError when loading citations - UI context lost in async task

## Error

```
RuntimeError: The current slot cannot be determined because the slot stack for this task is empty.
This may happen if you try to create UI from a background task.
To fix this, enter the target slot explicitly using `with container_element:`.
```

**Location**: `_load_citations()` function calling `ui.notify()`

## Root Cause

**Problem**: Using `asyncio.create_task()` to call async function from button handler

```python
# BROKEN - Creates background task, loses UI context
ui.button(
    "Load",
    on_click=lambda: asyncio.create_task(self._load_citations(...))
)
```

When `asyncio.create_task()` creates a background task, it runs outside of NiceGUI's UI context. Any calls to `ui.notify()` or other UI elements fail because they can't determine which client/page to update.

## Solution

**Make `_load_citations()` synchronous** - it doesn't actually do any async work

```python
# FIXED - Synchronous function, maintains UI context
ui.button(
    "Load",
    on_click=lambda: self._load_citations(...)
)

# Changed from:
async def _load_citations(...) -> None:
    # ...

# To:
def _load_citations(...) -> None:
    # ... (no await calls, just synchronous database queries)
```

## Why This Works

1. **`_load_citations()` does no async I/O**:
   - Calls `find_census_citations()` - synchronous database query
   - Updates session state - synchronous
   - Refreshes UI panels - synchronous
   - No `await` calls anywhere in the function

2. **NiceGUI button handlers support both sync and async**:
   - Sync functions: Called directly, maintain UI context ✅
   - Async functions: NiceGUI handles them automatically ✅
   - Manual `asyncio.create_task()`: Loses context ❌

3. **Other async functions remain async**:
   - `_start_batch_processing()` - Has `await` calls, stays async
   - `_process_single_citation()` - Has `await` calls, stays async
   - Called directly from button handler, NiceGUI handles context

## Code Changes

**File**: `src/rmcitecraft/ui/tabs/batch_processing.py`

### Before (Broken)
```python
ui.button(
    "Load",
    icon="download",
    on_click=lambda: asyncio.create_task(self._load_citations(
        year_select.value,
        int(limit_input.value),
        int(offset_input.value),
        dialog,
    )),
).props("color=primary")

async def _load_citations(self, census_year: int, limit: int, offset: int, dialog: ui.dialog) -> None:
    ui.notify(f"Loading...")  # FAILS - no UI context
    # ...
```

### After (Fixed)
```python
ui.button(
    "Load",
    icon="download",
    on_click=lambda: self._load_citations(
        year_select.value,
        int(limit_input.value),
        int(offset_input.value),
        dialog,
    ),
).props("color=primary")

def _load_citations(self, census_year: int, limit: int, offset: int, dialog: ui.dialog) -> None:
    ui.notify(f"Loading...")  # WORKS - UI context maintained
    # ...
```

## Testing

```bash
$ uv run python -c "from rmcitecraft.ui.tabs.batch_processing import BatchProcessingTab; print('Import successful')"
Import successful
```

## Rule for NiceGUI Async

**When to use async in NiceGUI event handlers:**

✅ **Use async when**:
- Function has `await` calls (API calls, sleep, etc.)
- Assigned directly to `on_click` handler
- NiceGUI handles the context automatically

❌ **Don't use `asyncio.create_task()` when**:
- Function needs to update UI
- Function calls `ui.notify()`, `ui.update()`, etc.
- Use direct call or make function synchronous instead

✅ **Make function synchronous when**:
- No `await` calls in function body
- Only synchronous database queries
- Only synchronous state updates
- Simpler and maintains context automatically

---

**Status**: ✅ Fixed
**Impact**: Load Citations button now works correctly
**Test**: Click Load → Citations load → No runtime errors
