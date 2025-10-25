/**
 * RMCitecraft FamilySearch Assistant - Background Service Worker
 *
 * Manages communication between content script and RMCitecraft application.
 * Polls for commands from RMCitecraft and coordinates data extraction.
 */

// Configuration
const RMCITECRAFT_PORT = 8080;
const RMCITECRAFT_BASE_URL = `http://localhost:${RMCITECRAFT_PORT}`;
const POLL_INTERVAL_MS = 2000; // Poll every 2 seconds
const HEALTH_CHECK_INTERVAL_MS = 10000; // Check health every 10 seconds

// State
let isConnected = false;
let isPoll

ing = false;
let pollIntervalId = null;
let healthCheckIntervalId = null;

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
        startPolling();
        updateBadge('connected');
      }
      return true;
    }
  } catch (error) {
    if (isConnected) {
      console.log('[RMCitecraft] Lost connection to RMCitecraft');
      isConnected = false;
      stopPolling();
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
  // Send message to content script on the active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (tab && tab.url && tab.url.includes('familysearch.org')) {
    chrome.tabs.sendMessage(tab.id, {
      type: 'download_image',
      commandId: command.id,
      data: command.data
    }, async (response) => {
      if (chrome.runtime.lastError) {
        console.error('[RMCitecraft] Error sending message to content script:', chrome.runtime.lastError);
        await respondToCommand(command.id, { status: 'error', error: chrome.runtime.lastError.message });
      } else {
        await respondToCommand(command.id, response);
      }
    });
  } else {
    await respondToCommand(command.id, {
      status: 'error',
      error: 'No active FamilySearch tab found'
    });
  }
}

/**
 * Send command response back to RMCitecraft
 */
async function respondToCommand(commandId, response) {
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
  }
});

/**
 * Send citation data to RMCitecraft
 */
async function sendCitationData(citationData) {
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
