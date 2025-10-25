/**
 * RMCitecraft FamilySearch Assistant - Content Script
 *
 * Extracts census data from FamilySearch record pages and sends to RMCitecraft.
 * Automatically detects when on a census record page and extracts structured data.
 */

// Configuration
const AUTO_SEND_DELAY_MS = 2000; // Wait 2 seconds after page load before auto-sending
const DEBUG = true; // Enable console logging

/**
 * Log debug message
 */
function log(...args) {
  if (DEBUG) {
    console.log('[RMCitecraft Content]', ...args);
  }
}

/**
 * Check if this is a census record page
 */
function isCensusRecordPage() {
  // Check URL pattern for ARK or PAL census records
  const url = window.location.href;
  const isCensusURL = (url.includes('/ark:/') || url.includes('/pal:/')) &&
                      (url.includes('familysearch.org'));

  log('Checking if census page...');
  log('URL contains /ark:/ or /pal:/?', isCensusURL);

  if (!isCensusURL) {
    log('Not a census URL pattern');
    return false;
  }

  // Check page content for census indicators
  // FamilySearch may use different selectors, so check multiple
  const hasEventDate = document.querySelector('[data-testid="event-date"]') !== null;
  const hasEventPlace = document.querySelector('[data-testid="event-place"]') !== null;
  const hasCensusInTitle = document.title.toLowerCase().includes('census');
  const hasRecordTitle = document.querySelector('h1, h2, [data-testid="record-title"]') !== null;

  log('Detection checks:', {
    hasEventDate,
    hasEventPlace,
    hasCensusInTitle,
    hasRecordTitle,
    title: document.title
  });

  // If URL matches census pattern, assume it's a census page
  // FamilySearch structure changes frequently, so be permissive
  return isCensusURL;
}

/**
 * Extract census year from page
 */
function extractCensusYear() {
  // Try to find census year in page title or headings
  // Look for pattern: "Census, 1950" or "Census • United States, Census, 1950"
  const headings = document.querySelectorAll('h1, h2, h3, [data-testid="record-title"]');
  for (const heading of headings) {
    const text = heading.textContent;
    // Match "Census, YYYY" or "Census YYYY"
    const match = text.match(/Census[,\s•]+.*?(\b(?:17|18|19|20)\d{2}\b)/i);
    if (match) {
      return parseInt(match[1]);
    }
  }

  // Try document title
  const titleMatch = document.title.match(/Census[,\s]+.*?(\b(?:17|18|19|20)\d{2}\b)/i);
  if (titleMatch) {
    return parseInt(titleMatch[1]);
  }

  // Try URL
  const urlMatch = window.location.href.match(/census[\/\-_]?(17|18|19|20)\d{2}/i);
  if (urlMatch) {
    return parseInt(urlMatch[0].match(/\d{4}/)[0]);
  }

  return null;
}

/**
 * Extract text from element
 */
function extractText(selector) {
  const element = document.querySelector(selector);
  return element ? element.textContent.trim() : null;
}

/**
 * Extract data attribute
 */
function extractDataAttr(selector, attr) {
  const element = document.querySelector(selector);
  return element ? element.getAttribute(attr) : null;
}

/**
 * Extract value from FamilySearch table by label
 * FamilySearch uses <table> with <th> for labels and <td> for values
 */
function extractTableValue(labelText) {
  // Find all table rows
  const rows = document.querySelectorAll('table tr');

  for (const row of rows) {
    const th = row.querySelector('th');
    if (th && th.textContent.trim() === labelText) {
      const td = row.querySelector('td');
      if (td) {
        // Get text content, excluding nested <strong> if present
        // FamilySearch often wraps values in <strong> tags
        const strongElement = td.querySelector('strong');
        return strongElement ? strongElement.textContent.trim() : td.textContent.trim();
      }
    }
  }

  return null;
}

/**
 * Extract census data from FamilySearch page
 */
function extractCensusData() {
  log('Extracting census data from page...');

  const data = {
    // Page metadata
    familySearchUrl: window.location.href,
    extractedAt: new Date().toISOString(),
    censusYear: extractCensusYear(),

    // Person information - extracted from table
    name: extractTableValue('Name'),
    sex: extractTableValue('Sex'),
    age: extractTableValue('Age'),
    birthYear: extractTableValue('Birth Year (Estimated)') || extractTableValue('Birth Year'),
    birthplace: extractTableValue('Birthplace'),
    race: extractTableValue('Race'),
    relationship: extractTableValue('Relationship to Head of Household') || extractTableValue('Relationship'),
    maritalStatus: extractTableValue('Marital Status'),

    // Occupation/Industry (1950+)
    occupation: extractTableValue('Occupation'),
    industry: extractTableValue('Industry'),

    // Event information
    eventType: extractTableValue('Event Type'),
    eventDate: extractTableValue('Event Date'),
    eventPlace: extractTableValue('Event Place'),
    eventPlaceOriginal: extractTableValue('Event Place (Original)'),

    // Residence information (1940 and earlier)
    residenceDate: extractTableValue('Residence Date'),
    residencePlace: extractTableValue('Residence Place'),

    // Census-specific fields (vary by year)
    enumerationDistrict: extractTableValue('Enumeration District') ||
                         extractTableValue('Enumeration District Number') ||
                         extractTableValue('ED'),
    enumerationDistrictLocation: null, // Will be populated from 1940 format cleanup
    lineNumber: extractTableValue('Line Number') || extractTableValue('Line'),

    // Sheet/Page numbering (varies by year)
    // 1940 and earlier use Sheet Number + Sheet Letter
    // 1950+ use Page Number
    pageNumber: extractTableValue('Page Number') || extractTableValue('Page'),
    sheetNumber: extractTableValue('Sheet Number') || extractTableValue('Sheet'),
    sheetLetter: extractTableValue('Sheet Letter'),

    // Additional census fields
    familyNumber: extractTableValue('Family Number'),
    dwellingNumber: extractTableValue('Dwelling Number'),

    // Additional metadata
    filmNumber: extractTableValue('Film Number'),
    imageNumber: extractTableValue('Image Number'),
    affiliatePublicationNumber: extractTableValue('Affiliate Publication Number'),
  };

  // FALLBACK 1: Parse census year from eventDate if not found in page heading
  if (!data.censusYear && data.eventDate) {
    const yearMatch = data.eventDate.match(/\b(17|18|19|20)\d{2}\b/);
    if (yearMatch) {
      data.censusYear = parseInt(yearMatch[0]);
      log('Parsed census year from eventDate:', data.censusYear);
    }
  }

  // CLEANUP: Parse ED number from combined field (1940 format: "112-9 Mill Spring Township...")
  if (data.enumerationDistrict && /^\d+[-\d]*\s+[A-Z]/.test(data.enumerationDistrict)) {
    // Extract the number portion and the location portion separately
    const edMatch = data.enumerationDistrict.match(/^(\d+[-\d]*)\s+(.+)$/);
    if (edMatch) {
      data.enumerationDistrictLocation = edMatch[2]; // Save location info
      data.enumerationDistrict = edMatch[1]; // Keep just the number
      log('Parsed ED from combined field:', {
        district: data.enumerationDistrict,
        location: data.enumerationDistrictLocation
      });
    }
  }

  // FALLBACK 2: Parse enumeration district from eventPlaceOriginal if not found in table
  if (!data.enumerationDistrict && data.eventPlaceOriginal) {
    // Try pattern: "ED 98" or "ED 22-27"
    let edMatch = data.eventPlaceOriginal.match(/\bED\s+(\d+[-\d]*)\b/i);
    if (edMatch) {
      data.enumerationDistrict = edMatch[1];
      log('Parsed ED from eventPlaceOriginal:', data.enumerationDistrict);
    } else {
      // Try pattern: ", 233," (number between commas, common in 1910)
      edMatch = data.eventPlaceOriginal.match(/,\s+(\d{2,3}),/);
      if (edMatch) {
        data.enumerationDistrict = edMatch[1];
        log('Parsed ED number from eventPlaceOriginal:', data.enumerationDistrict);
      }
    }
  }

  // Clean up data (remove null values and trim whitespace)
  const cleanedData = {};
  for (const [key, value] of Object.entries(data)) {
    if (value !== null && value !== '') {
      cleanedData[key] = typeof value === 'string' ? value.trim() : value;
    }
  }

  log('Extracted data:', cleanedData);
  return cleanedData;
}

/**
 * Send data to RMCitecraft via background script
 */
async function sendToRMCitecraft(data) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: 'send_citation_data', data: data },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (response && response.status === 'success') {
          resolve(response.data);
        } else {
          reject(new Error(response?.error || 'Unknown error'));
        }
      }
    );
  });
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 16px 20px;
    background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6'};
    color: white;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    z-index: 10000;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    max-width: 300px;
  `;
  notification.textContent = message;

  document.body.appendChild(notification);

  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transition = 'opacity 0.3s';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

/**
 * Auto-extract and send data when page loads
 */
async function autoExtractAndSend() {
  if (!isCensusRecordPage()) {
    log('Not a census record page, skipping auto-extraction');
    return;
  }

  log('Census record page detected, waiting before auto-extraction...');

  // Wait for page to fully load
  await new Promise(resolve => setTimeout(resolve, AUTO_SEND_DELAY_MS));

  try {
    // Check if RMCitecraft is connected
    const { connected } = await new Promise(resolve => {
      chrome.runtime.sendMessage({ type: 'get_connection_status' }, resolve);
    });

    if (!connected) {
      log('RMCitecraft not connected, skipping auto-send');
      return;
    }

    // Extract and send data
    const data = extractCensusData();

    if (Object.keys(data).length > 2) { // At least more than URL and timestamp
      log('Sending data to RMCitecraft...');
      await sendToRMCitecraft(data);
      showNotification('✓ Sent to RMCitecraft', 'success');
      log('Data sent successfully');
    } else {
      log('Insufficient data extracted, not sending');
    }
  } catch (error) {
    log('Error during auto-extraction:', error);
    showNotification('⚠ RMCitecraft connection error', 'error');
  }
}

/**
 * Handle messages from popup and background script
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  log('Received message:', message.type);

  if (message.type === 'EXTRACT_AND_SEND') {
    // Manual send triggered from popup
    log('Manual send triggered');

    if (!isCensusRecordPage()) {
      sendResponse({
        success: false,
        error: 'Not a census record page'
      });
      return true;
    }

    // Extract and send data
    const data = extractCensusData();
    sendToRMCitecraft(data)
      .then(() => {
        sendResponse({ success: true });
      })
      .catch(error => {
        sendResponse({
          success: false,
          error: error.message
        });
      });

    return true; // Will respond asynchronously
  }

  if (message.type === 'download_image') {
    log('Received download_image command');

    // Find and click the download button on FamilySearch page
    const downloadButton = document.querySelector('[aria-label="Download"], [data-testid="download-button"], button[title="Download"]');

    if (downloadButton) {
      downloadButton.click();
      sendResponse({ status: 'success', message: 'Download initiated' });
      showNotification('⬇ Downloading image...', 'info');
    } else {
      sendResponse({ status: 'error', error: 'Download button not found' });
      showNotification('⚠ Download button not found', 'error');
    }

    return true; // Will respond asynchronously
  }
});

// Log that content script is loaded
log('Content script loaded on:', window.location.href);

// Initialize when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', autoExtractAndSend);
} else {
  autoExtractAndSend();
}

log('Content script initialized');
