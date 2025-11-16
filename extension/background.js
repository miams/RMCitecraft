/**
 * RMCitecraft FamilySearch Assistant - Background Service Worker
 *
 * Manages communication between content script and RMCitecraft application.
 * Polls for commands from RMCitecraft and coordinates data extraction.
 */

// Configuration
const RMCITECRAFT_PORT = 8080;
const RMCITECRAFT_BASE_URL = `http://localhost:${RMCITECRAFT_PORT}`;
const RMCITECRAFT_WS_URL = `ws://localhost:${RMCITECRAFT_PORT}/api/ws/extension`;
const POLL_INTERVAL_MS = 2000; // Poll every 2 seconds
const HEALTH_CHECK_INTERVAL_MS = 10000; // Check health every 10 seconds
const WS_RECONNECT_INTERVAL_MS = 5000; // Reconnect WebSocket every 5 seconds if disconnected

// State
let isConnected = false;
let isPolling = false;
let pollIntervalId = null;
let healthCheckIntervalId = null;
let commandCheckIntervalId = null;
let websocket = null;
let useWebSocket = true; // Prefer WebSocket over polling
let wsReconnectTimeout = null;

/**
 * Connect to RMCitecraft via WebSocket
 */
function connectWebSocket() {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    return; // Already connected
  }

  try {
    console.log('[RMCitecraft] Connecting to WebSocket...');
    websocket = new WebSocket(RMCITECRAFT_WS_URL);

    websocket.onopen = () => {
      console.log('[RMCitecraft] WebSocket connected');
      isConnected = true;
      useWebSocket = true;
      stopPolling(); // Stop polling if it was running
      updateBadge('connected');

      // Clear reconnect timeout if any
      if (wsReconnectTimeout) {
        clearTimeout(wsReconnectTimeout);
        wsReconnectTimeout = null;
      }

      // Start periodic command checking via WebSocket
      startCommandChecking();
    };

    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('[RMCitecraft] WebSocket message parse error:', error);
      }
    };

    websocket.onerror = (error) => {
      console.error('[RMCitecraft] WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('[RMCitecraft] WebSocket closed');
      websocket = null;
      stopCommandChecking(); // Stop command checking

      // Try to reconnect after interval
      if (isConnected) {
        isConnected = false;
        updateBadge('disconnected');

        // Fall back to polling
        console.log('[RMCitecraft] Falling back to polling mode');
        useWebSocket = false;
        startPolling();
      }

      // Schedule reconnect attempt
      wsReconnectTimeout = setTimeout(() => {
        if (isConnected) {
          connectWebSocket();
        }
      }, WS_RECONNECT_INTERVAL_MS);
    };

  } catch (error) {
    console.error('[RMCitecraft] WebSocket connection error:', error);
    useWebSocket = false;
  }
}

/**
 * Handle WebSocket message from RMCitecraft
 */
async function handleWebSocketMessage(message) {
  console.log('[RMCitecraft] WebSocket received:', message.type);

  switch (message.type) {
    case 'commands':
      // Received pending commands
      if (message.data && message.data.length > 0) {
        for (const command of message.data) {
          await handleCommand(command);
        }
      }
      break;

    case 'ping':
      // Respond to ping
      sendWebSocketMessage({ type: 'pong' });
      break;

    case 'ack':
      // Command acknowledged
      console.log('[RMCitecraft] Command acknowledged:', message.command_id);
      break;

    case 'citation_imported':
      // Citation was successfully imported
      console.log('[RMCitecraft] Citation imported:', message.citation_id);
      break;

    default:
      console.warn('[RMCitecraft] Unknown WebSocket message type:', message.type);
  }
}

/**
 * Send message via WebSocket
 */
function sendWebSocketMessage(message) {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(JSON.stringify(message));
    return true;
  }
  return false;
}

/**
 * Check if RMCitecraft is running
 */
async function checkRMCitecraftHealth() {
  try {
    const response = await fetch(`${RMCITECRAFT_BASE_URL}/api/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      if (!isConnected) {
        console.log('[RMCitecraft] Connected to RMCitecraft');
        isConnected = true;

        // Try WebSocket first, fall back to polling
        if (useWebSocket) {
          connectWebSocket();
        } else {
          startPolling();
        }

        updateBadge('connected');
      }
      return true;
    }
  } catch (error) {
    if (isConnected) {
      console.log('[RMCitecraft] Lost connection to RMCitecraft');
      isConnected = false;
      stopPolling();

      if (websocket) {
        websocket.close();
        websocket = null;
      }

      updateBadge('disconnected');
    }
    return false;
  }
}

/**
 * Start polling for commands from RMCitecraft
 */
function startPolling() {
  if (isPolling) return;

  console.log('[RMCitecraft] Starting command polling');
  isPolling = true;

  pollIntervalId = setInterval(async () => {
    try {
      const response = await fetch(`${RMCITECRAFT_BASE_URL}/api/extension/commands`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const commands = await response.json();
        if (commands && commands.length > 0) {
          for (const command of commands) {
            await handleCommand(command);
          }
        }
      }
    } catch (error) {
      console.error('[RMCitecraft] Polling error:', error);
    }
  }, POLL_INTERVAL_MS);
}

/**
 * Stop polling for commands
 */
function stopPolling() {
  if (!isPolling) return;

  console.log('[RMCitecraft] Stopping command polling');
  isPolling = false;

  if (pollIntervalId) {
    clearInterval(pollIntervalId);
    pollIntervalId = null;
  }
}

/**
 * Start periodic command checking via WebSocket
 */
function startCommandChecking() {
  if (commandCheckIntervalId) return; // Already running

  console.log('[RMCitecraft] Starting periodic command checking via WebSocket');

  commandCheckIntervalId = setInterval(() => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      sendWebSocketMessage({ type: 'check_commands' });
    }
  }, POLL_INTERVAL_MS); // Check every 2 seconds
}

/**
 * Stop command checking
 */
function stopCommandChecking() {
  if (!commandCheckIntervalId) return;

  console.log('[RMCitecraft] Stopping command checking');

  if (commandCheckIntervalId) {
    clearInterval(commandCheckIntervalId);
    commandCheckIntervalId = null;
  }
}

/**
 * Handle command from RMCitecraft
 */
async function handleCommand(command) {
  console.log('[RMCitecraft] Received command:', command);

  try {
    switch (command.type) {
      case 'download_image':
        await executeDownloadImage(command);
        break;
      case 'ping':
        await respondToCommand(command.id, { status: 'pong' });
        break;
      case 'shutdown':
        stopPolling();
        isConnected = false;
        updateBadge('disconnected');
        await respondToCommand(command.id, { status: 'shutdown' });
        break;
      default:
        console.warn('[RMCitecraft] Unknown command type:', command.type);
    }
  } catch (error) {
    console.error('[RMCitecraft] Command execution error:', error);
    await respondToCommand(command.id, { status: 'error', error: error.message });
  }
}

/**
 * Execute download_image command
 */
async function executeDownloadImage(command) {
  // Find ANY FamilySearch tab (not just active one)
  // User may have switched to RMCitecraft window, making FS tab inactive
  const familySearchTabs = await chrome.tabs.query({ url: '*://www.familysearch.org/*' });

  if (familySearchTabs.length === 0) {
    await respondToCommand(command.id, {
      status: 'error',
      error: 'No FamilySearch tabs found. Please keep the FamilySearch page open.'
    });
    return;
  }

  // Prefer the most recently accessed FamilySearch tab
  const tab = familySearchTabs.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0];

  console.log('[RMCitecraft] Found FamilySearch tab:', tab.id, tab.url);

  // Send message to content script
  chrome.tabs.sendMessage(tab.id, {
    type: 'download_image',
    commandId: command.id,
    data: command.data
  }, async (response) => {
    if (chrome.runtime.lastError) {
      console.error('[RMCitecraft] Error sending message to content script:', chrome.runtime.lastError);
      await respondToCommand(command.id, {
        status: 'error',
        error: `Failed to communicate with FamilySearch tab: ${chrome.runtime.lastError.message}`
      });
    } else {
      await respondToCommand(command.id, response);
    }
  });
}

/**
 * Send command response back to RMCitecraft
 */
async function respondToCommand(commandId, response) {
  // Try WebSocket first
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    sendWebSocketMessage({
      type: 'command_response',
      command_id: commandId,
      status: response.status || 'success',
      data: response
    });
    return;
  }

  // Fall back to HTTP
  try {
    await fetch(`${RMCITECRAFT_BASE_URL}/api/extension/commands/${commandId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(response)
    });
  } catch (error) {
    console.error('[RMCitecraft] Error responding to command:', error);
  }
}

/**
 * Update extension badge
 */
function updateBadge(status) {
  if (status === 'connected') {
    chrome.action.setBadgeText({ text: '' });
    chrome.action.setBadgeBackgroundColor({ color: '#22c55e' }); // green
  } else if (status === 'disconnected') {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' }); // red
  }
}

/**
 * Handle messages from content script or popup
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'send_citation_data') {
    // Forward citation data to RMCitecraft
    sendCitationData(message.data)
      .then(response => sendResponse({ status: 'success', data: response }))
      .catch(error => sendResponse({ status: 'error', error: error.message }));
    return true; // Will respond asynchronously
  } else if (message.type === 'get_connection_status') {
    sendResponse({ connected: isConnected });
  } else if (message.type === 'check_health') {
    checkRMCitecraftHealth()
      .then(connected => sendResponse({ connected }))
      .catch(() => sendResponse({ connected: false }));
    return true; // Will respond asynchronously
  } else if (message.type === 'PORT_CHANGED') {
    // Port change notification from popup (informational only)
    console.log('[RMCitecraft] Port changed to:', message.port);
    sendResponse({ status: 'acknowledged' });
  } else if (message.type === 'AUTO_ACTIVATE_CHANGED') {
    // Auto-activate setting change from popup (informational only)
    console.log('[RMCitecraft] Auto-activate changed to:', message.enabled);
    sendResponse({ status: 'acknowledged' });
  } else if (message.type === 'DOWNLOAD_FILE') {
    // Download file using chrome.downloads API
    chrome.downloads.download({
      url: message.url,
      filename: message.filename || 'download.jpg',
      saveAs: false // Auto-save to default downloads folder
    }, (downloadId) => {
      if (chrome.runtime.lastError) {
        console.error('[RMCitecraft] Download error:', chrome.runtime.lastError);
        sendResponse({ success: false, error: chrome.runtime.lastError.message });
      } else {
        console.log('[RMCitecraft] Download started:', downloadId);
        sendResponse({ success: true, downloadId });
      }
    });
    return true; // Will respond asynchronously
  }
});

/**
 * Send citation data to RMCitecraft
 */
async function sendCitationData(citationData) {
  // Try WebSocket first
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    return new Promise((resolve, reject) => {
      // Send via WebSocket
      sendWebSocketMessage({
        type: 'citation_import',
        data: citationData
      });

      // Set timeout for response
      const timeout = setTimeout(() => {
        reject(new Error('Citation import timeout'));
      }, 10000);

      // Listen for response (handled in handleWebSocketMessage)
      // For now, resolve immediately as WebSocket is fire-and-forget
      clearTimeout(timeout);
      resolve({ status: 'sent_via_websocket' });
    });
  }

  // Fall back to HTTP
  const response = await fetch(`${RMCITECRAFT_BASE_URL}/api/citation/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(citationData)
  });

  if (!response.ok) {
    throw new Error(`Failed to send citation data: ${response.statusText}`);
  }

  return await response.json();
}

// Start health check on extension load
checkRMCitecraftHealth();
healthCheckIntervalId = setInterval(checkRMCitecraftHealth, HEALTH_CHECK_INTERVAL_MS);

console.log('[RMCitecraft] Background service worker initialized');
