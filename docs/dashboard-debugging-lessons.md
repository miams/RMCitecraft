---
priority: reference
topics: [database, citation, batch, findagrave, testing]
---

# Dashboard Debugging Lessons Learned

## Problem Summary

The Find a Grave batch operations dashboard failed to display in the browser despite successful server-side rendering. The issue was **lambda functions in ECharts configuration dictionaries** causing silent JSON serialization failures.

## Timeline of Investigation

### Initial Symptoms
- Dashboard button clicked → No visible change in browser
- Server logs showed "Dashboard rendered successfully"
- No JavaScript errors in browser console
- Other tabs (Find a Grave, Citation Manager) worked fine

### First Fix Attempt: JSON Serialization of Callbacks
**Discovered**: `TypeError: Type is not JSON serializable: function`

**Problem**: Public callback attributes in dashboard components were being serialized by NiceGUI
```python
# WRONG - Public callbacks get serialized
self.on_status_click = on_status_click
self.state_repo = state_repo
```

**Solution**: Made all callbacks and repositories private
```python
# CORRECT - Private attributes avoid serialization
self._on_status_click = on_status_click
self._state_repo = state_repo
```

**Result**: Fixed callback serialization BUT dashboard still didn't display.

### Root Cause Discovery: Lambda Functions in ECharts

**Method**: Incremental component testing
1. ✅ Simplified dashboard (just labels) → **Worked**
2. ✅ Dashboard + header → **Worked**
3. ✅ Dashboard + header + Phase 1 components → **Worked**
4. ❌ Dashboard + Phase 2 charts (ECharts) → **FAILED**

**Problem Found**: `processing_timeline.py` had lambda functions inside ECharts configuration:

```python
# WRONG - Lambda in ECharts config causes silent serialization failure
chart_options = {
    'tooltip': {
        'trigger': 'axis',
        'formatter': lambda params: (  # ❌ Cannot be JSON serialized
            f"{person_names[params[0]['dataIndex']]}<br/>"
            f"PersonID: {person_ids[params[0]['dataIndex']]}<br/>"
            # ...
        )
    },
    'yAxis': {
        'axisLabel': {
            'formatter': lambda value: (  # ❌ Cannot be JSON serialized
                'Completed' if value == 1 else 'Failed' if value == 0 else 'Pending'
            )
        }
    }
}
```

## The Fix

### Solution 1: Pre-formatted Tooltip Data
Move tooltip content out of lambda and into series data:

```python
# CORRECT - Build tooltip strings during data preparation
series_data_with_tooltip = [
    {
        'value': status,
        'itemStyle': {'color': get_status_color(status)},
        'tooltip': {
            'formatter': (  # Static string, not lambda
                f"{person_names[i]}<br/>"
                f"PersonID: {person_ids[i]}<br/>"
                f"Time: {timestamps[i]}<br/>"
                f"Status: {'✓ Completed' if status == 1 else '✗ Failed'}"
            )
        }
    }
    for i, status in enumerate(statuses)
]

chart_options = {
    'tooltip': {'trigger': 'item'},  # Changed from 'axis' to 'item'
    'series': [{'data': series_data_with_tooltip}]
}
```

### Solution 2: Simple Template Strings
Use ECharts template strings instead of lambdas:

```python
# CORRECT - Use template string
'yAxis': {
    'axisLabel': {
        'formatter': '{value}',  # ECharts template string
    }
}
```

## Why This Was Hard to Debug

1. **Silent Failure**: No error messages in server logs or browser console
2. **Successful Server Rendering**: Server-side code executed without exceptions
3. **Serialization Happens After Rendering**: JSON serialization occurs when NiceGUI sends UI state to browser
4. **Lambda Location Matters**: Lambdas in event handlers (e.g., `on_click=lambda: ...`) work fine, but lambdas inside configuration dictionaries fail

## Prevention Rules

### ✅ DO: Safe Lambda Usage
```python
# Safe: Lambda passed directly to NiceGUI component
ui.button('Click', on_click=lambda: do_something())
ui.select([1, 2, 3], on_change=lambda e: handle_change(e.value))

# Safe: Private attributes for callbacks
self._on_row_click = on_row_click

# Safe: ECharts template strings
'formatter': '{value}%'
'formatter': '{b}: {c} ({d}%)'
```

### ❌ DON'T: Serialization Failures
```python
# WRONG: Lambda in configuration dictionary
chart_options = {
    'tooltip': {'formatter': lambda x: format_tooltip(x)}
}

# WRONG: Public callback attributes
self.on_status_click = on_status_click

# WRONG: Function reference in config
chart_options = {
    'axisLabel': {'formatter': self._format_label}
}
```

## Testing Strategy

### Incremental Component Testing
When debugging view-not-updating issues:

1. Start with minimal rendering (just labels)
2. Gradually add components one at a time
3. Test after each addition
4. When failure occurs, you've identified the problematic component

### Example Test Script
```python
from playwright.async_api import async_playwright

async def test_component():
    # Start app, navigate to page
    # Click dashboard button
    # Check if expected content appears
    body_text = await page.inner_text('body')
    assert '✅ Component X rendered!' in body_text
```

## Key Takeaways

1. **NiceGUI serializes component state to JSON** for browser updates
2. **Lambda functions cannot be JSON serialized**
3. **Make all callbacks and repositories private** (`_` prefix)
4. **Use ECharts template strings** instead of lambda formatters
5. **Pre-format data** during preparation, not in configuration
6. **Test incrementally** when debugging silent failures

## Files Modified

- `src/rmcitecraft/ui/tabs/dashboard.py` - Made callbacks private
- `src/rmcitecraft/ui/components/dashboard/processing_timeline.py` - Removed lambda formatters
- `src/rmcitecraft/ui/components/dashboard/status_distribution.py` - Made callbacks private
- `src/rmcitecraft/ui/components/dashboard/session_selector.py` - Made callbacks private
- `src/rmcitecraft/ui/components/dashboard/items_table.py` - Made callbacks private
- `src/rmcitecraft/ui/components/dashboard/item_detail.py` - Made config private

## Commit Message

```
fix(dashboard): remove lambda functions from ECharts configurations

Lambda functions in ECharts config dictionaries caused silent JSON
serialization failures, preventing dashboard from displaying in browser
despite successful server-side rendering.

Changes:
- Removed lambda formatters from processing_timeline.py tooltip/yAxis
- Pre-format tooltip data during series data preparation
- Use ECharts template strings for simple formatters
- Made all callbacks and repositories private to avoid serialization

Issue discovered through incremental component testing, which isolated
the problem to Phase 2 ECharts components.

Fixes: Silent dashboard rendering failure
```

## Date

2025-11-20

## Related Issues

- JSON serialization of functions in NiceGUI
- ECharts formatter configuration best practices
- Silent failures in server-client state synchronization
