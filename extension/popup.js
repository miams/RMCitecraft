/**
 * RMCitecraft Extension Popup
 *
 * Provides UI for:
 * - Connection status display
 * - Port configuration
 * - Manual send trigger
 * - Activity log
 * - Statistics
 */

// Constants
const DEFAULT_PORT = 8080;
const MAX_LOG_ENTRIES = 10;
const REFRESH_INTERVAL_MS = 2000;

// State
let rmcitecraftPort = DEFAULT_PORT;
let autoActivateEnabled = true;
let activityLog = [];
let stats = {
  sentToday: 0,
  commandsReceived: 0
};

// DOM Elements
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const portInput = document.getElementById('port-input');
const savePortBtn = document.getElementById('save-port-btn');
const autoActivateToggle = document.getElementById('auto-activate-toggle');
const sendNowBtn = document.getElementById('send-now-btn');
const activityLogDiv = document.getElementById('activity-log');
const clearLogBtn = document.getElementById('clear-log-btn');
const statSent = document.getElementById('stat-sent');
const statCommands = document.getElementById('stat-commands');
const helpLink = document.getElementById('help-link');

/**
 * Initialize popup
 */
async function init() {
  console.log('[RMCitecraft Popup] Initializing popup...');

  // Load saved settings
  await loadSettings();
  console.log('[RMCitecraft Popup] Settings loaded:', { rmcitecraftPort, autoActivateEnabled });

  // Update UI with loaded settings
  portInput.value = rmcitecraftPort;
  autoActivateToggle.checked = autoActivateEnabled;

  // Load activity log and stats
  await loadActivityLog();
  await loadStats();
  console.log('[RMCitecraft Popup] Activity log and stats loaded');

  // Check connection status
  await checkConnectionStatus();

  // Set up event listeners
  setupEventListeners();
  console.log('[RMCitecraft Popup] Event listeners set up');

  // Start periodic refresh
  setInterval(refreshStatus, REFRESH_INTERVAL_MS);
  console.log('[RMCitecraft Popup] Popup initialized successfully');
}

/**
 * Load settings from storage
 */
async function loadSettings() {
  const result = await chrome.storage.local.get(['port', 'autoActivate']);

  rmcitecraftPort = result.port || DEFAULT_PORT;
  autoActivateEnabled = result.autoActivate !== undefined ? result.autoActivate : true;
}

/**
 * Load activity log from storage
 */
async function loadActivityLog() {
  const result = await chrome.storage.local.get(['activityLog']);
  activityLog = result.activityLog || [];
  renderActivityLog();
}

/**
 * Load statistics from storage
 */
async function loadStats() {
  const result = await chrome.storage.local.get(['stats']);
  if (result.stats) {
    stats = result.stats;
  }
  renderStats();
}

/**
 * Save settings to storage
 */
async function saveSettings() {
  await chrome.storage.local.set({
    port: rmcitecraftPort,
    autoActivate: autoActivateEnabled
  });
}

/**
 * Save activity log to storage
 */
async function saveActivityLog() {
  await chrome.storage.local.set({ activityLog });
}

/**
 * Save statistics to storage
 */
async function saveStats() {
  await chrome.storage.local.set({ stats });
}

/**
 * Check connection status to RMCitecraft
 */
async function checkConnectionStatus() {
  try {
    const response = await fetch(`http://localhost:${rmcitecraftPort}/api/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });

    if (response.ok) {
      updateConnectionStatus(true);
      return true;
    } else {
      updateConnectionStatus(false);
      return false;
    }
  } catch (error) {
    updateConnectionStatus(false);
    return false;
  }
}

/**
 * Update connection status UI
 */
function updateConnectionStatus(connected) {
  if (connected) {
    statusIndicator.className = 'status-indicator status-connected';
    statusText.textContent = 'Connected';
    sendNowBtn.disabled = false;
  } else {
    statusIndicator.className = 'status-indicator status-disconnected';
    statusText.textContent = 'Disconnected';
    sendNowBtn.disabled = true;
  }
}

/**
 * Refresh status and update UI
 */
async function refreshStatus() {
  await checkConnectionStatus();
  await loadActivityLog();
  await loadStats();
  renderActivityLog();
  renderStats();
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
  // Save port configuration
  savePortBtn.addEventListener('click', async () => {
    const newPort = parseInt(portInput.value);
    if (newPort >= 1024 && newPort <= 65535) {
      rmcitecraftPort = newPort;
      await saveSettings();
      addLogEntry('info', `Port changed to ${newPort}`);
      await checkConnectionStatus();

      // Notify background script of port change
      chrome.runtime.sendMessage({
        type: 'PORT_CHANGED',
        port: newPort
      });
    } else {
      addLogEntry('error', 'Invalid port number (1024-65535)');
    }
  });

  // Toggle auto-activate
  autoActivateToggle.addEventListener('change', async () => {
    autoActivateEnabled = autoActivateToggle.checked;
    await saveSettings();
    addLogEntry('info', `Auto-send ${autoActivateEnabled ? 'enabled' : 'disabled'}`);

    // Notify background script
    chrome.runtime.sendMessage({
      type: 'AUTO_ACTIVATE_CHANGED',
      enabled: autoActivateEnabled
    });
  });

  // Manual send button
  sendNowBtn.addEventListener('click', async () => {
    console.log('[RMCitecraft Popup] Send button clicked');
    sendNowBtn.disabled = true;
    sendNowBtn.textContent = 'Sending...';

    try {
      // Get active tab
      console.log('[RMCitecraft Popup] Getting active tab...');
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      console.log('[RMCitecraft Popup] Active tab:', tab);

      if (!tab || !tab.url) {
        console.error('[RMCitecraft Popup] No active tab found');
        addLogEntry('error', 'No active tab found');
        return;
      }

      console.log('[RMCitecraft Popup] Tab URL:', tab.url);
      console.log('[RMCitecraft Popup] Tab ID:', tab.id);

      // Check if it's a FamilySearch page
      if (!tab.url.includes('familysearch.org')) {
        console.error('[RMCitecraft Popup] Not a FamilySearch page:', tab.url);
        addLogEntry('error', 'Not a FamilySearch page');
        return;
      }

      // Send message to content script
      console.log('[RMCitecraft Popup] Sending EXTRACT_AND_SEND message to tab', tab.id);

      const response = await chrome.tabs.sendMessage(tab.id, {
        type: 'EXTRACT_AND_SEND'
      }).catch(err => {
        console.error('[RMCitecraft Popup] sendMessage error:', err);
        throw err;
      });

      console.log('[RMCitecraft Popup] Response from content script:', response);

      if (response && response.success) {
        console.log('[RMCitecraft Popup] Data sent successfully');
        addLogEntry('success', 'Data sent successfully');
        stats.sentToday++;
        await saveStats();
      } else {
        console.error('[RMCitecraft Popup] Send failed:', response);
        addLogEntry('error', response?.error || 'Failed to send data');
      }
    } catch (error) {
      console.error('[RMCitecraft Popup] Exception in send handler:', error);
      addLogEntry('error', `Send failed: ${error.message}`);
    } finally {
      sendNowBtn.disabled = false;
      sendNowBtn.innerHTML = '<span class="btn-icon">📤</span> Send to RMCitecraft';
    }
  });

  // Clear log button
  clearLogBtn.addEventListener('click', async () => {
    activityLog = [];
    await saveActivityLog();
    renderActivityLog();
    addLogEntry('info', 'Activity log cleared');
  });

  // Help link
  helpLink.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({
      url: 'https://github.com/yourusername/RMCitecraft/wiki/Extension-Help'
    });
  });

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'LOG_ACTIVITY') {
      addLogEntry(message.level, message.message);
    } else if (message.type === 'STATS_UPDATE') {
      stats = message.stats;
      saveStats();
      renderStats();
    }
  });
}

/**
 * Add entry to activity log
 */
function addLogEntry(level, message) {
  const timestamp = new Date().toLocaleTimeString();

  const entry = {
    timestamp,
    level,
    message
  };

  activityLog.unshift(entry);

  // Keep only last MAX_LOG_ENTRIES
  if (activityLog.length > MAX_LOG_ENTRIES) {
    activityLog = activityLog.slice(0, MAX_LOG_ENTRIES);
  }

  saveActivityLog();
  renderActivityLog();
}

/**
 * Render activity log to DOM
 */
function renderActivityLog() {
  if (activityLog.length === 0) {
    activityLogDiv.innerHTML = `
      <div class="log-entry log-info">
        <span class="log-time">--:--:--</span>
        <span class="log-message">No activity yet</span>
      </div>
    `;
    return;
  }

  activityLogDiv.innerHTML = activityLog
    .map(entry => `
      <div class="log-entry log-${entry.level}">
        <span class="log-time">${entry.timestamp}</span>
        <span class="log-message">${escapeHtml(entry.message)}</span>
      </div>
    `)
    .join('');
}

/**
 * Render statistics to DOM
 */
function renderStats() {
  statSent.textContent = stats.sentToday;
  statCommands.textContent = stats.commandsReceived;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Format timestamp for display
 */
function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
