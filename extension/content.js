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
 * Simulate keyboard key press
 */
function simulateKey(key) {
  const keyCode = key === 'Tab' ? 9 : key === 'Enter' ? 13 : key === 'ArrowDown' ? 40 : 0;

  const eventDown = new KeyboardEvent('keydown', {
    key: key,
    code: key,
    keyCode: keyCode,
    which: keyCode,
    bubbles: true,
    cancelable: true
  });

  document.activeElement?.dispatchEvent(eventDown);

  // Also dispatch keyup
  const eventUp = new KeyboardEvent('keyup', {
    key: key,
    code: key,
    keyCode: keyCode,
    which: keyCode,
    bubbles: true,
    cancelable: true
  });

  document.activeElement?.dispatchEvent(eventUp);
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
 * Download census image from FamilySearch
 */
async function downloadCensusImage() {
  log('Attempting to download census image...');

  // Check if we're on the image viewer page (ark:/61903/3:1:...)
  const currentUrl = window.location.href;
  const isImageViewerPage = currentUrl.includes('/ark:/61903/3:1:');
  const isRecordPage = currentUrl.includes('/ark:/61903/1:1:');

  log('Current page type:', { isImageViewerPage, isRecordPage, url: currentUrl });

  // STRATEGY 1: If on record page, navigate to image viewer first
  if (isRecordPage && !isImageViewerPage) {
    log('On record page - looking for link to image viewer...');

    // Look for image thumbnails or "View Image" links
    const imageLinks = document.querySelectorAll('a[href*="/ark:/61903/3:1:"]');

    if (imageLinks.length > 0) {
      const imageLink = imageLinks[0];
      log('Found image viewer link, will navigate and auto-download:', imageLink.href);

      // Store in sessionStorage for after page reload
      sessionStorage.setItem('rmcitecraft_auto_download', 'pending');
      sessionStorage.setItem('rmcitecraft_target_url', imageLink.href);

      // Navigate - download will happen automatically on new page
      setTimeout(() => {
        window.location.href = imageLink.href;
      }, 100);

      // Return immediately - actual download will be reported by new page
      return {
        method: 'navigating_to_viewer',
        message: 'Navigating to image viewer... (download will auto-trigger)'
      };
    }
  }

  // STRATEGY 2: If on image viewer page, click the download button
  if (isImageViewerPage) {
    log('On image viewer page - looking for download button...');

    // FamilySearch uses this specific test ID
    const downloadButton = document.querySelector('button[data-testid="download-image-button"]');

    if (downloadButton) {
      log('Found download button, focusing and clicking...');
      downloadButton.focus();
      downloadButton.click();

      // Wait for download options dialog to appear
      log('Waiting for download options dialog...');
      await new Promise(resolve => setTimeout(resolve, 800));

      // Use keyboard automation to select JPG Only and download
      // Keyboard sequence: tab down down tab tab enter
      // - Tab: move to first radio button
      // - Down Down: move to 3rd option (JPG Only)
      // - Tab Tab: move to DOWNLOAD button
      // - Enter: click DOWNLOAD
      log('Using keyboard automation: tab down down tab tab enter');

      // Tab (move to first radio button)
      simulateKey('Tab');
      await new Promise(resolve => setTimeout(resolve, 100));

      // Down arrow twice (move to 3rd option - JPG Only)
      simulateKey('ArrowDown');
      await new Promise(resolve => setTimeout(resolve, 100));
      simulateKey('ArrowDown');
      await new Promise(resolve => setTimeout(resolve, 100));

      // Tab twice (move to Download button)
      simulateKey('Tab');
      await new Promise(resolve => setTimeout(resolve, 100));
      simulateKey('Tab');
      await new Promise(resolve => setTimeout(resolve, 100));

      // Enter (click Download)
      simulateKey('Enter');
      await new Promise(resolve => setTimeout(resolve, 500));

      log('Keyboard sequence completed - download should start');

      return {
        method: 'keyboard_automation',
        message: 'Used keyboard to select JPG Only and initiate download'
      };
    }

    // Fallback: Try other download button selectors
    const fallbackSelectors = [
      'button[aria-label="Download"]',
      'button[aria-label*="Download"]',
      '[data-testid="download-button"]'
    ];

    for (const selector of fallbackSelectors) {
      const button = document.querySelector(selector);
      if (button) {
        log('Found download button via fallback selector:', selector);
        button.click();

        await new Promise(resolve => setTimeout(resolve, 1000));

        return {
          method: 'button_click_fallback',
          message: 'Download button clicked via fallback method'
        };
      }
    }
  }

  // STRATEGY 3: Try to find image URL directly (last resort)
  log('Trying direct image URL extraction...');

  const imageSelectors = [
    'img[src*="familysearch"]',
    'img[class*="image"]',
    'canvas', // FamilySearch sometimes uses canvas for images
    '[data-testid*="image"] img'
  ];

  let imageUrl = null;
  for (const selector of imageSelectors) {
    const img = document.querySelector(selector);
    if (img && img.src && img.src.includes('http')) {
      imageUrl = img.src;
      log('Found image via selector:', selector, imageUrl);
      break;
    }
  }

  if (imageUrl) {
    try {
      // Request download via background script
      const response = await chrome.runtime.sendMessage({
        type: 'DOWNLOAD_FILE',
        url: imageUrl,
        filename: 'census-image.jpg'
      });

      if (response && response.success) {
        log('Download initiated via chrome.downloads');
        return {
          method: 'chrome_download',
          downloadId: response.downloadId,
          url: imageUrl
        };
      }
    } catch (error) {
      log('Chrome download failed:', error);
    }
  }

  throw new Error('Could not find census image or download button on this page. Please ensure you are on the image viewer page (URL should contain ark:/61903/3:1:)');
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
    log('Received download_image command from RMCitecraft');

    // Try to find and download the image
    downloadCensusImage()
      .then((result) => {
        sendResponse({ status: 'success', ...result });
        showNotification('⬇ Image downloaded', 'success');
      })
      .catch((error) => {
        sendResponse({ status: 'error', error: error.message });
        showNotification(`⚠ Download failed: ${error.message}`, 'error');
      });

    return true; // Will respond asynchronously
  }
});

/**
 * Check if we should auto-download after navigation
 */
async function checkAutoDownload() {
  // Check if auto-download flag is set (from navigation)
  const autoDownload = sessionStorage.getItem('rmcitecraft_auto_download');
  const targetUrl = sessionStorage.getItem('rmcitecraft_target_url');

  if (autoDownload === 'pending') {
    log('Auto-download pending - verifying we arrived at correct page...');

    const currentUrl = window.location.href;
    const isImageViewerPage = currentUrl.includes('/ark:/61903/3:1:');

    // Verify we're on the expected page
    if (isImageViewerPage) {
      log('Confirmed on image viewer page - preparing auto-download...');

      // Clear flags
      sessionStorage.removeItem('rmcitecraft_auto_download');
      sessionStorage.removeItem('rmcitecraft_target_url');

      // Wait for download button to appear (FamilySearch is slow to render)
      log('Waiting for download button to appear...');

      let downloadButton = null;
      const maxAttempts = 15; // Try for up to 15 seconds

      // Multiple selectors to try
      const buttonSelectors = [
        'button[data-testid="download-image-button"]',
        'button[aria-label="Download"]',
        'button[aria-label*="Download"]',
        'button:has-text("Download")',
        '[data-testid*="download"]'
      ];

      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        // Try each selector
        for (const selector of buttonSelectors) {
          try {
            downloadButton = document.querySelector(selector);
            if (downloadButton) {
              log(`Download button found using selector: ${selector}`);
              break;
            }
          } catch (e) {
            // Ignore selector errors (like :has-text which may not work)
          }
        }

        // If still not found, try finding any button with "Download" text
        if (!downloadButton) {
          const allButtons = document.querySelectorAll('button');
          for (const btn of allButtons) {
            if (btn.getAttribute('aria-label')?.toLowerCase().includes('download') ||
                btn.textContent?.toLowerCase().includes('download')) {
              downloadButton = btn;
              log('Download button found by searching all buttons');
              break;
            }
          }
        }

        if (downloadButton) {
          log(`Download button found after ${attempt} second(s)`);
          break;
        }

        log(`Attempt ${attempt}/${maxAttempts}: button not found yet, waiting...`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      if (!downloadButton) {
        log('ERROR: Download button never appeared after 15 seconds');
        showNotification('⚠ Timeout: Download button did not appear', 'error');
        return;
      }

      try {
        log('Starting auto-download...');
        const result = await downloadCensusImage();
        log('Auto-download SUCCESS:', result);
        showNotification('✅ Census image downloaded automatically', 'success');

        // Notify background script of success (for logging/monitoring)
        try {
          await chrome.runtime.sendMessage({
            type: 'AUTO_DOWNLOAD_SUCCESS',
            result: result
          });
        } catch (e) {
          log('Failed to notify background script:', e);
        }

      } catch (error) {
        log('Auto-download FAILED:', error);
        showNotification(`⚠ Auto-download failed: ${error.message}`, 'error');

        // Notify background script of failure
        try {
          await chrome.runtime.sendMessage({
            type: 'AUTO_DOWNLOAD_FAILED',
            error: error.message
          });
        } catch (e) {
          log('Failed to notify background script:', e);
        }
      }
    } else {
      log('NOT on image viewer page after navigation - clearing flags');
      sessionStorage.removeItem('rmcitecraft_auto_download');
      sessionStorage.removeItem('rmcitecraft_target_url');
    }
  }
}

// Log that content script is loaded
log('Content script loaded on:', window.location.href);

// Initialize when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    autoExtractAndSend();
    checkAutoDownload();
  });
} else {
  autoExtractAndSend();
  checkAutoDownload();
}

log('Content script initialized');
