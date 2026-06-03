---
priority: medium
topics: [cli, usage, daemon]
status: active
---

# RMCitecraft CLI Usage Guide

**Version**: 1.0
**Date**: 2026-02-06

## Overview

RMCitecraft provides a command-line interface (CLI) for starting, stopping, and managing the application. The CLI supports both foreground and daemon (background) modes.

## Installation

The CLI is available after installing RMCitecraft:

```bash
# Install in development mode
uv pip install -e .

# Or run directly with uv
uv run python -m rmcitecraft [command]
```

## Commands

### Start (Foreground)

Start RMCitecraft in the foreground (interactive mode):

```bash
# Using uv
uv run python -m rmcitecraft start

# If installed
rmcitecraft start
```

**Behavior**:
- Application runs in the current terminal
- Press `Ctrl+C` to stop
- Output displayed directly to terminal
- PID file created at `~/.rmcitecraft/rmcitecraft.pid`

**When to use**: Development, debugging, or when you want to see real-time output.

### Start (Daemon Mode)

Start RMCitecraft as a background daemon:

```bash
# Using uv
uv run python -m rmcitecraft start -d

# If installed
rmcitecraft start -d
```

**Behavior**:
- Application runs in the background
- Process detaches from terminal
- Logs written to files (see below)
- PID file created at `~/.rmcitecraft/rmcitecraft.pid`

**When to use**: Production, long-running sessions, or when you want to close the terminal.

**⚠️ Daemon Mode Limitations**:
- NiceGUI native mode may not work properly in daemon mode (requires display)
- Browser mode opens in the system default browser
- Best suited for server environments or when running browser mode

### Stop

Stop a running daemon:

```bash
# Using uv
uv run python -m rmcitecraft stop

# If installed
rmcitecraft stop
```

**Behavior**:
- Sends `SIGTERM` for graceful shutdown
- Waits up to 10 seconds for process to stop
- If process doesn't stop, sends `SIGKILL` (force stop)
- Removes PID file after successful stop

**Example Output**:
```
⏹️  Stopping RMCitecraft (PID: 12345)...
✅ RMCitecraft stopped
```

### Status

Check if RMCitecraft is running:

```bash
# Using uv
uv run python -m rmcitecraft status

# If installed
rmcitecraft status
```

**Behavior**:
- Checks PID file for running process
- Verifies process is actually running
- Shows log file locations
- Exit code 0 if running, 1 if not running

**Example Output (Running)**:
```
✅ RMCitecraft is running (PID: 12345)

📋 Log files:
   Stdout: /Users/username/.rmcitecraft/stdout.log
   Stderr: /Users/username/.rmcitecraft/stderr.log
   Application: /Users/username/.rmcitecraft/rmcitecraft.log
```

**Example Output (Not Running)**:
```
⚫ RMCitecraft is not running
```

## Log Files

When running in daemon mode, logs are written to:

| File | Content | Location |
|------|---------|----------|
| `stdout.log` | Standard output (print statements) | `~/.rmcitecraft/stdout.log` |
| `stderr.log` | Standard error (error messages) | `~/.rmcitecraft/stderr.log` |
| `rmcitecraft.log` | Application log (loguru) | `~/.rmcitecraft/rmcitecraft.log` |
| `rmcitecraft.pid` | Process ID file | `~/.rmcitecraft/rmcitecraft.pid` |

### Viewing Logs

```bash
# View last 20 lines of application log
tail -20 ~/.rmcitecraft/rmcitecraft.log

# Follow application log in real-time
tail -f ~/.rmcitecraft/rmcitecraft.log

# View stdout
cat ~/.rmcitecraft/stdout.log

# View errors
cat ~/.rmcitecraft/stderr.log
```

## Process Management

### Checking if Running

```bash
# Option 1: Use status command
rmcitecraft status

# Option 2: Check PID file manually
cat ~/.rmcitecraft/rmcitecraft.pid

# Option 3: Check process list
ps aux | grep rmcitecraft
```

### Manually Stopping (Emergency)

If the `stop` command doesn't work:

```bash
# Get PID
PID=$(cat ~/.rmcitecraft/rmcitecraft.pid)

# Send SIGTERM
kill $PID

# If that doesn't work, force kill
kill -9 $PID

# Clean up PID file
rm ~/.rmcitecraft/rmcitecraft.pid
```

## Common Use Cases

### Development Workflow

```bash
# Start in foreground to see output
rmcitecraft start

# Make changes to code...
# Press Ctrl+C to stop

# Restart
rmcitecraft start
```

### Production Deployment

```bash
# Start as daemon
rmcitecraft start -d

# Check it's running
rmcitecraft status

# View logs
tail -f ~/.rmcitecraft/rmcitecraft.log

# Stop when done
rmcitecraft stop
```

### Automated Startup (macOS)

Create a LaunchAgent plist at `~/Library/LaunchAgents/com.rmcitecraft.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rmcitecraft</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/rmcitecraft</string>
        <string>start</string>
        <string>-d</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/username/.rmcitecraft/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/username/.rmcitecraft/launchd.error.log</string>
</dict>
</plist>
```

Load the agent:
```bash
launchctl load ~/Library/LaunchAgents/com.rmcitecraft.plist
```

## Troubleshooting

### "Already Running" Error

```
❌ RMCitecraft is already running (PID: 12345)
   Use 'rmcitecraft stop' to stop it first
```

**Solution**: Stop the existing process first:
```bash
rmcitecraft stop
rmcitecraft start
```

### Stale PID File

```
❌ RMCitecraft process (PID: 12345) is not running
   Cleaning up stale PID file...
```

**Cause**: Process was killed without cleaning up PID file.

**Solution**: Automatic - the CLI detects and removes stale PID files.

### Can't Stop Process

If `rmcitecraft stop` fails:

```bash
# Find the process
ps aux | grep rmcitecraft

# Force kill (use PID from above)
kill -9 [PID]

# Clean up PID file
rm ~/.rmcitecraft/rmcitecraft.pid
```

### Permission Errors

If you get permission errors:

```bash
# Check ownership of .rmcitecraft directory
ls -la ~/.rmcitecraft/

# Fix permissions
chmod -R u+rw ~/.rmcitecraft/
```

## Advanced Usage

### Environment Variables

Control application behavior with environment variables:

```bash
# Run in native mode (desktop app)
export RMCITECRAFT_NATIVE=true
rmcitecraft start

# Set log level
export LOG_LEVEL=DEBUG
rmcitecraft start
```

### Custom Port

The default port is 8080. To use a different port, modify `main.py`:

```python
ui.run(
    title="RMCitecraft",
    native=native_mode,
    port=8888,  # Change port here
)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error or not running |

**Example in Scripts**:
```bash
#!/bin/bash

# Check if running
if rmcitecraft status > /dev/null 2>&1; then
    echo "RMCitecraft is running"
else
    echo "RMCitecraft is not running"
    rmcitecraft start -d
fi
```

## See Also

- [CLAUDE.md](../../CLAUDE.md) - Development guide
- [Application Configuration](../reference/CONFIGURATION.md) - Settings reference
- [Logging Configuration](../reference/LOGGING.md) - Log configuration
