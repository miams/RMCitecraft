// Alternative keyboard-based approach for clicking download button
// This simulates keyboard presses which might be more reliable

async function downloadViaKeyboard() {
  log('Attempting keyboard-based download...');

  // Find and focus the download button
  const downloadButton = document.querySelector('button[data-testid="download-image-button"]');

  if (downloadButton) {
    log('Found download button, focusing and clicking...');
    downloadButton.focus();
    downloadButton.click();

    // Wait for dialog
    await new Promise(resolve => setTimeout(resolve, 800));

    // Simulate keyboard presses: tab down down tab tab enter
    log('Simulating keyboard: tab down down tab tab enter');

    const activeEl = document.activeElement;
    log('Active element after click:', activeEl?.tagName, activeEl?.type);

    // Tab (move to first radio button)
    simulateKey('Tab');
    await new Promise(resolve => setTimeout(resolve, 100));

    // Down arrow twice (move to 3rd option)
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

    log('Keyboard sequence completed');

    return {
      method: 'keyboard_automation',
      message: 'Used keyboard to select JPG and download'
    };
  }

  throw new Error('Download button not found');
}

function simulateKey(key) {
  const event = new KeyboardEvent('keydown', {
    key: key,
    code: key,
    keyCode: key === 'Tab' ? 9 : key === 'Enter' ? 13 : key === 'ArrowDown' ? 40 : 0,
    which: key === 'Tab' ? 9 : key === 'Enter' ? 13 : key === 'ArrowDown' ? 40 : 0,
    bubbles: true,
    cancelable: true
  });

  document.activeElement?.dispatchEvent(event);

  // Also dispatch keyup
  const eventUp = new KeyboardEvent('keyup', {
    key: key,
    code: key,
    keyCode: event.keyCode,
    which: event.which,
    bubbles: true,
    cancelable: true
  });

  document.activeElement?.dispatchEvent(eventUp);
}
