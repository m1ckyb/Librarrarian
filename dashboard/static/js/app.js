// --- Utility Functions ---
/**
 * Escapes HTML special characters to prevent XSS vulnerabilities
 * @param {string} text - The text to escape
 * @returns {string} The escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Sonarr Tools Logic (Corrected and placed in index.html) ---
const sonarrRenameScanButton = document.getElementById('sonarr-rename-scan-button');
const sonarrQualityScanButton = document.getElementById('sonarr-quality-scan-button');
const sonarrCancelScanButton = document.getElementById('sonarr-cancel-scan-button');

// Radarr scan buttons
const radarrRenameScanButton = document.getElementById('radarr-rename-scan-button');
const radarrCancelScanButton = document.getElementById('radarr-cancel-scan-button');

// Lidarr scan buttons
const lidarrRenameScanButton = document.getElementById('lidarr-rename-scan-button');
const lidarrCancelScanButton = document.getElementById('lidarr-cancel-scan-button');

// Rename the quality scan button as requested.
if (sonarrQualityScanButton) {
    sonarrQualityScanButton.textContent = 'Scan for Quality Mismatches';
}

// Progress elements for Rename Scan
const sonarrRenameScanContainer = document.getElementById('sonarr-rename-scan-container');
const sonarrRenameScanFeedback = document.getElementById('sonarr-rename-scan-feedback');
const sonarrRenameScanProgress = document.getElementById('sonarr-rename-scan-progress');
const sonarrRenameScanProgressBar = sonarrRenameScanProgress ? sonarrRenameScanProgress.querySelector('.progress-bar') : null;
const sonarrRenameScanProgressText = document.getElementById('sonarr-rename-scan-progress-text');
const sonarrRenameScanTime = document.getElementById('sonarr-rename-scan-time');

// Progress elements for Quality Scan
const sonarrQualityScanContainer = document.getElementById('sonarr-quality-scan-container');
const sonarrQualityScanFeedback = document.getElementById('sonarr-quality-scan-feedback');
const sonarrQualityScanProgress = document.getElementById('sonarr-quality-scan-progress');
const sonarrQualityScanProgressBar = sonarrQualityScanProgress ? sonarrQualityScanProgress.querySelector('.progress-bar') : null;
const sonarrQualityScanProgressText = document.getElementById('sonarr-quality-scan-progress-text');
const sonarrQualityScanTime = document.getElementById('sonarr-quality-scan-time');

// Progress elements for Radarr Rename Scan
const radarrRenameScanContainer = document.getElementById('radarr-rename-scan-container');
const radarrRenameScanFeedback = document.getElementById('radarr-rename-scan-feedback');
const radarrRenameScanProgress = document.getElementById('radarr-rename-scan-progress');
const radarrRenameScanProgressBar = radarrRenameScanProgress ? radarrRenameScanProgress.querySelector('.progress-bar') : null;
const radarrRenameScanProgressText = document.getElementById('radarr-rename-scan-progress-text');
const radarrRenameScanTime = document.getElementById('radarr-rename-scan-time');

// Progress elements for Lidarr Rename Scan
const lidarrRenameScanContainer = document.getElementById('lidarr-rename-scan-container');
const lidarrRenameScanFeedback = document.getElementById('lidarr-rename-scan-feedback');
const lidarrRenameScanProgress = document.getElementById('lidarr-rename-scan-progress');
const lidarrRenameScanProgressBar = lidarrRenameScanProgress ? lidarrRenameScanProgress.querySelector('.progress-bar') : null;
const lidarrRenameScanProgressText = document.getElementById('lidarr-rename-scan-progress-text');
const lidarrRenameScanTime = document.getElementById('lidarr-rename-scan-time');

let isPollingForScan = false;
let activeScanType = null;
let activeScanSource = null; // 'sonarr', 'radarr', or 'lidarr'
let progressInterval = null;
let scanStartTime = null;

/**
 * Formats elapsed time in seconds to a human-readable string.
 * e.g., 64 seconds becomes "1m 04s", 120 seconds becomes "2m 00s"
 */
function formatElapsedTime(totalSeconds) {
    if (totalSeconds < 60) {
        return `${totalSeconds}s`;
    }
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}

function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    isPollingForScan = false;
    activeScanType = null;
    activeScanSource = null;
}

function getScanElements(scanType, scanSource) {
    if (scanSource === 'radarr') {
        return {
            feedbackEl: radarrRenameScanFeedback,
            containerEl: radarrRenameScanContainer,
            progressEl: radarrRenameScanProgress,
            progressBarEl: radarrRenameScanProgressBar,
            progressTextEl: radarrRenameScanProgressText,
            timeEl: radarrRenameScanTime
        };
    }
    if (scanSource === 'lidarr') {
        return {
            feedbackEl: lidarrRenameScanFeedback,
            containerEl: lidarrRenameScanContainer,
            progressEl: lidarrRenameScanProgress,
            progressBarEl: lidarrRenameScanProgressBar,
            progressTextEl: lidarrRenameScanProgressText,
            timeEl: lidarrRenameScanTime
        };
    }
    // Default to Sonarr
    if (scanType === 'rename') {
        return {
            feedbackEl: sonarrRenameScanFeedback,
            containerEl: sonarrRenameScanContainer,
            progressEl: sonarrRenameScanProgress,
            progressBarEl: sonarrRenameScanProgressBar,
            progressTextEl: sonarrRenameScanProgressText,
            timeEl: sonarrRenameScanTime
        };
    } else {
        return {
            feedbackEl: sonarrQualityScanFeedback,
            containerEl: sonarrQualityScanContainer,
            progressEl: sonarrQualityScanProgress,
            progressBarEl: sonarrQualityScanProgressBar,
            progressTextEl: sonarrQualityScanProgressText,
            timeEl: sonarrQualityScanTime
        };
    }
}

function showScanFeedback(message, type, scanType, scanSource = 'sonarr') {
    const { feedbackEl, containerEl } = getScanElements(scanType, scanSource);
    if (!feedbackEl || !containerEl) return;
    feedbackEl.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
    containerEl.style.display = 'block';
    feedbackEl.style.display = 'block';
}

// Keep legacy function for backward compatibility
function showSonarrFeedback(message, type, scanType) {
    showScanFeedback(message, type, scanType, 'sonarr');
}

function resetScanUI() {
    // Stop any polling and clear timers
    stopProgressPolling();

    // Hide progress bars and feedback containers for Sonarr
    if(sonarrRenameScanContainer) sonarrRenameScanContainer.style.display = 'none';
    if(sonarrQualityScanContainer) sonarrQualityScanContainer.style.display = 'none';

    // Hide progress bars and feedback containers for Radarr
    if(radarrRenameScanContainer) radarrRenameScanContainer.style.display = 'none';

    // Hide progress bars and feedback containers for Lidarr
    if(lidarrRenameScanContainer) lidarrRenameScanContainer.style.display = 'none';

    // Re-enable scan buttons, hide cancel buttons for Sonarr
    if(sonarrRenameScanButton) sonarrRenameScanButton.disabled = false;
    if(sonarrQualityScanButton) sonarrQualityScanButton.disabled = false;
    if(sonarrCancelScanButton) sonarrCancelScanButton.style.display = 'none';

    // Re-enable scan buttons, hide cancel buttons for Radarr
    if(radarrRenameScanButton) radarrRenameScanButton.disabled = false;
    if(radarrCancelScanButton) radarrCancelScanButton.style.display = 'none';

    // Re-enable scan buttons, hide cancel buttons for Lidarr
    if(lidarrRenameScanButton) lidarrRenameScanButton.disabled = false;
    if(lidarrCancelScanButton) lidarrCancelScanButton.style.display = 'none';
}

function startProgressPolling(scanType, scanSource = 'sonarr') {
    stopProgressPolling();

    const { containerEl, progressEl, progressBarEl, progressTextEl, timeEl, feedbackEl } = getScanElements(scanType, scanSource);

    if (!containerEl || !progressEl) return;

    // Clear feedback when progress starts
    if (feedbackEl) {
        feedbackEl.innerHTML = '';
    }

    containerEl.style.display = 'block';
    progressEl.style.display = 'block';
    progressBarEl.style.width = '0%';
    progressBarEl.textContent = '0%';
    progressTextEl.textContent = 'Starting scan...';
    scanStartTime = new Date();
    activeScanSource = scanSource;
    activeScanType = scanType;

    progressInterval = setInterval(() => {
        fetch('/api/scan/progress')
            .then(response => response.json())
            .then(data => {
                const now = new Date();
                const elapsedSeconds = Math.round((now - scanStartTime) / 1000);
                if(timeEl) timeEl.textContent = `Elapsed: ${formatElapsedTime(elapsedSeconds)}`;

                if (data.is_running) {
                    const progressPercent = data.total_steps > 0 ? ((data.progress / data.total_steps) * 100).toFixed(1) : 0;
                    if (progressBarEl) progressBarEl.style.width = `${progressPercent}%`;
                    if (progressBarEl) progressBarEl.textContent = `${progressPercent}%`;
                    if (progressTextEl) progressTextEl.textContent = data.current_step || 'Scanning...';
                } else {
                    // Scan finished or failed to start
                    stopProgressPolling();
                    
                    // Check if this is an error/conflict message vs a success
                    // Also check if progress is 0 - this indicates the scan never really started
                    const currentStep = data.current_step || '';
                    const isError = currentStep.toLowerCase().includes('error') || 
                                    currentStep.toLowerCase().includes('already in progress') ||
                                    currentStep.toLowerCase().includes('cancelled') ||
                                    (data.progress === 0 && data.total_steps === 0);
                    
                    if (isError) {
                        // Don't show 100% progress bar for errors
                        showScanFeedback(currentStep || 'Scan was interrupted.', 'warning', scanType, scanSource);
                        resetScanUI();
                    } else {
                        if (progressBarEl) progressBarEl.style.width = '100%';
                        if (progressBarEl) progressBarEl.textContent = '100%';
                        if (progressTextEl) progressTextEl.textContent = currentStep || 'Scan complete.';
                        // Just reset the UI after a brief delay without showing a separate alert
                        setTimeout(resetScanUI, 2000);
                    }
                }
            })
            .catch(error => {
                console.error('Error polling for scan progress:', error);
                stopProgressPolling();
                resetScanUI();
                showScanFeedback('Error polling for scan progress.', 'danger', scanType, scanSource);
            });
    }, 2000); // Poll every 2 seconds
}

async function handleScanButtonClick(scanType, scanSource = 'sonarr') {
    // If a scan is already running, don't start another one.
    if (isPollingForScan) {
        console.warn("A scan is already in progress. Please wait or cancel it.");
        return;
    }

    // Disable all scan buttons to prevent double-clicking
    if (sonarrRenameScanButton) sonarrRenameScanButton.disabled = true;
    if (sonarrQualityScanButton) sonarrQualityScanButton.disabled = true;
    if (radarrRenameScanButton) radarrRenameScanButton.disabled = true;
    if (lidarrRenameScanButton) lidarrRenameScanButton.disabled = true;

    // Determine the endpoint based on scan source and type
    let endpoint;
    if (scanSource === 'radarr') {
        endpoint = '/api/scan/radarr_rename';
    } else if (scanSource === 'lidarr') {
        endpoint = '/api/scan/lidarr_rename';
    } else {
        endpoint = scanType === 'rename' ? '/api/scan/rename' : '/api/scan/quality';
    }

    try {
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            isPollingForScan = true;
            showScanFeedback(`'${scanType}' scan started successfully.`, 'success', scanType, scanSource);
            
            // Keep all scan buttons visible but disabled, show appropriate cancel button
            if (sonarrRenameScanButton) sonarrRenameScanButton.disabled = true;
            if (sonarrQualityScanButton) sonarrQualityScanButton.disabled = true;
            if (radarrRenameScanButton) radarrRenameScanButton.disabled = true;
            if (lidarrRenameScanButton) lidarrRenameScanButton.disabled = true;
            
            if (scanSource === 'radarr') {
                if (radarrCancelScanButton) radarrCancelScanButton.style.display = 'inline-block';
            } else if (scanSource === 'lidarr') {
                if (lidarrCancelScanButton) lidarrCancelScanButton.style.display = 'inline-block';
            } else {
                if (sonarrCancelScanButton) sonarrCancelScanButton.style.display = 'inline-block';
            }
            
            startProgressPolling(scanType, scanSource);
        } else {
            showScanFeedback(data.message || `Failed to start '${scanType}' scan.`, 'danger', scanType, scanSource);
            resetScanUI(); // Re-enable buttons on failure
        }
    } catch (error) {
        console.error(`Error starting ${scanSource} ${scanType} scan:`, error);
        showScanFeedback(`An error occurred while starting the '${scanType}' scan.`, 'danger', scanType, scanSource);
        resetScanUI(); // Re-enable buttons on error
    }
}

if (sonarrRenameScanButton) {
    sonarrRenameScanButton.addEventListener('click', () => handleScanButtonClick('rename', 'sonarr'));
}

if (sonarrQualityScanButton) {
    sonarrQualityScanButton.addEventListener('click', () => handleScanButtonClick('quality', 'sonarr'));
}

if (radarrRenameScanButton) {
    radarrRenameScanButton.addEventListener('click', () => handleScanButtonClick('rename', 'radarr'));
}

if (lidarrRenameScanButton) {
    lidarrRenameScanButton.addEventListener('click', () => handleScanButtonClick('rename', 'lidarr'));
}

if (sonarrCancelScanButton) {
    sonarrCancelScanButton.addEventListener('click', async () => {
        // Save the current scan context before any async operations
        const currentScanType = activeScanType || 'rename';
        const currentScanSource = activeScanSource || 'sonarr';
        
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', currentScanType, currentScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', currentScanType, currentScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', currentScanType, currentScanSource);
            // Still reset the UI on error to avoid getting stuck
            resetScanUI();
        }
    });
}

if (radarrCancelScanButton) {
    radarrCancelScanButton.addEventListener('click', async () => {
        // Save the current scan context before any async operations
        const currentScanType = activeScanType || 'rename';
        const currentScanSource = activeScanSource || 'radarr';
        
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', currentScanType, currentScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', currentScanType, currentScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', currentScanType, currentScanSource);
            // Still reset the UI on error to avoid getting stuck
            resetScanUI();
        }
    });
}

if (lidarrCancelScanButton) {
    lidarrCancelScanButton.addEventListener('click', async () => {
        // Save the current scan context before any async operations
        const currentScanType = activeScanType || 'rename';
        const currentScanSource = activeScanSource || 'lidarr';
        
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', currentScanType, currentScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', currentScanType, currentScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', currentScanType, currentScanSource);
            // Still reset the UI on error to avoid getting stuck
            resetScanUI();
        }
    });
}

// On page load, check if a scan is already running and resume polling
fetch('/api/scan/progress').then(r => r.json()).then(data => {
    if (data.is_running) {
        // Use the scan_source and scan_type fields if available, otherwise fall back to inference
        let runningScanType = data.scan_type || 'rename';
        let runningScanSource = data.scan_source || 'sonarr';
        
        // Fallback: Infer from current_step if the new fields are empty (for backwards compatibility)
        if (!data.scan_source && data.current_step) {
            if (data.current_step.toLowerCase().includes('quality')) {
                runningScanType = 'quality';
            }
            if (data.current_step.toLowerCase().includes('radarr')) {
                runningScanSource = 'radarr';
            }
            if (data.current_step.toLowerCase().includes('lidarr')) {
                runningScanSource = 'lidarr';
            }
        }
        // Resume the UI state without triggering a new API call
        // Just start polling for progress and update UI accordingly
        resumeScanUI(runningScanType, runningScanSource);
    }
});

/**
 * Resumes the scan UI state when a scan is already in progress on page load.
 * Unlike handleScanButtonClick, this does NOT trigger a new API call.
 */
function resumeScanUI(scanType, scanSource) {
    if (isPollingForScan) {
        console.warn("Already polling for a scan.");
        return;
    }
    
    isPollingForScan = true;
    activeScanType = scanType;
    activeScanSource = scanSource;
    
    // Keep all scan buttons visible but disabled, show appropriate cancel button
    if (sonarrRenameScanButton) sonarrRenameScanButton.disabled = true;
    if (sonarrQualityScanButton) sonarrQualityScanButton.disabled = true;
    if (radarrRenameScanButton) radarrRenameScanButton.disabled = true;
    if (lidarrRenameScanButton) lidarrRenameScanButton.disabled = true;
    
    if (scanSource === 'radarr') {
        if (radarrCancelScanButton) radarrCancelScanButton.style.display = 'inline-block';
    } else if (scanSource === 'lidarr') {
        if (lidarrCancelScanButton) lidarrCancelScanButton.style.display = 'inline-block';
    } else {
        if (sonarrCancelScanButton) sonarrCancelScanButton.style.display = 'inline-block';
    }
    
    startProgressPolling(scanType, scanSource);
}

// Function to create an HTML element for a single node
function createNodeCard(node) {
    const isIdle = node.status === 'idle' || node.percent === 0;
    const isPaused = node.command === 'paused';
    const pauseButtonIcon = isPaused ? 'play' : 'pause';
    const pauseButtonText = isPaused ? 'Resume' : 'Pause';
    
    // Determine button disabled states
    const startDisabled = (node.status !== 'offline' && node.command !== 'idle') ? 'disabled' : '';
    const stopDisabled = (node.command === 'idle' || node.status === 'offline') ? 'disabled' : '';
    const pauseDisabled = (node.command === 'idle' || node.status === 'offline') ? 'disabled' : '';
    
    return `
    <div class="card mb-3">
        <div id="node-${node.hostname}" class="card-header fs-5 d-flex justify-content-between align-items-center">
            <span>
                <span class="health-icon me-2" title="Calculating...">●</span>${node.hostname}
                ${node.version_mismatch ? `<strong class="text-warning ms-3">** Version Mismatch **</strong>` : ''}
            </span>
            <div>
                <div class="btn-group btn-group-sm me-2" role="group" style="gap: 4px;">
                    <button class="btn btn-outline-secondary" onclick="showNodeOptions('${node.hostname}')"><span class="mdi mdi-cog"></span> Options</button>
                    <button class="btn btn-outline-success" onclick="startNode('${node.hostname}')" ${startDisabled}><span class="mdi mdi-play"></span> Start</button>
                    <button class="btn btn-outline-danger" onclick="stopNode('${node.hostname}')" ${stopDisabled}><span class="mdi mdi-stop"></span> Stop</button>
                    <button class="btn btn-outline-warning" onclick="pauseResumeNode('${node.hostname}', '${node.command}')" ${pauseDisabled}><span class="mdi mdi-${pauseButtonIcon}"></span> ${pauseButtonText}</button>
                </div>
                <span class="badge ${node.version_mismatch ? 'badge-outline-danger' : 'badge-outline-info'}">${node.version || 'N/A'}</span>
            </div>
        </div>
        <div class="card-body">
            ${node.percent > 0 ? `
                <p class="card-text text-body-secondary mb-2" style="font-family: monospace;">${node.current_file || 'N/A'}</p>
                <div class="progress" role="progressbar">
                    <div class="progress-bar progress-bar-striped progress-bar-animated text-bg-teal" style="width: ${node.percent}%">
                        <b>${node.percent}%</b>
                    </div>
                </div>
            ` : `
                <div class="text-center p-3">
                    <h5 class="card-title text-muted">${node.command === 'paused' ? 'Paused' : (node.status === 'offline' ? 'Offline' : (node.current_file || 'Idle'))}</h5>
                </div>
            `}
        </div>
        <div class="card-footer d-flex justify-content-between align-items-center bg-transparent">
            <div>
                <span class="badge badge-outline-secondary">Uptime: ${node.uptime_str || 'N/A'}</span>
            </div>
            <div>
            ${node.percent > 0 ? `
                <span class="badge badge-outline-secondary me-2">FPS: ${node.fps || 'N/A'}</span>
                <span class="badge badge-outline-secondary me-2">Speed: ${node.speed}x</span>
                <span class="badge badge-outline-teal me-2">Codec: ${node.codec}</span>
                <span class="badge badge-outline-info">ETA: ${node.eta || 'N/A'}</span>
            ` : `
                <span class="badge badge-outline-secondary">${node.command === 'paused' ? 'Paused' : (node.status === 'offline' ? 'Offline' : 'Idle')}</span>
            `}
            </div>
        </div>
    </div>`;
}

// Main function to fetch data and update the DOM
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        // Update summary badges
        const failCount = data.fail_count;
        const failCountBadge = document.getElementById('fail-count-badge');
        const viewErrorsBtn = document.getElementById('view-errors-btn');
        failCountBadge.innerText = failCount;
        
        // Update View Errors button color
        // Remove all potential color classes first
        viewErrorsBtn.classList.remove('btn-outline-danger', 'btn-outline-success', 'btn-outline-warning');
        const clearErrorsBtn = document.getElementById('clear-errors-btn');
        clearErrorsBtn.style.display = (failCount > 0) ? 'inline-block' : 'none';

        // If there are errors, the button is always red.
        if (failCount > 0) {
            viewErrorsBtn.classList.add('btn-outline-danger');
            failCountBadge.classList.add('text-bg-light');
        }
        
        // Update DB error alert
        const errorAlert = document.getElementById('db-error-alert');
        if (data.db_error) {
            errorAlert.innerHTML = `<strong>Database Error:</strong> ${data.db_error}`;
            errorAlert.classList.remove('d-none');
        } else {
            errorAlert.classList.add('d-none');
        }

        // --- Update Pause Queue Button State ---
        const pauseQueueBtn = document.getElementById('pause-queue-btn');
        if (data.queue_paused) {
            pauseQueueBtn.classList.remove('btn-outline-warning');
            pauseQueueBtn.classList.add('btn-outline-success');
            pauseQueueBtn.innerHTML = `<span class="mdi mdi-play"></span> Resume Queue`;
            pauseQueueBtn.title = "Resume the distribution of new jobs to workers";
        } else {
            pauseQueueBtn.classList.remove('btn-outline-success');
            pauseQueueBtn.classList.add('btn-outline-warning');
            pauseQueueBtn.innerHTML = `<span class="mdi mdi-pause"></span> Pause Queue`;
            pauseQueueBtn.title = "Pause the distribution of new jobs to workers";
        }

        // Update nodes list
        const nodesContainer = document.getElementById('nodes-container');
        if (data.nodes && data.nodes.length > 0) {
            nodesContainer.innerHTML = data.nodes.map(createNodeCard).join('');
        } else {
            nodesContainer.innerHTML = `
            <div class="text-center p-5">
                <p class="text-muted">No active nodes found.</p>
            </div>`;
        }

        // --- NEW: Update Health Icons ---
        data.nodes.forEach(node => {
            const cardHeader = document.getElementById(`node-${node.hostname}`);
            if (cardHeader) {
                const healthIcon = cardHeader.querySelector('.health-icon');
                if (node.age < 30) {
                    healthIcon.style.color = 'green';
                    healthIcon.title = `Healthy (last seen ${Math.round(node.age)}s ago)`;
                } else if (node.age < 60) {
                    healthIcon.style.color = 'orange';
                    healthIcon.title = `Warning (last seen ${Math.round(node.age)}s ago)`;
                } else {
                    healthIcon.style.color = 'red';
                    healthIcon.title = `Critical (last seen ${Math.round(node.age)}s ago)`;
                }
            }
        });
    } catch (error) {
        console.error("Failed to fetch status:", error);
        const errorAlert = document.getElementById('db-error-alert');
        errorAlert.innerHTML = `<strong>Frontend Error:</strong> Could not fetch status from the server.`;
        errorAlert.classList.remove('d-none');
    }
}

// Function to fetch and display failures in the modal
const viewErrorsBtn = document.getElementById('view-errors-btn');
if (viewErrorsBtn) {
    viewErrorsBtn.addEventListener('click', async () => {
        const tableBody = document.getElementById('failures-table-body');
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading...</td></tr>';
        try {
            const response = await fetch('/api/failures');
            const data = await response.json();
            if (data.files && data.files.length > 0) {
                tableBody.innerHTML = data.files.map((file, index) => {
                    let actionsHtml = '';
                    if (file.type === 'stuck_job') {
                        // Stuck job: show re-add and clear buttons
                        actionsHtml = `
                            <div class="btn-group btn-group-sm" role="group">
                                <button class="btn btn-outline-primary" onclick="requeueFailedJob(${file.id})" title="Re-add to queue">
                                    <span class="mdi mdi-refresh"></span> Re-add
                                </button>
                                <button class="btn btn-outline-danger" onclick="deleteFailedJob(${file.id})" title="Remove stuck job">
                                    <span class="mdi mdi-delete"></span> Clear
                                </button>
                            </div>
                            <button class="btn btn-sm btn-outline-secondary mt-1" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-log-${index}">
                                View Details
                            </button>
                        `;
                    } else {
                        // Regular failed file: show view log button
                        actionsHtml = `
                            <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-log-${index}">
                                View Log
                            </button>
                        `;
                    }
                    
                    return `
                        <tr>
                            <td style="word-break: break-all;">${file.filename}</td>
                            <td>${file.reason}</td>
                            <td>${file.reported_at}</td>
                            <td>${actionsHtml}</td>
                        </tr>
                        <tr class="collapse" id="collapse-log-${index}">
                            <td colspan="4"><pre class="bg-dark text-white-50 p-3 rounded" style="max-height: 300px; overflow-y: auto;">${file.log || 'No log available.'}</pre></td>
                        </tr>
                    `;
                }).join('');
            } else {
                tableBody.innerHTML = '<tr><td colspan="4" class="text-center">No failed files or stuck jobs found.</td></tr>';
            }
        } catch (error) {
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Failed to load errors.</td></tr>';
        }
    });
}

// Shared function to clear all failures
async function clearAllFailures() {
    if (!confirm('Are you sure you want to permanently clear all failed file logs? This action cannot be undone.')) {
        return;
    }
    try {
        const response = await fetch('/api/failures/clear', { method: 'POST' });
        if (response.ok) {
            // Manually close the modal if it's open
            const modal = bootstrap.Modal.getInstance(document.getElementById('failuresModal'));
            if (modal) modal.hide();
            // Refresh the status to update the count
            updateStatus();
        }
    } catch (error) {
        alert('An error occurred while trying to clear the failures.');
    }
}

// Function to clear all failures (header button)
const clearErrorsBtn = document.getElementById('clear-errors-btn');
if (clearErrorsBtn) {
    clearErrorsBtn.addEventListener('click', clearAllFailures);
}

// Function to clear all failures (modal button)
const modalClearAllErrorsBtn = document.getElementById('modal-clear-all-errors-btn');
if (modalClearAllErrorsBtn) {
    modalClearAllErrorsBtn.addEventListener('click', clearAllFailures);
}

// Function to re-queue a stuck job from the failures modal
window.requeueFailedJob = async function(jobId) {
    if (!confirm(`Are you sure you want to re-add job ${jobId} to the queue? This will reset it to pending status.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/jobs/requeue/${jobId}`, { method: 'POST' });
        if (response.ok) {
            // Refresh the failures list
            document.getElementById('view-errors-btn').click();
            // Also refresh the status to update the count
            updateStatus();
        } else {
            const data = await response.json();
            alert(`Error: ${data.error || 'Failed to re-queue job'}`);
        }
    } catch (error) {
        console.error('Error re-queuing job:', error);
        alert('An error occurred while trying to re-queue the job.');
    }
}

// Function to delete a stuck job from the failures modal
window.deleteFailedJob = async function(jobId) {
    if (!confirm(`Are you sure you want to permanently delete job ${jobId}?`)) {
        return;
    }
    try {
        const response = await fetch(`/api/jobs/delete/${jobId}`, { method: 'POST' });
        if (response.ok) {
            // Refresh the failures list
            document.getElementById('view-errors-btn').click();
            // Also refresh the status to update the count
            updateStatus();
        } else {
            const data = await response.json();
            alert(`Error: ${data.error || 'Failed to delete job'}`);
        }
    } catch (error) {
        console.error('Error deleting job:', error);
        alert('An error occurred while trying to delete the job.');
    }
}

async function pollScanProgress() {
    if (!isPollingForScan) return;

    try {
        const response = await fetch('/api/scan/progress');
        const data = await response.json();
        const sonarrScanStatusDiv = document.getElementById('sonarr-scan-status');

        if (data.is_running) {
            const elapsed = Math.round((Date.now() - scanStartTime) / 1000);
            const progressPercent = data.total_steps > 0 ? ((data.progress / data.total_steps) * 100).toFixed(1) : 0;
            sonarrScanStatusDiv.innerHTML = `
                <div class="progress" style="height: 20px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-teal" role="progressbar" style="width: ${progressPercent}%" aria-valuenow="${progressPercent}" aria-valuemin="0" aria-valuemax="100">${progressPercent}%</div>
                </div>
                <div class="mt-1">
                    <small class="text-muted">Step ${data.progress} of ${data.total_steps}: ${data.current_step} (Elapsed: ${elapsed}s)</small>
                </div>
            `;
        } else {
            // Scan is finished
            isPollingForScan = false;
            const finalMessage = data.current_step || "Scan finished.";
            sonarrScanStatusDiv.innerHTML = `<div class="alert alert-success">${finalMessage}</div>`;
            revertActiveButton();
            // Refresh job queue to see results of scan
            if (document.querySelector('#jobs-tab.active')) {
                updateJobQueue();
            }
        }
    } catch (error) {
        console.error("Error polling for scan progress:", error);
        isPollingForScan = false;
        revertActiveButton();
    }
}

// Main data update loop. Fetches node status and other data.
async function mainUpdateLoop() {
    await updateStatus();

    // Check which tab is active and update its content if needed
    if (document.querySelector('#history-stats-tab.active')) {
        await updateHistoryAndStats();
    }
    if (document.querySelector('#jobs-tab.active')) {
        await updateJobQueue(jobQueueCurrentPage); // Use the current page for refresh
    }
}

// --- Independent, Non-Blocking Timers ---
// This is the correct pattern to prevent UI freezes.

// 1. A dedicated, lightweight timer for the clock. It does nothing else.
setInterval(() => {
    const clockContainer = document.getElementById('clock-container');
    const timeOptions = {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: !window.Librarrarian.settings.use24HourClock
    };
    const timeString = new Date().toLocaleTimeString([], timeOptions);
    if (clockContainer) clockContainer.innerHTML = `<span class="badge badge-outline-secondary fs-6">Updated: ${timeString}</span>`;
}, 1000); // Runs every second.

// 2. A separate, independent loop for polling scan progress so it doesn't block other updates.
setInterval(() => { if (isPollingForScan) pollScanProgress(); }, 1000); // Polls every second

// Run initial update on page load
updateStatus();

// Set up global node control button event listeners
const startAllNodesBtn = document.getElementById('start-all-nodes-btn');
const stopAllNodesBtn = document.getElementById('stop-all-nodes-btn');
const pauseAllNodesBtn = document.getElementById('pause-all-nodes-btn');

if (startAllNodesBtn) {
    startAllNodesBtn.addEventListener('click', startAllNodes);
}
if (stopAllNodesBtn) {
    stopAllNodesBtn.addEventListener('click', stopAllNodes);
}
if (pauseAllNodesBtn) {
    pauseAllNodesBtn.addEventListener('click', pauseAllNodes);
}

// Initialize all tooltips on the page after the DOM is ready
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
});

// Function to clear all history
const clearHistoryBtn = document.getElementById('clear-history-btn');
if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to permanently clear the entire transcode history? This action cannot be undone.')) {
            return;
        }
        try {
        const response = await fetch('/api/history/clear', { method: 'POST' });
        if (response.ok) {
            // Refresh the history table to show it's empty
            updateHistoryAndStats();
        }
    } catch (error) {
        console.error('Error clearing history:', error);
        alert('An error occurred while trying to clear the history.');
        }
    });
}

// Function to update the job queue
let jobQueueCurrentPage = 1; // Keep track of the current page
let jobQueueFilterType = ''; // Current type filter
let jobQueueFilterStatus = ''; // Current status filter

// Function to load filter options
async function loadJobQueueFilters() {
    try {
        const response = await fetch('/api/jobs/filters');
        const data = await response.json();
        
        const typeSelect = document.getElementById('job-filter-type');
        const statusSelect = document.getElementById('job-filter-status');
        
        if (typeSelect && data.job_types) {
            // Preserve current selection
            const currentType = typeSelect.value;
            typeSelect.innerHTML = '<option value="">All Types</option>' + 
                data.job_types.map(t => `<option value="${t}">${t}</option>`).join('');
            if (currentType) typeSelect.value = currentType;
        }
        
        if (statusSelect && data.statuses) {
            // Preserve current selection
            const currentStatus = statusSelect.value;
            statusSelect.innerHTML = '<option value="">All Statuses</option>' + 
                data.statuses.map(s => `<option value="${s}">${s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ')}</option>`).join('');
            if (currentStatus) statusSelect.value = currentStatus;
        }
    } catch (error) {
        console.error('Error loading job filters:', error);
    }
}

// Helper function to generate action buttons for job queue
function getJobActionButtons(job) {
    if (job.is_stuck) {
        // Stuck job: worker is online but processing higher job IDs
        return `<div class="btn-group btn-group-sm" role="group">
            <button class="btn btn-xs btn-outline-danger" onclick="deleteJob(${job.id})" title="Remove stuck job"><span class="mdi mdi-delete"></span> Remove</button>
            <button class="btn btn-xs btn-outline-primary" onclick="requeueJob(${job.id})" title="Re-add to queue"><span class="mdi mdi-refresh"></span> Re-add</button>
        </div>`;
    }
    if (job.status === 'encoding' && job.minutes_since_heartbeat && job.minutes_since_heartbeat > 10) {
        // Worker offline: show force remove
        return `<button class="btn btn-xs btn-outline-danger" onclick="deleteJob(${job.id})" title="Force Remove Stuck Job">Force Remove</button>`;
    }
    if (['pending', 'awaiting_approval', 'failed'].includes(job.status)) {
        // Regular deletable jobs
        return `<button class="btn btn-xs btn-outline-danger" onclick="deleteJob(${job.id})" title="Delete Job">&times;</button>`;
    }
    return '';
}

async function updateJobQueue(page = 1) {
    jobQueueCurrentPage = page;
    
    // Build query string with filters
    let queryParams = `page=${page}`;
    if (jobQueueFilterType) queryParams += `&type=${encodeURIComponent(jobQueueFilterType)}`;
    if (jobQueueFilterStatus) queryParams += `&status=${encodeURIComponent(jobQueueFilterStatus)}`;
    
    try {
        const response = await fetch(`/api/jobs?${queryParams}`);
        const data = await response.json();
        const tableBody = document.getElementById('job-queue-table-body');
        tableBody.innerHTML = ''; // Clear existing rows

        if (data.db_error) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-danger">Database Error: ${data.db_error}</td></tr>`;
            return;
        }

        if (data.jobs.length === 0) {
            const filterMsg = (jobQueueFilterType || jobQueueFilterStatus) ? 'No jobs match the current filters.' : 'No jobs in the queue.';
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">${filterMsg}</td></tr>`;
            return;
        }

        // Build the entire table HTML at once and set it. This is much more efficient
        // and prevents the "ghost row" rendering bug.
        const rowsHtml = data.jobs.map(job => {
            // Check if job has symlink metadata
            // Parse metadata if it's a string, otherwise use it directly
            const metadata = typeof job.metadata === 'string' ? JSON.parse(job.metadata) : job.metadata;
            const isSymlink = metadata && metadata.is_symlink;
            const symlinkWarning = isSymlink ? escapeHtml(metadata.warning) : '';
            
            return `
            <tr>
                <td>
                    ${(job.job_type === 'cleanup' || job.job_type === 'Rename Job' || isSymlink) && job.status === 'awaiting_approval' ? 
                        `<input type="checkbox" class="form-check-input approval-checkbox" data-job-id="${job.id}">` : 
                        job.id 
                    }
                </td>
                <td style="word-break: break-all;">
                    ${job.filepath}
                    ${isSymlink ? `<br><small class="text-warning"><span class="mdi mdi-alert"></span> ${symlinkWarning}</small>` : ''}
                </td>
                <td><span class="badge badge-outline-info">${job.job_type}</span></td>
                <td>
                    ${job.status === 'encoding' ? 
                        `<span class="badge badge-outline-primary"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Encoding</span>` :
                    job.status === 'awaiting_approval' ?
                        `<span class="badge badge-outline-warning">Awaiting Approval</span>` :
                    job.status === 'pending' ?
                        `<span class="badge badge-outline-secondary">Pending</span>` :
                    job.status === 'failed' ?
                        `<span class="badge badge-outline-danger">Failed</span>` :
                    job.status === 'completed' ?
                        `<span class="badge badge-outline-success">Completed</span>` :
                        `<span class="badge badge-outline-warning">${job.status}</span>`
                    }
                </td>
                <td>${job.assigned_to || 'N/A'}</td>
                <td>${new Date(job.created_at).toLocaleString()}</td>
                <td>${getJobActionButtons(job)}</td>
            </tr>
            `;
        }).join('');
        tableBody.innerHTML = rowsHtml;

        renderJobQueuePagination(data.page, Math.ceil(data.total_jobs / data.per_page));

        // Add event listener for the new "select all" checkbox
        const selectAllCheckbox = document.getElementById('select-all-cleanup');
        selectAllCheckbox.addEventListener('change', (e) => {
            document.querySelectorAll('.approval-checkbox').forEach(checkbox => {
                checkbox.checked = e.target.checked;
            });
        });
        // Uncheck "select all" if any individual box is unchecked
        document.querySelectorAll('.approval-checkbox').forEach(checkbox => checkbox.addEventListener('change', () => { if (!checkbox.checked) selectAllCheckbox.checked = false; }));

    } catch (error) {
        console.error('Error fetching job queue:', error);
        document.getElementById('job-queue-table-body').innerHTML = `<tr><td colspan="6" class="text-danger">Failed to fetch job queue.</td></tr>`;
    }
}

// Function to create cleanup jobs
const createCleanupJobsBtn = document.getElementById('create-cleanup-jobs-btn');
if (createCleanupJobsBtn) {
    createCleanupJobsBtn.addEventListener('click', async () => {
        const statusDiv = document.getElementById('cleanup-status');
        statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm" role="status"></div> Searching for stale files...`;
        const response = await fetch('/api/jobs/create_cleanup', { method: 'POST' });
        if (!response.ok) {
            statusDiv.innerHTML = `<div class="alert alert-danger" role="alert">Error communicating with server.</div>`;
            return;
        }
        const result = await response.json();
        const alertClass = result.success ? 'alert-success' : 'alert-danger';
        statusDiv.innerHTML = `<div class="alert ${alertClass}" role="alert">${result.message || result.error}</div>`;
    });
}

// --- History & Stats Page Logic ---
let fullHistoryData = [];
let historyCurrentPage = 1;
let historyItemsPerPage = 15; // Default to 15
let historySortColumn = 'id';
let historySortDirection = 'desc'; // Default to descending (newest first)

// Combined function to fetch and display stats and history
async function updateHistoryAndStats() {
    const statsCardsContainer = document.getElementById('stats-cards-container');
    const historyBody = document.getElementById('history-table-body');

    try {
        // Get the limit from the dropdown
        const historyLimitSelect = document.getElementById('history-limit-select');
        const limit = historyLimitSelect ? historyLimitSelect.value : '100';
        
        // Fetch both stats and history in parallel
        const [statsResponse, historyResponse] = await Promise.all([
            fetch('/api/stats'),
            fetch(`/api/history?limit=${limit}`)
        ]);

        // Process Stats
        const statsData = await statsResponse.json();
        const reductionPercent = parseFloat(statsData.stats.total_reduction_percent);
        let reductionBorderClass = 'border-success';
        let reductionTextClass = 'text-success';
        if (reductionPercent < 50) {
            reductionBorderClass = 'border-danger';
            reductionTextClass = 'text-danger';
        } else if (reductionPercent < 75) {
            reductionBorderClass = 'border-warning';
            reductionTextClass = 'text-warning';
        }

        statsCardsContainer.innerHTML = `
            <div class="col-md-3"><div class="card"><div class="card-body">
                <h5 class="card-title">${statsData.stats.total_files}</h5><p class="card-text text-muted">Files Encoded</p>
            </div></div></div>
            <div class="col-md-3"><div class="card"><div class="card-body">
                <h5 class="card-title">${statsData.stats.total_new_size_gb} GB</h5><p class="card-text text-muted">New Size</p>
            </div></div></div>
            <div class="col-md-3"><div class="card"><div class="card-body">
                <h5 class="card-title">${statsData.stats.total_original_size_gb} GB</h5><p class="card-text text-muted">Original Size</p>
            </div></div></div>
            <div class="col-md-3"><div class="card ${reductionBorderClass}" style="border-width: 2px;"><div class="card-body">
                <h5 class="card-title ${reductionTextClass}">${statsData.stats.total_reduction_percent}%</h5><p class="card-text text-muted">Average Reduction</p>
            </div></div></div>
        `;

        // Process History
        const historyData = await historyResponse.json();
        fullHistoryData = historyData.history || [];
        renderHistoryTable(); // Render the table with the new data

    } catch (error) {
        console.error("Failed to fetch history/stats:", error);
        statsCardsContainer.innerHTML = '<div class="col-12"><div class="alert alert-danger">Failed to load statistics.</div></div>';
        historyBody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Failed to load history.</td></tr>';
    }
}

// Function to render the history table with search, sorting, and pagination
function renderHistoryTable() {
    const historyBody = document.getElementById('history-table-body');
    const paginationContainer = document.getElementById('history-pagination');
    const searchTerm = document.getElementById('history-search-input').value.toLowerCase();
    const perPageValue = document.getElementById('history-per-page-select').value;

    // Filter data
    let filteredData = fullHistoryData.filter(item => 
        item.filename.toLowerCase().includes(searchTerm) ||
        item.hostname.toLowerCase().includes(searchTerm)
    );

    // Sort data
    filteredData.sort((a, b) => {
        let aVal = a[historySortColumn];
        let bVal = b[historySortColumn];
        
        // Handle numeric sorting for specific columns
        if (historySortColumn === 'id' || historySortColumn === 'original_size' || historySortColumn === 'reduction_percent') {
            aVal = parseFloat(aVal) || 0;
            bVal = parseFloat(bVal) || 0;
        } else {
            // String comparison
            aVal = String(aVal).toLowerCase();
            bVal = String(bVal).toLowerCase();
        }
        
        if (aVal < bVal) return historySortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return historySortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    // Update sort indicators in table headers
    document.querySelectorAll('th[data-sort]').forEach(th => {
        const sortIcon = th.querySelector('.mdi');
        if (th.getAttribute('data-sort') === historySortColumn) {
            sortIcon.className = `mdi mdi-arrow-${historySortDirection === 'asc' ? 'up' : 'down'}`;
        } else {
            sortIcon.className = 'mdi mdi-sort';
        }
    });

    // Determine items per page and paginate data
    let paginatedData;
    let totalPages;
    
    if (perPageValue === 'all' || filteredData.length === 0) {
        // Show all items or handle empty data
        paginatedData = filteredData;
        totalPages = filteredData.length > 0 ? 1 : 0;
        historyCurrentPage = 1;
    } else {
        const effectiveItemsPerPage = parseInt(perPageValue);
        totalPages = Math.ceil(filteredData.length / effectiveItemsPerPage);
        if (historyCurrentPage > totalPages) {
            historyCurrentPage = totalPages || 1;
        }
        const startIndex = (historyCurrentPage - 1) * effectiveItemsPerPage;
        paginatedData = filteredData.slice(startIndex, startIndex + effectiveItemsPerPage);
    }

    // Render table rows
    if (paginatedData.length > 0) {
        historyBody.innerHTML = paginatedData.map(item => `
            <tr>
                <td>${item.id}</td>
                <td style="word-break: break-all;">${item.filename}</td>
                <td>${item.hostname}</td>
                <td><span class="badge badge-outline-secondary">${item.codec}</span></td>
                ${item.status === 'encoding' ? `
                    <td colspan="2" class="text-center"><span class="badge badge-outline-primary">In Progress</span></td>
                ` : `
                    <td>${item.original_size_gb} → ${item.new_size_gb}</td>
                    <td><span class="badge badge-outline-success">${item.reduction_percent}%</span></td>
                `}
                <td>${item.encoded_at}</td>
                <td><button class="btn btn-xs btn-outline-danger" title="Delete this entry">&times;</button></td>
            </tr>
        `).join('');
    } else {
        historyBody.innerHTML = `<tr><td colspan="8" class="text-center">${searchTerm ? 'No matching files found.' : 'No encoded files found.'}</td></tr>`;
    }

    // Render pagination (only if not showing all)
    paginationContainer.innerHTML = '';
    if (totalPages > 1 && perPageValue !== 'all') {
        const pageWindow = 5; // How many pages to show around the current page
        
        // Helper to create a page link
        const createPageLink = (page, text, isDisabled = false, isActive = false) => {
            const li = document.createElement('li');
            li.className = `page-item ${isDisabled ? 'disabled' : ''} ${isActive ? 'active' : ''}`;
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.innerText = text;
            if (!isDisabled) {
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    historyCurrentPage = page;
                    renderHistoryTable();
                });
            }
            li.appendChild(a);
            return li;
        };
        
        // Previous Button
        paginationContainer.appendChild(createPageLink(historyCurrentPage - 1, 'Previous', historyCurrentPage === 1));
        
        // Page numbers
        let startPage = Math.max(1, historyCurrentPage - pageWindow);
        let endPage = Math.min(totalPages, historyCurrentPage + pageWindow);
        
        if (startPage > 1) {
            paginationContainer.appendChild(createPageLink(1, '1'));
            if (startPage > 2) {
                paginationContainer.appendChild(createPageLink(-1, '...', true));
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            paginationContainer.appendChild(createPageLink(i, i.toString(), false, i === historyCurrentPage));
        }
        
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationContainer.appendChild(createPageLink(-1, '...', true));
            }
            paginationContainer.appendChild(createPageLink(totalPages, totalPages.toString()));
        }
        
        // Next Button
        paginationContainer.appendChild(createPageLink(historyCurrentPage + 1, 'Next', historyCurrentPage === totalPages));
    }
}

// Event listener for the search input
const historySearchInput = document.getElementById('history-search-input');
if (historySearchInput) {
    historySearchInput.addEventListener('input', () => {
        historyCurrentPage = 1; // Reset to first page on search
        renderHistoryTable();
    });
}

// Event listener for the per-page select
const historyPerPageSelect = document.getElementById('history-per-page-select');
if (historyPerPageSelect) {
    historyPerPageSelect.addEventListener('change', () => {
        historyCurrentPage = 1; // Reset to first page when changing items per page
        renderHistoryTable();
    });
}

// Event listener for the history limit select
const historyLimitSelect = document.getElementById('history-limit-select');
if (historyLimitSelect) {
    historyLimitSelect.addEventListener('change', () => {
        historyCurrentPage = 1; // Reset to first page when changing limit
        updateHistoryAndStats(); // Re-fetch data from server with new limit
    });
}

// Event listeners for sortable column headers
document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
        const sortColumn = th.getAttribute('data-sort');
        if (historySortColumn === sortColumn) {
            // Toggle sort direction if clicking the same column
            historySortDirection = historySortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            // New column, default to descending for ID/date, ascending for others
            historySortColumn = sortColumn;
            historySortDirection = (sortColumn === 'id' || sortColumn === 'encoded_at') ? 'desc' : 'asc';
        }
        historyCurrentPage = 1; // Reset to first page when sorting
        renderHistoryTable();
    });
});

// --- NEW: Smart Pagination Renderer ---
function renderJobQueuePagination(currentPage, totalPages) {
    const paginationContainer = document.getElementById('job-queue-pagination');
    paginationContainer.innerHTML = '';
    if (totalPages <= 1) return;

    const pageWindow = 5; // How many pages to show around the current page

    // Helper to create a page link
    const createPageLink = (page, text, isDisabled = false, isActive = false) => {
        const li = document.createElement('li');
        li.className = `page-item ${isDisabled ? 'disabled' : ''} ${isActive ? 'active' : ''}`;
        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.innerText = text;
        if (!isDisabled) {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                updateJobQueue(page);
            });
        }
        li.appendChild(a);
        return li;
    };

    // Previous Button
    paginationContainer.appendChild(createPageLink(currentPage - 1, 'Previous', currentPage === 1));

    // Page numbers
    let startPage = Math.max(1, currentPage - pageWindow);
    let endPage = Math.min(totalPages, currentPage + pageWindow);

    if (startPage > 1) {
        paginationContainer.appendChild(createPageLink(1, '1'));
        if (startPage > 2) {
            paginationContainer.appendChild(createPageLink(0, '...', true));
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        paginationContainer.appendChild(createPageLink(i, i.toString(), false, i === currentPage));
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            paginationContainer.appendChild(createPageLink(0, '...', true));
        }
        paginationContainer.appendChild(createPageLink(totalPages, totalPages.toString()));
    }

    // Next Button
    paginationContainer.appendChild(createPageLink(currentPage + 1, 'Next', currentPage === totalPages));
}

// Update history/stats when the tab is shown
const historyStatsTab = document.querySelector('#history-stats-tab');
historyStatsTab.addEventListener('shown.bs.tab', () => {
    updateHistoryAndStats();
});

// Update job queue when its tab is shown
const jobsTab = document.querySelector('#jobs-tab');
jobsTab.addEventListener('shown.bs.tab', () => {
    loadJobQueueFilters();
    updateJobQueue();
});

// Job queue filter event listeners
const jobFilterType = document.getElementById('job-filter-type');
const jobFilterStatus = document.getElementById('job-filter-status');
const jobFilterClear = document.getElementById('job-filter-clear');

if (jobFilterType) {
    jobFilterType.addEventListener('change', () => {
        jobQueueFilterType = jobFilterType.value;
        jobQueueCurrentPage = 1; // Reset to first page when filtering
        updateJobQueue(1);
    });
}

if (jobFilterStatus) {
    jobFilterStatus.addEventListener('change', () => {
        jobQueueFilterStatus = jobFilterStatus.value;
        jobQueueCurrentPage = 1; // Reset to first page when filtering
        updateJobQueue(1);
    });
}

if (jobFilterClear) {
    jobFilterClear.addEventListener('click', () => {
        jobQueueFilterType = '';
        jobQueueFilterStatus = '';
        if (jobFilterType) jobFilterType.value = '';
        if (jobFilterStatus) jobFilterStatus.value = '';
        jobQueueCurrentPage = 1;
        updateJobQueue(1);
    });
}

// Load *arr stats when Tools tab is shown
const toolsTab = document.querySelector('#tools-tab');
if (toolsTab) {
    toolsTab.addEventListener('shown.bs.tab', () => {
        loadArrStats();
    });
}

// Function to load *arr statistics
async function loadArrStats() {
    try {
        const response = await fetch('/api/arr/stats');
        const data = await response.json();
        
        if (!data.success) {
            console.warn('Failed to load *arr stats:', data.error || 'Unknown error');
            return;
        }
        
        if (!data.stats) return;
        
        const stats = data.stats;
        
        // Update Sonarr stats
        if (stats.sonarr && stats.sonarr.enabled) {
            const showsEl = document.getElementById('sonarr-stat-shows');
            const seasonsEl = document.getElementById('sonarr-stat-seasons');
            const episodesEl = document.getElementById('sonarr-stat-episodes');
            if (showsEl) showsEl.textContent = stats.sonarr.shows.toLocaleString();
            if (seasonsEl) seasonsEl.textContent = stats.sonarr.seasons.toLocaleString();
            if (episodesEl) episodesEl.textContent = stats.sonarr.episodes.toLocaleString();
        }
        
        // Update Radarr stats
        if (stats.radarr && stats.radarr.enabled) {
            const moviesEl = document.getElementById('radarr-stat-movies');
            if (moviesEl) moviesEl.textContent = stats.radarr.movies.toLocaleString();
        }
        
        // Update Lidarr stats
        if (stats.lidarr && stats.lidarr.enabled) {
            const artistsEl = document.getElementById('lidarr-stat-artists');
            const albumsEl = document.getElementById('lidarr-stat-albums');
            const tracksEl = document.getElementById('lidarr-stat-tracks');
            if (artistsEl) artistsEl.textContent = stats.lidarr.artists.toLocaleString();
            if (albumsEl) albumsEl.textContent = stats.lidarr.albums.toLocaleString();
            if (tracksEl) tracksEl.textContent = stats.lidarr.tracks.toLocaleString();
        }
    } catch (error) {
        console.error('Error loading *arr stats:', error);
    }
}

// Start the main update loop
setInterval(mainUpdateLoop, 5000);

// Function to send the 'start' command to a node
async function startNode(hostname) {
    try {
        const response = await fetch(`/api/nodes/${hostname}/start`, {
            method: 'POST',
        });
        const result = await response.json();

        if (result.success) {
            // The command was successful, just refresh the UI.
            // Immediately refresh the status to show the node has started
            updateStatus();
        } else {
            // If the server reported an error, show it.
            alert(`Failed to send start command to ${hostname}: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting node:', error);
        alert(`An error occurred while trying to start ${hostname}.`);
    }
}

// Function to send the 'stop' command to a node
async function stopNode(hostname) {
    if (!confirm(`Are you sure you want to stop the worker on '${hostname}'? It will finish its current file and then go idle.`)) {
        return;
    }
    try {
        const response = await fetch(`/api/nodes/${hostname}/stop`, {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            updateStatus(); // Refresh UI to show the node going idle
        } else {
            alert(`Failed to send stop command to ${hostname}: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error stopping node:', error);
    }
}

// Function to send 'pause' or 'resume' command
async function pauseResumeNode(hostname, currentCommand) {
    const action = currentCommand === 'paused' ? 'resume' : 'pause';
    try {
        const response = await fetch(`/api/nodes/${hostname}/${action}`, {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            updateStatus(); // Refresh UI
        } else {
            alert(`Failed to ${action} node ${hostname}: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error(`Error ${action}ing node:`, error);
    }
}

// Global control functions for all nodes
async function startAllNodes() {
    try {
        const response = await fetch('/api/nodes/start-all', {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            updateStatus(); // Refresh UI to show nodes starting
            if (result.count === 0) {
                alert('No idle nodes to start.');
            }
        } else {
            alert(`Failed to start all nodes: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error starting all nodes:', error);
        alert('An error occurred while trying to start all nodes.');
    }
}

async function stopAllNodes() {
    if (!confirm('Are you sure you want to stop all running workers? They will finish their current files and then go idle.')) {
        return;
    }
    try {
        const response = await fetch('/api/nodes/stop-all', {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            updateStatus(); // Refresh UI to show nodes stopping
            if (result.count === 0) {
                alert('No running nodes to stop.');
            }
        } else {
            alert(`Failed to stop all nodes: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error stopping all nodes:', error);
        alert('An error occurred while trying to stop all nodes.');
    }
}

async function pauseAllNodes() {
    try {
        const response = await fetch('/api/nodes/pause-all', {
            method: 'POST',
        });
        const result = await response.json();
        if (result.success) {
            updateStatus(); // Refresh UI to show nodes pausing
            if (result.count === 0) {
                alert('No running nodes to pause.');
            }
        } else {
            alert(`Failed to pause all nodes: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error pausing all nodes:', error);
        alert('An error occurred while trying to pause all nodes.');
    }
}

// Placeholder for future per-node options
let nodeOptionsModal = null;
function showNodeOptions(hostname) {
    if (!nodeOptionsModal) {
        nodeOptionsModal = new bootstrap.Modal(document.getElementById('nodeOptionsModal'));
    }
    document.getElementById('nodeOptionsModalTitle').innerText = `Options for ${hostname}`;
    const quitBtn = document.getElementById('quit-node-btn');
    // Re-assign the onclick event to the button for the specific hostname
    quitBtn.onclick = () => quitNode(hostname);
    nodeOptionsModal.show();
}

document.addEventListener('DOMContentLoaded', () => {
    const enableSonarrLink = document.getElementById('enable-sonarr-link');
    if (enableSonarrLink) {
        enableSonarrLink.addEventListener('click', (e) => {
            e.preventDefault();
            // Use bootstrap's API to show the main options tab
            const optionsTabTrigger = document.getElementById('options-tab');
            const tab = new bootstrap.Tab(optionsTabTrigger);
            tab.show();

            // Once the main tab is shown, show the sonarr sub-tab
            optionsTabTrigger.addEventListener('shown.bs.tab', () => {
                const sonarrSubTabTrigger = document.getElementById('sonarr-integration-tab');
                const subTab = new bootstrap.Tab(sonarrSubTabTrigger);
                subTab.show();
            }, { once: true }); // Use 'once' so this listener only fires once
        });
    }

    const enableRadarrLink = document.getElementById('enable-radarr-link');
    if (enableRadarrLink) {
        enableRadarrLink.addEventListener('click', (e) => {
            e.preventDefault();
            // Use bootstrap's API to show the main options tab
            const optionsTabTrigger = document.getElementById('options-tab');
            const tab = new bootstrap.Tab(optionsTabTrigger);
            tab.show();

            // Once the main tab is shown, show the radarr sub-tab
            optionsTabTrigger.addEventListener('shown.bs.tab', () => {
                const radarrSubTabTrigger = document.getElementById('radarr-integration-tab');
                const subTab = new bootstrap.Tab(radarrSubTabTrigger);
                subTab.show();
            }, { once: true }); // Use 'once' so this listener only fires once
        });
    }

    const enableLidarrLink = document.getElementById('enable-lidarr-link');
    if (enableLidarrLink) {
        enableLidarrLink.addEventListener('click', (e) => {
            e.preventDefault();
            // Use bootstrap's API to show the main options tab
            const optionsTabTrigger = document.getElementById('options-tab');
            const tab = new bootstrap.Tab(optionsTabTrigger);
            tab.show();

            // Once the main tab is shown, show the lidarr sub-tab
            optionsTabTrigger.addEventListener('shown.bs.tab', () => {
                const lidarrSubTabTrigger = document.getElementById('lidarr-integration-tab');
                const subTab = new bootstrap.Tab(lidarrSubTabTrigger);
                subTab.show();
            }, { once: true }); // Use 'once' so this listener only fires once
        });
    }

    const mainTabs = document.querySelector('#mainTabs');
    const advancedSwitchContainer = document.querySelector('#advanced-switch-container');
    const globalNodeControls = document.querySelector('#global-node-controls');

    if (mainTabs) {
        mainTabs.addEventListener('shown.bs.tab', function (event) {
            // Show/hide advanced switch container based on tab
            if (advancedSwitchContainer) {
                if (event.target.id === 'options-tab') {
                    advancedSwitchContainer.classList.remove('d-none');
                } else {
                    advancedSwitchContainer.classList.add('d-none');
                }
            }
            
            // Show/hide global node controls based on tab
            if (globalNodeControls) {
                if (event.target.id === 'nodes-tab') {
                    globalNodeControls.classList.remove('d-none');
                } else {
                    globalNodeControls.classList.add('d-none');
                }
            }
        });
    }

    const showAdvancedSwitch = document.getElementById('show-advanced-transcoding');
    const advancedSection = document.getElementById('advanced-transcoding-section');

    if (showAdvancedSwitch && advancedSection) {
        showAdvancedSwitch.addEventListener('change', (event) => {
            if (event.target.checked) {
                advancedSection.classList.remove('d-none');
            } else {
                advancedSection.classList.add('d-none');
            }
        });
    }

    const clockToggle = document.getElementById('clock-24hr');
    if (clockToggle) {
        clockToggle.addEventListener('change', (event) => {
            window.Librarrarian.settings.use24HourClock = event.target.checked;
        });
    }

    // Function to send the 'quit' command to a node
    window.quitNode = async function(hostname) {
        if (!confirm(`Are you sure you want to QUIT the worker on '${hostname}'? This will stop the process immediately. The container will likely restart based on Docker policy.`)) {
            return;
        }
        try {
            const response = await fetch(`/api/nodes/${hostname}/quit`, {
                method: 'POST',
            });
            const result = await response.json();
            if (result.success) {
                updateStatus(); // Refresh UI to show the node disappearing
            } else {
                alert(`Failed to send quit command to ${hostname}: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error quitting node:', error);
        }
    }

    // Slider logic
    const delaySlider = document.getElementById('rescan_delay_minutes');
    if (delaySlider) {
        const delayValue = document.getElementById('delay-value');
        delaySlider.addEventListener('input', (event) => {
            delayValue.textContent = `${event.target.value} min`;
        });
    }

    // Function to activate a tab based on URL hash
    function activateTabFromHash() {
        const hash = window.location.hash;
        if (hash) {
            const triggerEl = document.querySelector(`button[data-bs-target="${hash}"]`);
            if (triggerEl) {
                const tab = new bootstrap.Tab(triggerEl);
                tab.show();
                // If loading directly to Tools tab, load stats immediately
                if (hash === '#tools-tab-pane') {
                    loadArrStats();
                }
            }
        } else {
            const defaultTab = document.getElementById('nodes-tab');
            if (defaultTab) {
                const tab = new bootstrap.Tab(defaultTab);
                tab.show();
            }
        }
    }
    activateTabFromHash();

    // --- Plex Authentication Logic ---
    const plexLoginBtn = document.getElementById('plex-login-btn');
    const plexModifyBtn = document.getElementById('plex-modify-btn');
    const plexSignInBtn = document.getElementById('plex-signin-btn');
    const plexUpdateBtn = document.getElementById('plex-update-btn');
    const plexModalUnlinkBtn = document.getElementById('plex-modal-unlink-btn');

    // Function to set Plex modal to link mode
    function setPlexModalLinkMode() {
        document.getElementById('plexLoginModalLabel').textContent = 'Link Plex Account';
        document.getElementById('plex-modal-description').textContent = 'Enter your Plex server URL and Plex.tv credentials. This is a one-time login to retrieve an authentication token. Your password is not stored.';
        
        // Reset to credentials mode by default
        const credentialsRadio = document.getElementById('plex-auth-credentials');
        if (credentialsRadio) {
            credentialsRadio.checked = true;
            document.getElementById('plex-credentials-group').style.display = 'block';
            document.getElementById('plex-token-group').style.display = 'none';
        }
        
        document.getElementById('plex-signin-btn').style.display = 'inline-block';
        document.getElementById('plex-save-token-btn').style.display = 'none';
        document.getElementById('plex-update-btn').style.display = 'none';
        document.getElementById('plex-modal-unlink-btn').style.display = 'none';
        document.getElementById('plex-modal-url').value = '';
        document.getElementById('plex-username').value = '';
        document.getElementById('plex-password').value = '';
        document.getElementById('plex-token-input').value = '';
        document.getElementById('plex-login-status').innerHTML = '';
    }

    // Function to set Plex modal to modify mode
    function setPlexModalModifyMode() {
        document.getElementById('plexLoginModalLabel').textContent = 'Modify Plex Configuration';
        document.getElementById('plex-modal-description').textContent = 'Update your Plex server URL. Your existing authentication will be verified with the new server.';
        
        // Hide authentication method toggle and all auth groups in modify mode
        document.getElementById('plex-credentials-group').style.display = 'none';
        document.getElementById('plex-token-group').style.display = 'none';
        
        document.getElementById('plex-signin-btn').style.display = 'none';
        document.getElementById('plex-save-token-btn').style.display = 'none';
        document.getElementById('plex-update-btn').style.display = 'inline-block';
        document.getElementById('plex-modal-unlink-btn').style.display = 'inline-block';
        
        // Pre-fill with current URL
        document.getElementById('plex-modal-url').value = window.Librarrarian.settings.plexUrl || '';
        document.getElementById('plex-login-status').innerHTML = '';
    }

    if (plexLoginBtn) {
        plexLoginBtn.addEventListener('click', () => {
            setPlexModalLinkMode();
            const loginModal = new bootstrap.Modal(document.getElementById('plexLoginModal'));
            loginModal.show();
        });
    }

    if (plexModifyBtn) {
        plexModifyBtn.addEventListener('click', () => {
            setPlexModalModifyMode();
            const loginModal = new bootstrap.Modal(document.getElementById('plexLoginModal'));
            loginModal.show();
        });
    }

    if (plexSignInBtn) {
        plexSignInBtn.addEventListener('click', async () => {
            const usernameInput = document.getElementById('plex-username');
            const passwordInput = document.getElementById('plex-password');
            const urlInput = document.getElementById('plex-modal-url');
            const statusDiv = document.getElementById('plex-login-status');
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Signing in...`;

            const response = await fetch('/api/plex/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username: usernameInput.value, 
                    password: passwordInput.value,
                    plex_url: urlInput.value
                })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => {
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('plexLoginModal'));
                    if (loginModal) loginModal.hide();
                    window.location.hash = '#options-tab-pane';
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    if (plexUpdateBtn) {
        plexUpdateBtn.addEventListener('click', async () => {
            const urlInput = document.getElementById('plex-modal-url');
            const statusDiv = document.getElementById('plex-login-status');
            
            if (!urlInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Plex Server URL.</div>`;
                return;
            }
            
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Updating URL...`;

            const response = await fetch('/api/plex/update-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ plex_url: urlInput.value })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => {
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('plexLoginModal'));
                    if (loginModal) loginModal.hide();
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    const plexTestConnectionBtn = document.getElementById('plex-test-connection-btn');
    if (plexTestConnectionBtn) {
        plexTestConnectionBtn.addEventListener('click', async () => {
            const urlInput = document.getElementById('plex-modal-url');
            const statusDiv = document.getElementById('plex-login-status');
            
            if (!urlInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Plex Server URL first.</div>`;
                return;
            }
            
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Testing connection...`;

            const response = await fetch('/api/plex/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ plex_url: urlInput.value })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    if (plexModalUnlinkBtn) {
        plexModalUnlinkBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to unlink your Plex account? This will remove both the authentication token and server URL.')) {
                const statusDiv = document.getElementById('plex-login-status');
                statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Unlinking...`;
                await fetch('/api/plex/logout', { method: 'POST' });
                window.location.reload();
            }
        });
    }

    // Handle Plex authentication method toggle
    const plexAuthCredentialsRadio = document.getElementById('plex-auth-credentials');
    const plexAuthTokenRadio = document.getElementById('plex-auth-token');
    const plexCredentialsGroup = document.getElementById('plex-credentials-group');
    const plexTokenGroup = document.getElementById('plex-token-group');
    const plexSaveTokenBtn = document.getElementById('plex-save-token-btn');

    if (plexAuthCredentialsRadio && plexAuthTokenRadio) {
        plexAuthCredentialsRadio.addEventListener('change', () => {
            if (plexAuthCredentialsRadio.checked) {
                plexCredentialsGroup.style.display = 'block';
                plexTokenGroup.style.display = 'none';
                plexSignInBtn.style.display = 'inline-block';
                plexSaveTokenBtn.style.display = 'none';
            }
        });

        plexAuthTokenRadio.addEventListener('change', () => {
            if (plexAuthTokenRadio.checked) {
                plexCredentialsGroup.style.display = 'none';
                plexTokenGroup.style.display = 'block';
                plexSignInBtn.style.display = 'none';
                plexSaveTokenBtn.style.display = 'inline-block';
            }
        });
    }

    // Handle Save Token button
    if (plexSaveTokenBtn) {
        plexSaveTokenBtn.addEventListener('click', async () => {
            const tokenInput = document.getElementById('plex-token-input');
            const urlInput = document.getElementById('plex-modal-url');
            const statusDiv = document.getElementById('plex-login-status');

            if (!tokenInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Plex token.</div>`;
                return;
            }

            if (!urlInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Plex Server URL.</div>`;
                return;
            }

            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Saving token...`;

            const response = await fetch('/api/plex/save-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    token: tokenInput.value,
                    plex_url: urlInput.value
                })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => {
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('plexLoginModal'));
                    if (loginModal) loginModal.hide();
                    window.location.hash = '#options-tab-pane';
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    // --- Jellyfin Authentication Logic ---
    const jellyfinLoginBtn = document.getElementById('jellyfin-login-btn');
    const jellyfinModifyBtn = document.getElementById('jellyfin-modify-btn');
    const jellyfinSignInBtn = document.getElementById('jellyfin-signin-btn');
    const jellyfinUpdateBtn = document.getElementById('jellyfin-update-btn');
    const jellyfinModalUnlinkBtn = document.getElementById('jellyfin-modal-unlink-btn');

    // Function to set Jellyfin modal to link mode
    function setJellyfinModalLinkMode() {
        document.getElementById('jellyfinLoginModalLabel').textContent = 'Link Jellyfin Server';
        document.getElementById('jellyfin-modal-description').textContent = 'Enter your Jellyfin server URL and API key to link your server. You can find your API key in Jellyfin\'s Dashboard under Advanced → API Keys.';
        document.getElementById('jellyfin-api-key-group').style.display = 'block';
        document.getElementById('jellyfin-signin-btn').style.display = 'inline-block';
        document.getElementById('jellyfin-update-btn').style.display = 'none';
        document.getElementById('jellyfin-modal-unlink-btn').style.display = 'none';
        document.getElementById('jellyfin-host').value = '';
        document.getElementById('jellyfin-api-key').value = '';
        document.getElementById('jellyfin-login-status').innerHTML = '';
    }

    // Function to set Jellyfin modal to modify mode
    function setJellyfinModalModifyMode() {
        document.getElementById('jellyfinLoginModalLabel').textContent = 'Modify Jellyfin Configuration';
        document.getElementById('jellyfin-modal-description').textContent = 'Update your Jellyfin server URL. To change the API key, enter a new one.';
        document.getElementById('jellyfin-api-key-group').style.display = 'block';
        document.getElementById('jellyfin-signin-btn').style.display = 'none';
        document.getElementById('jellyfin-update-btn').style.display = 'inline-block';
        document.getElementById('jellyfin-modal-unlink-btn').style.display = 'inline-block';
        // Pre-fill with current values
        document.getElementById('jellyfin-host').value = window.Librarrarian.settings.jellyfinHost || '';
        document.getElementById('jellyfin-api-key').value = ''; // Don't pre-fill API key for security
        document.getElementById('jellyfin-api-key').placeholder = '(Optional) Enter new API key';
        document.getElementById('jellyfin-login-status').innerHTML = '';
    }

    if (jellyfinLoginBtn) {
        jellyfinLoginBtn.addEventListener('click', () => {
            setJellyfinModalLinkMode();
            const loginModal = new bootstrap.Modal(document.getElementById('jellyfinLoginModal'));
            loginModal.show();
        });
    }

    if (jellyfinModifyBtn) {
        jellyfinModifyBtn.addEventListener('click', () => {
            setJellyfinModalModifyMode();
            const loginModal = new bootstrap.Modal(document.getElementById('jellyfinLoginModal'));
            loginModal.show();
        });
    }

    if (jellyfinSignInBtn) {
        jellyfinSignInBtn.addEventListener('click', async () => {
            const hostInput = document.getElementById('jellyfin-host');
            const apiKeyInput = document.getElementById('jellyfin-api-key');
            const statusDiv = document.getElementById('jellyfin-login-status');
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Connecting to server...`;

            const response = await fetch('/api/jellyfin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    host: hostInput.value, 
                    api_key: apiKeyInput.value
                })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => {
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('jellyfinLoginModal'));
                    if (loginModal) loginModal.hide();
                    window.location.hash = '#options-tab-pane';
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    if (jellyfinUpdateBtn) {
        jellyfinUpdateBtn.addEventListener('click', async () => {
            const hostInput = document.getElementById('jellyfin-host');
            const apiKeyInput = document.getElementById('jellyfin-api-key');
            const statusDiv = document.getElementById('jellyfin-login-status');
            
            if (!hostInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Jellyfin Server URL.</div>`;
                return;
            }
            
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Updating configuration...`;

            // Build request body - only include API key if provided
            const requestBody = { host: hostInput.value };
            if (apiKeyInput.value) {
                requestBody.api_key = apiKeyInput.value;
            }

            const response = await fetch('/api/jellyfin/update-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => {
                    const loginModal = bootstrap.Modal.getInstance(document.getElementById('jellyfinLoginModal'));
                    if (loginModal) loginModal.hide();
                    window.location.reload();
                }, 2000);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    const jellyfinTestConnectionBtn = document.getElementById('jellyfin-test-connection-btn');
    if (jellyfinTestConnectionBtn) {
        jellyfinTestConnectionBtn.addEventListener('click', async () => {
            const hostInput = document.getElementById('jellyfin-host');
            const apiKeyInput = document.getElementById('jellyfin-api-key');
            const statusDiv = document.getElementById('jellyfin-login-status');
            
            if (!hostInput.value) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter a Jellyfin Server URL first.</div>`;
                return;
            }
            
            // Check if we have an API key (either entered or saved)
            const hasApiKey = apiKeyInput.value || window.Librarrarian.settings.jellyfinApiKey;
            if (!hasApiKey) {
                statusDiv.innerHTML = `<div class="alert alert-warning">Please enter an API key first.</div>`;
                return;
            }
            
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Testing connection...`;

            const response = await fetch('/api/jellyfin/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    host: hostInput.value,
                    api_key: apiKeyInput.value  // Send input value (may be empty); backend uses saved key if empty
                })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    if (jellyfinModalUnlinkBtn) {
        jellyfinModalUnlinkBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to unlink your Jellyfin server? This will remove both the API key and server URL.')) {
                const statusDiv = document.getElementById('jellyfin-login-status');
                statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Unlinking...`;
                await fetch('/api/jellyfin/logout', { method: 'POST' });
                window.location.reload();
            }
        });
    }

    // --- Show/Hide Logic ---
    // Set up visibility toggles BEFORE loading functions are called
    // Items are considered "ignored" when their media type dropdown is set to "none"
    function setupShowIgnoredToggle(toggleId, listContainerId) {
        const toggle = document.getElementById(toggleId);
        const listContainer = document.getElementById(listContainerId);

        if (!toggle || !listContainer) {
            console.warn(`Could not find toggle (${toggleId}) or container (${listContainerId}) for show/hide logic`);
            return () => {};
        }

        const applyVisibility = () => {
            const showIgnored = toggle.checked;
            listContainer.querySelectorAll('.media-source-item').forEach(item => {
                // Check if the media type dropdown is set to "none" (ignored)
                const typeDropdown = item.querySelector('select');
                const isIgnored = typeDropdown ? typeDropdown.value === 'none' : false;
                
                if (isIgnored && !showIgnored) {
                    // Use Bootstrap's d-none class to hide, as it has !important
                    // which overrides the d-flex class's display: flex !important
                    item.classList.add('d-none');
                } else {
                    item.classList.remove('d-none');
                }
            });
        };

        // Listen for toggle changes
        toggle.addEventListener('change', applyVisibility);

        // Listen for dropdown changes within the list (using event delegation)
        listContainer.addEventListener('change', (e) => {
            if (e.target.matches('select')) {
                applyVisibility();
            }
        });

        // Use MutationObserver to apply visibility when content is dynamically loaded
        const observer = new MutationObserver(() => {
            applyVisibility();
        });
        observer.observe(listContainer, { childList: true, subtree: true });

        // Return the function so it can be called manually if needed
        return applyVisibility;
    }
    const applyPlexVisibility = setupShowIgnoredToggle('plex-show-hidden-toggle', 'plex-libraries-list');
    const applyJellyfinVisibility = setupShowIgnoredToggle('jellyfin-show-hidden-toggle', 'jellyfin-libraries-list');
    const applyInternalVisibility = setupShowIgnoredToggle('internal-show-hidden-toggle', 'internal-folders-list');
    const applyCombinedVisibility = setupShowIgnoredToggle('combined-show-hidden-toggle', 'combined-libraries-list');

    // --- Dynamic Plex Library Loading ---
    async function loadPlexLibraries() {
        const container = document.getElementById('plex-libraries-list');
        const mediaTypes = {
            'movie': 'Movie',
            'show': 'TV Show',
            'music': 'Music',
            'other': 'Other Videos',
            'none': 'None (Ignore)'
        };
        const createDropdown = (name, plexType, selectedType) => {
            // Default to music for 'artist', other for 'photo', otherwise use the saved type.
            const finalSelectedType = selectedType || (plexType === 'artist' ? 'music' : (plexType === 'photo' ? 'other' : plexType));
            const options = Object.entries(mediaTypes).map(([key, value]) => `<option value="${key}" ${finalSelectedType === key ? 'selected' : ''}>${value}</option>`).join('');
            return `<select class="form-select form-select-sm" name="${name}" style="width: 150px;">${options}</select>`;
        };

        // Use the settings rendered directly into the page by the server.
        // This completely avoids any race conditions with the DOM.
        const hasToken = window.Librarrarian.settings.plexToken !== "";

        if (!hasToken) {
            container.innerHTML = `<p class="text-muted">Link your Plex account to see libraries.</p>`;
            return;
        }

        const response = await fetch('/api/plex/libraries');
        const data = await response.json();
        const currentLibs = window.Librarrarian.settings.plexLibraries;

        // Check if multi-server is enabled and primary server is Plex
        const multiServerEnabled = document.getElementById('enable_multi_server')?.checked;
        const primaryServer = document.querySelector('input[name="primary_media_server"]:checked')?.value;
        const showJellyfinLink = multiServerEnabled && primaryServer === 'plex';

        // Fetch Jellyfin libraries if needed for linking
        let jellyfinLibs = [];
        if (showJellyfinLink) {
            try {
                const jellyfinResponse = await fetch('/api/jellyfin/libraries');
                const jellyfinData = await jellyfinResponse.json();
                if (jellyfinData.libraries) {
                    jellyfinLibs = jellyfinData.libraries;
                }
            } catch (e) {
                console.log('Could not fetch Jellyfin libraries for linking');
            }
        }

        const createJellyfinLinkDropdown = (plexLibName, selectedLibrary = '') => {
            const escapedLibName = escapeHtml(plexLibName);
            const hasJellyfinAuth = window.Librarrarian.settings.jellyfinApiKey !== "";
            
            if (!hasJellyfinAuth) {
                return `<span class="text-muted small">Jellyfin not linked</span>`;
            }
            
            const options = ['<option value="">-- Ignore --</option>']
                .concat(jellyfinLibs.map(jLib => {
                    const escapedTitle = escapeHtml(jLib.title);
                    const selected = jLib.title === selectedLibrary ? 'selected' : '';
                    return `<option value="${escapedTitle}" ${selected}>${escapedTitle}</option>`;
                }))
                .join('');
            return `<select class="form-select form-select-sm" name="link_plex_${escapedLibName}" style="width: 180px;">${options}</select>`;
        };

        if (data.libraries && data.libraries.length > 0) {
            container.innerHTML = data.libraries.map(lib => {
                const escapedTitle = escapeHtml(lib.title);
                const escapedKey = escapeHtml(lib.key);
                return `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <div class="form-check" style="min-width: 150px;">
                        <input class="form-check-input" type="checkbox" name="plex_libraries" value="${escapedTitle}" id="lib-${escapedKey}" ${currentLibs.includes(lib.title) ? 'checked' : ''}>
                        <label class="form-check-label" for="lib-${escapedKey}">${escapedTitle}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center gap-2">
                        ${createDropdown(`type_plex_${escapedTitle}`, lib.plex_type, lib.type)}
                        ${showJellyfinLink ? '<span class="badge badge-outline-purple">Jellyfin</span>' : ''}
                        ${showJellyfinLink ? createJellyfinLinkDropdown(lib.title, lib.linked_library || '') : ''}
                    </div>
                </div>
            `;
            }).join('');
        } else {
            container.innerHTML = `<p class="text-muted">${data.error || 'No video libraries found.'}</p>`;
        }

        // Apply the initial visibility based on the toggle's state
        if (typeof applyPlexVisibility === 'function') {
            applyPlexVisibility();
        }
    }
    // Always load Plex libraries on page load (the function checks for token internally)
    if (document.getElementById('plex-libraries-container')) {
        loadPlexLibraries();
    }

    // --- Dynamic Jellyfin Library Loading ---
    async function loadJellyfinLibraries() {
        const container = document.getElementById('jellyfin-libraries-list');
        const mediaTypes = {
            'movie': 'Movie',
            'show': 'TV Show',
            'music': 'Music',
            'other': 'Other Videos',
            'none': 'None (Ignore)'
        };
        const createDropdown = (name, selectedType) => {
            const options = Object.entries(mediaTypes).map(([key, value]) => `<option value="${key}" ${selectedType === key ? 'selected' : ''}>${value}</option>`).join('');
            return `<select class="form-select form-select-sm" name="${name}" style="width: 150px;">${options}</select>`;
        };

        const hasApiKey = window.Librarrarian.settings.jellyfinApiKey !== "";

        if (!hasApiKey) {
            container.innerHTML = `<p class="text-muted">Link your Jellyfin server to see libraries.</p>`;
            return;
        }

        container.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Loading libraries...';

        const response = await fetch('/api/jellyfin/libraries');
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<p class="text-muted">${data.error}</p>`;
            return;
        }

        // Check if multi-server is enabled and primary server is Jellyfin
        const multiServerEnabled = document.getElementById('enable_multi_server')?.checked;
        const primaryServer = document.querySelector('input[name="primary_media_server"]:checked')?.value;
        const showPlexLink = multiServerEnabled && primaryServer === 'jellyfin';

        // Fetch Plex libraries if needed for linking
        let plexLibs = [];
        if (showPlexLink) {
            try {
                const plexResponse = await fetch('/api/plex/libraries');
                const plexData = await plexResponse.json();
                if (plexData.libraries) {
                    plexLibs = plexData.libraries;
                }
            } catch (e) {
                console.log('Could not fetch Plex libraries for linking');
            }
        }

        const createPlexLinkDropdown = (jellyfinLibName, selectedLibrary = '') => {
            const escapedLibName = escapeHtml(jellyfinLibName);
            const hasPlexAuth = window.Librarrarian.settings.plexToken !== "";
            
            if (!hasPlexAuth) {
                return `<span class="text-muted small">Plex not linked</span>`;
            }
            
            const options = ['<option value="">-- Ignore --</option>']
                .concat(plexLibs.map(pLib => {
                    const escapedTitle = escapeHtml(pLib.title);
                    const selected = pLib.title === selectedLibrary ? 'selected' : '';
                    return `<option value="${escapedTitle}" ${selected}>${escapedTitle}</option>`;
                }))
                .join('');
            return `<select class="form-select form-select-sm" name="link_jellyfin_${escapedLibName}" style="width: 180px;">${options}</select>`;
        };

        const currentLibs = window.Librarrarian.settings.jellyfinLibraries || [];

        if (data.libraries && data.libraries.length > 0) {
            container.innerHTML = data.libraries.map(lib => {
                const escapedTitle = escapeHtml(lib.title);
                const escapedId = escapeHtml(lib.id || lib.title);
                return `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <div class="form-check" style="min-width: 150px;">
                        <input class="form-check-input" type="checkbox" name="jellyfin_libraries" value="${escapedTitle}" id="jlib-${escapedId}" ${currentLibs.includes(lib.title) ? 'checked' : ''}>
                        <label class="form-check-label" for="jlib-${escapedId}">${escapedTitle}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center gap-2">
                        ${createDropdown(`type_jellyfin_${escapedTitle}`, lib.type)}
                        ${showPlexLink ? '<span class="badge badge-outline-warning">Plex</span>' : ''}
                        ${showPlexLink ? createPlexLinkDropdown(lib.title, lib.linked_library || '') : ''}
                    </div>
                </div>
            `;
            }).join('');
        } else {
            container.innerHTML = '<p class="text-muted">No libraries found.</p>';
        }

        // Apply the initial visibility based on the toggle's state
        if (typeof applyJellyfinVisibility === 'function') {
            applyJellyfinVisibility();
        }
    }
    // Always load Jellyfin libraries on page load (the function checks for API key internally)
    const jellyfinLibrariesContainer = document.getElementById('jellyfin-libraries-container');
    if (jellyfinLibrariesContainer) {
        loadJellyfinLibraries();
    }

    // --- Combined Libraries Loading (for Multi-Server Sync Mode) ---
    async function loadCombinedLibraries() {
        const container = document.getElementById('combined-libraries-list');
        const primaryServer = document.querySelector('input[name="primary_media_server"]:checked')?.value;
        
        const mediaTypes = {
            'movie': 'Movie',
            'show': 'TV Show',
            'music': 'Music',
            'other': 'Other Videos',
            'none': 'None (Ignore)'
        };
        
        const createDropdown = (name, selectedType) => {
            const options = Object.entries(mediaTypes).map(([key, value]) => `<option value="${key}" ${selectedType === key ? 'selected' : ''}>${value}</option>`).join('');
            return `<select class="form-select form-select-sm" name="${name}" style="width: 150px;">${options}</select>`;
        };
        
        container.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Loading libraries...';
        
        // Fetch both Plex and Jellyfin libraries
        let plexLibraries = [];
        let jellyfinLibraries = [];
        
        const hasPlexAuth = window.Librarrarian.settings.plexToken !== "";
        const hasJellyfinAuth = window.Librarrarian.settings.jellyfinApiKey !== "";
        
        // Fetch Plex libraries
        let plexError = null;
        if (hasPlexAuth) {
            try {
                const plexResponse = await fetch('/api/plex/libraries');
                const plexData = await plexResponse.json();
                if (plexData.libraries) {
                    plexLibraries = plexData.libraries;
                } else if (plexData.error) {
                    plexError = plexData.error;
                }
            } catch (e) {
                console.log('Could not fetch Plex libraries:', e);
                plexError = 'Failed to communicate with server.';
            }
        }
        
        // Fetch Jellyfin libraries
        let jellyfinError = null;
        if (hasJellyfinAuth) {
            try {
                const jellyfinResponse = await fetch('/api/jellyfin/libraries');
                const jellyfinData = await jellyfinResponse.json();
                if (jellyfinData.libraries) {
                    jellyfinLibraries = jellyfinData.libraries;
                } else if (jellyfinData.error) {
                    jellyfinError = jellyfinData.error;
                }
            } catch (e) {
                console.log('Could not fetch Jellyfin libraries:', e);
                jellyfinError = 'Failed to communicate with server.';
            }
        }
        
        // Create linking dropdown helper functions
        const createJellyfinLinkDropdown = (plexLibName, selectedLibrary = '') => {
            const escapedLibName = escapeHtml(plexLibName);
            if (!hasJellyfinAuth) {
                return `<span class="text-muted small">Jellyfin not linked</span>`;
            }
            const options = ['<option value="">-- Ignore --</option>']
                .concat(jellyfinLibraries.map(jLib => {
                    const escapedTitle = escapeHtml(jLib.title);
                    const selected = jLib.title === selectedLibrary ? 'selected' : '';
                    return `<option value="${escapedTitle}" ${selected}>${escapedTitle}</option>`;
                }))
                .join('');
            return `<select class="form-select form-select-sm" name="link_plex_${escapedLibName}" style="width: 180px;">${options}</select>`;
        };
        
        const createPlexLinkDropdown = (jellyfinLibName, selectedLibrary = '') => {
            const escapedLibName = escapeHtml(jellyfinLibName);
            if (!hasPlexAuth) {
                return `<span class="text-muted small">Plex not linked</span>`;
            }
            const options = ['<option value="">-- Ignore --</option>']
                .concat(plexLibraries.map(pLib => {
                    const escapedTitle = escapeHtml(pLib.title);
                    const selected = pLib.title === selectedLibrary ? 'selected' : '';
                    return `<option value="${escapedTitle}" ${selected}>${escapedTitle}</option>`;
                }))
                .join('');
            return `<select class="form-select form-select-sm" name="link_jellyfin_${escapedLibName}" style="width: 180px;">${options}</select>`;
        };
        
        // Build combined library list - show PRIMARY server's libraries with optional linking to secondary
        let libraryItems = [];
        
        // Show ONLY the primary server's libraries
        if (primaryServer === 'plex' && plexLibraries.length > 0) {
            const currentLibs = window.Librarrarian.settings.plexLibraries || [];
            libraryItems = plexLibraries.map(lib => {
                const escapedTitle = escapeHtml(lib.title);
                const escapedKey = escapeHtml(lib.key);
                return `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <span class="badge badge-outline-warning me-2">Plex</span>
                    <div class="form-check" style="min-width: 200px;">
                        <input class="form-check-input" type="checkbox" name="plex_libraries" value="${escapedTitle}" id="lib-${escapedKey}" ${currentLibs.includes(lib.title) ? 'checked' : ''}>
                        <label class="form-check-label" for="lib-${escapedKey}">${escapedTitle}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center gap-2">
                        ${createDropdown(`type_plex_${escapedTitle}`, lib.type)}
                        ${hasJellyfinAuth ? '<span class="badge badge-outline-purple">Jellyfin</span>' : ''}
                        ${hasJellyfinAuth ? createJellyfinLinkDropdown(lib.title, lib.linked_library || '') : ''}
                    </div>
                </div>
                `;
            });
        } else if (primaryServer === 'jellyfin' && jellyfinLibraries.length > 0) {
            const currentLibs = window.Librarrarian.settings.jellyfinLibraries || [];
            libraryItems = jellyfinLibraries.map(lib => {
                const escapedTitle = escapeHtml(lib.title);
                const escapedId = escapeHtml(lib.id || lib.title);
                return `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <span class="badge badge-outline-purple me-2">Jellyfin</span>
                    <div class="form-check" style="min-width: 200px;">
                        <input class="form-check-input" type="checkbox" name="jellyfin_libraries" value="${escapedTitle}" id="jlib-${escapedId}" ${currentLibs.includes(lib.title) ? 'checked' : ''}>
                        <label class="form-check-label" for="jlib-${escapedId}">${escapedTitle}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center gap-2">
                        ${createDropdown(`type_jellyfin_${escapedTitle}`, lib.type)}
                        ${hasPlexAuth ? '<span class="badge badge-outline-warning">Plex</span>' : ''}
                        ${hasPlexAuth ? createPlexLinkDropdown(lib.title, lib.linked_library || '') : ''}
                    </div>
                </div>
                `;
            });
        }
        
        if (libraryItems.length > 0) {
            container.innerHTML = libraryItems.join('');
            
            // DEBUG: Log created form fields for sync mode debugging
            console.log('[Sync Mode Debug] Combined libraries loaded. Form fields created:');
            const typeDropdowns = container.querySelectorAll('select[name^="type_"]');
            const linkDropdowns = container.querySelectorAll('select[name^="link_"]');
            const checkboxes = container.querySelectorAll('input[type="checkbox"]');
            
            console.log(`  - ${typeDropdowns.length} type dropdowns:`);
            typeDropdowns.forEach(dropdown => {
                console.log(`    ${dropdown.name} = ${dropdown.value} (disabled: ${dropdown.disabled})`);
            });
            
            console.log(`  - ${linkDropdowns.length} link dropdowns:`);
            linkDropdowns.forEach(dropdown => {
                console.log(`    ${dropdown.name} = ${dropdown.value} (disabled: ${dropdown.disabled})`);
            });
            
            console.log(`  - ${checkboxes.length} library checkboxes (checked: ${Array.from(checkboxes).filter(cb => cb.checked).length})`);
        } else {
            // Show appropriate message based on primary server
            const serverName = primaryServer === 'plex' ? 'Plex' : 'Jellyfin';
            const serverError = primaryServer === 'plex' ? plexError : jellyfinError;
            
            if ((primaryServer === 'plex' && !hasPlexAuth) || (primaryServer === 'jellyfin' && !hasJellyfinAuth)) {
                container.innerHTML = `<p class="text-muted">Link your ${serverName} account to see libraries.</p>`;
            } else if (serverError) {
                container.innerHTML = `<p class="text-muted">${serverError}</p>`;
            } else {
                container.innerHTML = `<p class="text-muted">No libraries found.</p>`;
            }
        }
        
        // Apply the initial visibility based on the toggle's state
        if (typeof applyCombinedVisibility === 'function') {
            applyCombinedVisibility();
        }
    }

    // --- Event listeners for multi-server library linking ---
    
    // Function to update the sync checkbox state based on what servers are linked
    function updateSyncCheckboxState() {
        const multiServerCheckbox = document.getElementById('enable_multi_server');
        if (!multiServerCheckbox) return;
        
        const primaryServer = document.querySelector('input[name="primary_media_server"]:checked')?.value;
        
        // If internal scanner is selected, disable sync
        if (primaryServer === 'internal') {
            multiServerCheckbox.disabled = true;
            multiServerCheckbox.checked = false;
            return;
        }
        
        // Check if both Plex and Jellyfin are linked
        const plexLinked = window.Librarrarian.settings.plexToken && window.Librarrarian.settings.plexToken.length > 0;
        const jellyfinLinked = window.Librarrarian.settings.jellyfinApiKey && window.Librarrarian.settings.jellyfinApiKey.length > 0;
        
        // Only enable sync if both servers are linked
        if (plexLinked && jellyfinLinked) {
            multiServerCheckbox.disabled = false;
        } else {
            multiServerCheckbox.disabled = true;
            multiServerCheckbox.checked = false;
        }
    }
    
    // Reload libraries when multi-server is toggled
    const multiServerCheckbox = document.getElementById('enable_multi_server');
    if (multiServerCheckbox) {
        multiServerCheckbox.addEventListener('change', () => {
            handlePrimaryServerChange();
        });
    }

    // Function to handle primary server changes
    function handlePrimaryServerChange() {
        const primaryServer = document.querySelector('input[name="primary_media_server"]:checked')?.value;
        const multiServerCheckbox = document.getElementById('enable_multi_server');
        const multiServerEnabled = multiServerCheckbox?.checked;
        const mediaServersTab = document.getElementById('media-servers-tab');
        const internalTab = document.getElementById('internal-integration-tab');
        const plexContainer = document.getElementById('plex-libraries-container');
        const jellyfinContainer = document.getElementById('jellyfin-libraries-container');
        const combinedContainer = document.getElementById('combined-libraries-container');
        
        // Update sync checkbox state based on linked servers
        updateSyncCheckboxState();
        
        if (primaryServer === 'internal') {
            // If Internal Media Scanner is selected:
            // - Disable Media Servers tab
            // - Enable Internal Media Scanner tab
            // - Auto-switch to Internal Media Scanner tab
            // - Hide all library containers
            if (mediaServersTab) {
                mediaServersTab.disabled = true;
            }
            if (internalTab) {
                internalTab.disabled = false;
                // Auto-activate Internal Media Scanner tab
                try {
                    const internalTabButton = new bootstrap.Tab(internalTab);
                    internalTabButton.show();
                } catch (e) {
                    console.error('Error activating Internal Media Scanner tab:', e);
                }
            }
            if (plexContainer) plexContainer.style.display = 'none';
            if (jellyfinContainer) jellyfinContainer.style.display = 'none';
            if (combinedContainer) combinedContainer.style.display = 'none';
            
            // Don't load libraries when internal is selected
            return;
        } else {
            // If Plex or Jellyfin is selected:
            // - Enable Media Servers tab
            // - Disable Internal Media Scanner tab
            // - Auto-switch to Media Servers tab
            if (mediaServersTab) {
                mediaServersTab.disabled = false;
                // Auto-activate Media Servers tab
                try {
                    const mediaServersTabButton = new bootstrap.Tab(mediaServersTab);
                    mediaServersTabButton.show();
                } catch (e) {
                    console.error('Error activating Media Servers tab:', e);
                }
            }
            if (internalTab) {
                internalTab.disabled = true;
            }
            
            // Show/hide library containers based on selection and multi-server mode
            // Also disable form inputs in hidden containers to prevent them from being submitted
            if (multiServerEnabled) {
                // When multi-server is enabled, show only the combined container
                if (plexContainer) {
                    plexContainer.style.display = 'none';
                    // Disable all form inputs in this container
                    plexContainer.querySelectorAll('input, select').forEach(el => el.disabled = true);
                }
                if (jellyfinContainer) {
                    jellyfinContainer.style.display = 'none';
                    // Disable all form inputs in this container
                    jellyfinContainer.querySelectorAll('input, select').forEach(el => el.disabled = true);
                }
                if (combinedContainer) {
                    combinedContainer.style.display = 'block';
                    // Enable all form inputs in this container
                    combinedContainer.querySelectorAll('input, select').forEach(el => el.disabled = false);
                }
                
                // Load combined libraries
                loadCombinedLibraries();
            } else {
                // When multi-server is disabled, hide combined and show only the selected server's container
                if (combinedContainer) {
                    combinedContainer.style.display = 'none';
                    // Disable all form inputs in this container
                    combinedContainer.querySelectorAll('input, select').forEach(el => el.disabled = true);
                }
                
                if (primaryServer === 'plex') {
                    if (plexContainer) {
                        plexContainer.style.display = 'block';
                        // Enable all form inputs in this container
                        plexContainer.querySelectorAll('input, select').forEach(el => el.disabled = false);
                    }
                    if (jellyfinContainer) {
                        jellyfinContainer.style.display = 'none';
                        // Disable all form inputs in this container
                        jellyfinContainer.querySelectorAll('input, select').forEach(el => el.disabled = true);
                    }
                    loadPlexLibraries();
                } else if (primaryServer === 'jellyfin') {
                    if (plexContainer) {
                        plexContainer.style.display = 'none';
                        // Disable all form inputs in this container
                        plexContainer.querySelectorAll('input, select').forEach(el => el.disabled = true);
                    }
                    if (jellyfinContainer) {
                        jellyfinContainer.style.display = 'block';
                        // Enable all form inputs in this container
                        jellyfinContainer.querySelectorAll('input, select').forEach(el => el.disabled = false);
                    }
                    loadJellyfinLibraries();
                }
            }
        }
    }
    
    // Reload libraries when primary server changes
    const primaryServerRadios = document.querySelectorAll('input[name="primary_media_server"]');
    primaryServerRadios.forEach(radio => {
        radio.addEventListener('change', handlePrimaryServerChange);
    });
    
    // Initialize on page load
    updateSyncCheckboxState();
    handlePrimaryServerChange();

    // --- Dynamic Internal Folder Loading ---
    async function loadInternalFolders() {
        const container = document.getElementById('internal-folders-list');
        const mediaTypes = {
            'movie': 'Movie',
            'show': 'TV Show',
            'music': 'Music',
            'other': 'Other Videos',
            'none': 'None (Ignore)'
        };
        const createDropdown = (name, selectedType) => {
            const options = Object.entries(mediaTypes).map(([key, value]) => `<option value="${key}" ${selectedType === key ? 'selected' : ''}>${value}</option>`).join('');
            return `<select class="form-select form-select-sm" name="${name}" style="width: 150px;">${options}</select>`;
        };
        container.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Loading folders...';

        const response = await fetch('/api/internal/folders');
        const data = await response.json();
        const currentPaths = window.Librarrarian.settings.internalScanPaths;

        if (data.folders && data.folders.length > 0) {
            container.innerHTML = data.folders.map(item => `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="internal_scan_paths" value="${item.name}" id="folder-${item.name}" ${currentPaths.includes(item.name) ? 'checked' : ''}>
                        <label class="form-check-label" for="folder-${item.name}">${item.name}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center me-2">
                        ${createDropdown(`type_internal_${item.name}`, item.type)}
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `<p class="text-muted">${data.error || 'No subdirectories found in /media.'}</p>`;
        }

        // Apply the initial visibility based on the toggle's state
        if (typeof applyInternalVisibility === 'function') {
            applyInternalVisibility();
        }
    }
    const internalTab = document.getElementById('internal-integration-tab');
    if (internalTab) {
        internalTab.addEventListener('shown.bs.tab', () => {
            loadInternalFolders();
        });
    }

    // --- NEW: Integrations Tab Logic ---
    const scannerPlexRadio = document.getElementById('scanner_plex');
    const scannerInternalRadio = document.getElementById('scanner_internal');
    const pathFromInput = document.getElementById('plex_path_from');
    const pathFromLabel = document.getElementById('path-from-label');
    const pathFromTooltip = document.getElementById('path-from-tooltip');
    const plexTabButton = document.getElementById('plex-integration-tab');
    const pathMappingToggleContainer = document.getElementById('path-mapping-toggle-container');
    const pathMappingToggle = document.getElementById('plex_path_mapping_enabled');
    const internalTabButton = document.getElementById('internal-integration-tab');

    // Only set up scanner change logic if the required elements exist
    if (scannerPlexRadio && scannerInternalRadio && pathFromInput && pathFromLabel && 
        pathFromTooltip && plexTabButton && pathMappingToggleContainer && 
        pathMappingToggle && internalTabButton) {
        
        function handleScannerChange() {
            // Both inputs should always be enabled.
            pathFromInput.disabled = false;

            if (scannerPlexRadio.checked) {
                pathFromLabel.innerText = 'Path in Plex';
                pathFromTooltip.setAttribute('data-bs-original-title', 'The absolute path to your media as seen by the Plex server (e.g., /data/movies)');
                // Enable Plex tab, disable Internal tab
                plexTabButton.disabled = false;
                internalTabButton.disabled = true;
                // If the internal tab was active, switch to the plex tab
                pathMappingToggleContainer.style.display = 'block'; // Show the toggle
                // Disable/enable path inputs based on the toggle's state
                const isMappingEnabled = pathMappingToggle.checked;
                document.getElementById('plex_path_from').disabled = !isMappingEnabled;
                document.getElementById('plex_path_to').disabled = !isMappingEnabled;

                if (internalTabButton.classList.contains('active')) {
                    new bootstrap.Tab(plexTabButton).show();
                }
            } else if (scannerInternalRadio.checked) {
                pathFromLabel.innerText = 'Internal Worker Path';
                pathFromTooltip.setAttribute('data-bs-original-title', 'The absolute path to your media as seen by the worker machine (e.g., /nfs/media)');
                // Disable Plex tab, enable Internal tab
                plexTabButton.disabled = true;
                internalTabButton.disabled = false;
                pathMappingToggleContainer.style.display = 'none'; // Hide the toggle
                // Always enable path inputs for internal scanner
                document.getElementById('plex_path_from').disabled = false;
                document.getElementById('plex_path_to').disabled = false;
                // If the plex tab was active, switch to the internal tab
                if (plexTabButton.classList.contains('active')) {
                    new bootstrap.Tab(internalTabButton).show();
                }
            }

            // Also update the manual scan button state
            const manualScanBtn = document.getElementById('manual-scan-btn');
            if (manualScanBtn) {
                const hasPlexToken = window.Librarrarian.settings.plexToken !== "";
                if (scannerPlexRadio.checked && !hasPlexToken) {
                    manualScanBtn.disabled = true;
                    manualScanBtn.title = "Plex account must be linked to run a scan.";
                } else {
                    manualScanBtn.disabled = false;
                    manualScanBtn.title = "Trigger a manual scan of the active media integration";
                }
            }
        }

        scannerPlexRadio.addEventListener('change', handleScannerChange);
        scannerInternalRadio.addEventListener('change', handleScannerChange);
        // Add listener for the new toggle
        pathMappingToggle.addEventListener('change', () => {
            const isEnabled = pathMappingToggle.checked;
            document.getElementById('plex_path_from').disabled = !isEnabled;
            document.getElementById('plex_path_to').disabled = !isEnabled;
        });

        handleScannerChange(); // Run on initial script execution to set the correct state
    }

    // --- Manual Media Scan Logic ---
    const manualScanBtn = document.getElementById('manual-scan-btn');
    const scanStatusDiv = document.getElementById('scan-status');
    const forceRescanCheckbox = document.getElementById('force-rescan-checkbox');
    
    if (manualScanBtn && scanStatusDiv) {
        // Media scan progress elements
        const mediaScanContainer = document.getElementById('media-scan-container');
        const mediaScanFeedback = document.getElementById('media-scan-feedback');
        const mediaScanProgress = document.getElementById('media-scan-progress');
        const mediaScanProgressBar = mediaScanProgress ? mediaScanProgress.querySelector('.progress-bar') : null;
        const mediaScanProgressText = document.getElementById('media-scan-progress-text');
        const mediaScanTime = document.getElementById('media-scan-time');
        
        let mediaScanInterval = null;
        let mediaScanStartTime = null;

        function startMediaScanPolling() {
            if (mediaScanInterval) clearInterval(mediaScanInterval);
            
            mediaScanStartTime = new Date();
            if (mediaScanContainer) mediaScanContainer.style.display = 'block';
            if (mediaScanProgress) mediaScanProgress.style.display = 'block';
            if (mediaScanProgressBar) {
                mediaScanProgressBar.style.width = '0%';
                mediaScanProgressBar.textContent = '0%';
            }
            if (mediaScanProgressText) mediaScanProgressText.textContent = 'Starting scan...';
            
            mediaScanInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/scan/progress');
                    const data = await response.json();
                    
                    const now = new Date();
                    const elapsedSeconds = Math.round((now - mediaScanStartTime) / 1000);
                    if (mediaScanTime) mediaScanTime.textContent = `Elapsed: ${formatElapsedTime(elapsedSeconds)}`;
                    
                    if (data.is_running && (data.scan_source === 'plex' || data.scan_source === 'internal')) {
                        const progressPercent = data.total_steps > 0 ? ((data.progress / data.total_steps) * 100).toFixed(1) : 0;
                        if (mediaScanProgressBar) {
                            mediaScanProgressBar.style.width = `${progressPercent}%`;
                            mediaScanProgressBar.textContent = `${progressPercent}%`;
                        }
                        if (mediaScanProgressText) mediaScanProgressText.textContent = data.current_step || 'Scanning...';
                    } else if (!data.is_running && (data.scan_source === '' || data.scan_source === 'plex' || data.scan_source === 'internal')) {
                        // Scan finished
                        clearInterval(mediaScanInterval);
                        mediaScanInterval = null;
                        
                        if (mediaScanProgressBar) {
                            mediaScanProgressBar.style.width = '100%';
                            mediaScanProgressBar.textContent = '100%';
                        }
                        if (mediaScanProgressText) mediaScanProgressText.textContent = data.current_step || 'Scan complete.';
                        
                        // Re-enable the button
                        if (manualScanBtn) {
                            manualScanBtn.disabled = false;
                            manualScanBtn.innerHTML = `<span class="mdi mdi-sync"></span> Scan Media`;
                        }
                        
                        // Refresh the job queue
                        updateJobQueue();
                        
                        // Hide progress after a delay
                        setTimeout(() => {
                            if (mediaScanContainer) mediaScanContainer.style.display = 'none';
                        }, 3000);
                    }
                } catch (error) {
                    console.error('Error polling for media scan progress:', error);
                }
            }, 2000);
        }

    manualScanBtn.addEventListener('click', async () => {
        manualScanBtn.disabled = true;
        manualScanBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Scanning...`;
        scanStatusDiv.innerHTML = '';
        const isForced = forceRescanCheckbox.checked;

        try {
            const response = await fetch('/api/scan/trigger', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ force: isForced }) });
            const data = await response.json();
            
            if (data.success) {
                // Start polling for progress
                startMediaScanPolling();
            } else {
                const alertClass = 'alert-warning';
                scanStatusDiv.innerHTML = `<div class="alert ${alertClass} alert-dismissible fade show" role="alert">${data.message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
                manualScanBtn.disabled = false;
                manualScanBtn.innerHTML = `<span class="mdi mdi-sync"></span> Scan Media`;
            }
        } catch (error) {
            scanStatusDiv.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">Error communicating with the server.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
            manualScanBtn.disabled = false;
            manualScanBtn.innerHTML = `<span class="mdi mdi-sync"></span> Scan Media`;
        }
    });
    
        // On page load, check if a media scan is already running
        fetch('/api/scan/progress').then(r => r.json()).then(data => {
            if (data.is_running && (data.scan_source === 'plex' || data.scan_source === 'internal')) {
                manualScanBtn.disabled = true;
                manualScanBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Scanning...`;
                startMediaScanPolling();
            }
        });
    }

    // --- Sonarr Options Logic ---
    const sendToQueueSwitch = document.getElementById('sonarr_send_to_queue');
    const sonarrStatusDiv = document.getElementById('sonarr-test-status');

    // --- *Arr Integration Enable/Disable Logic ---
    function setupArrToggle(arrType) {
        const enableToggle = document.getElementById(`${arrType}_enabled`);
        const integrationPane = document.getElementById(`${arrType}-integration-pane`);
        const enableLabel = document.getElementById(`${arrType}_enabled_label`);
        if (!enableToggle || !integrationPane) return;

        const mainToggleId = `${arrType}_enabled`;
        
        // Get all non-checkbox inputs, selects, buttons, and range inputs
        const inputs = integrationPane.querySelectorAll('input:not([type=checkbox]), select, button, input[type=range]');
        const checkboxes = integrationPane.querySelectorAll('input[type=checkbox]');

        function updateInputsState() {
            const isEnabled = enableToggle.checked;
            
            // Update label text
            if (enableLabel) {
                enableLabel.textContent = isEnabled ? 'Disable' : 'Enable';
            }
            
            // Disable/enable all text inputs, selects, buttons
            inputs.forEach(input => {
                if (input.id !== mainToggleId) input.disabled = !isEnabled;
            });
            
            // Disable/enable all checkboxes except the main enable toggle
            checkboxes.forEach(checkbox => {
                if (checkbox.id !== mainToggleId) checkbox.disabled = !isEnabled;
            });
            
            // Special handling for Sonarr tools
            if (arrType === 'sonarr') {
                const renameBtn = document.getElementById('sonarr-rename-scan-button');
                const qualityBtn = document.getElementById('sonarr-quality-scan-button');
                if (renameBtn && qualityBtn) [renameBtn, qualityBtn].forEach(btn => btn.disabled = !isEnabled);
            }
        }
        enableToggle.addEventListener('change', updateInputsState);
        updateInputsState(); // Set initial state on page load
    }
    ['sonarr', 'radarr', 'lidarr'].forEach(setupArrToggle);

    const releaseSelectedBtn = document.getElementById('release-selected-btn');
    const releaseAllCleanupBtn = document.getElementById('release-all-cleanup-btn');
    const releaseAllRenameBtn = document.getElementById('release-all-rename-btn');

    if (releaseSelectedBtn) {
        releaseSelectedBtn.addEventListener('click', async () => {
            const selectedIds = Array.from(document.querySelectorAll('.approval-checkbox:checked')).map(cb => cb.dataset.jobId);
            if (selectedIds.length === 0) {
                alert('No jobs selected. Select jobs awaiting approval to release them.');
                return;
            }
            if (confirm(`Are you sure you want to release ${selectedIds.length} job(s) to the queue?`)) {
                // Release all job types when selected
                await releaseJobs({ job_ids: selectedIds, job_type: ['cleanup', 'Rename Job'] });
            }
        });
    }

    if (releaseAllCleanupBtn) {
        releaseAllCleanupBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to release ALL cleanup jobs that are awaiting approval?')) {
                await releaseJobs({ release_all: true, job_type: 'cleanup' });
            }
        });
    }

    if (releaseAllRenameBtn) {
        releaseAllRenameBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to release ALL rename jobs that are awaiting approval? They will be processed automatically.')) {
                await releaseJobs({ release_all: true, job_type: 'Rename Job' });
            }
        });
    }

    async function releaseJobs(payload) {
        try {
            const response = await fetch('/api/jobs/release', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                updateJobQueue(jobQueueCurrentPage); // Refresh the queue
            }
        } catch (error) {
            alert('An error occurred while trying to release jobs.');
        }
    }

    // --- Clear All Jobs Logic ---
    const clearJobsBtn = document.getElementById('clear-jobs-btn');
    if (clearJobsBtn) {
        clearJobsBtn.addEventListener('click', async () => {
            const forceClearCheckbox = document.getElementById('force-clear-checkbox');
            const force = forceClearCheckbox ? forceClearCheckbox.checked : false;
            
            const confirmMessage = force 
                ? 'Are you sure you want to force clear the entire job queue? This will remove ALL jobs including those currently encoding. This action cannot be undone.'
                : 'Are you sure you want to permanently clear the entire job queue? This action cannot be undone.';
            
            if (!confirm(confirmMessage)) {
                return;
            }
            try {
                const response = await fetch('/api/jobs/clear', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: force })
                });
                if (response.ok) {
                    updateJobQueue(1); // Refresh the queue to show it's empty
                }
            } catch (error) {
                alert('An error occurred while trying to clear the job queue.');
            }
        });
    }

    // --- Delete Individual Job Logic ---
    window.deleteJob = async function(jobId) {
        if (!confirm(`Are you sure you want to permanently delete job ${jobId}?`)) {
            return;
        }
        try {
            const response = await fetch(`/api/jobs/delete/${jobId}`, { method: 'POST' });
            if (response.ok) {
                updateJobQueue(jobQueueCurrentPage); // Refresh the queue
            }
        } catch (error) {
            console.error('Error deleting job:', error);
            alert('An error occurred while trying to delete the job.');
        }
    }

    window.requeueJob = async function(jobId) {
        if (!confirm(`Are you sure you want to re-add job ${jobId} to the queue? This will reset it to pending status.`)) {
            return;
        }
        try {
            const response = await fetch(`/api/jobs/requeue/${jobId}`, { method: 'POST' });
            if (response.ok) {
                updateJobQueue(jobQueueCurrentPage); // Refresh the queue
            } else {
                const data = await response.json();
                alert(`Error: ${data.error || 'Failed to re-queue job'}`);
            }
        } catch (error) {
            console.error('Error re-queuing job:', error);
            alert('An error occurred while trying to re-queue the job.');
        }
    }

    // --- Pause Queue Button Logic ---
    const pauseQueueBtn = document.getElementById('pause-queue-btn');
    if (pauseQueueBtn) {
        pauseQueueBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/queue/toggle_pause', { method: 'POST' });
                if (response.ok) {
                    mainUpdateLoop(); // Immediately refresh the UI to show the new state
                }
            } catch (error) {
                alert('An error occurred while trying to toggle the queue state.');
            }
        });
    }

    // --- *Arr Connection Test Logic ---
    window.testArrConnection = async function(arrType) {
        const host = document.getElementById(`${arrType}_host`).value;
        const apiKey = document.getElementById(`${arrType}_api_key`).value;
        const statusDiv = document.getElementById(`${arrType}-test-status`);

        if (!host || !apiKey) {
            statusDiv.innerHTML = `<div class="alert alert-warning alert-dismissible fade show" role="alert">Host and API Key are required.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
            return;
        }

        statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Testing...`;

        try {
            const response = await fetch('/api/arr/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ arr_type: arrType, host: host, api_key: apiKey })
            });
            const data = await response.json();
            const alertClass = data.success ? 'alert-success' : 'alert-danger';
            statusDiv.innerHTML = `<div class="alert ${alertClass} alert-dismissible fade show" role="alert">${data.message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
        } catch (error) {
            console.error(`Error testing ${arrType} connection:`, error);
            statusDiv.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">An error occurred while communicating with the server.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
        }
    }

    // --- Backup Now Button Handler ---
    const backupNowBtn = document.getElementById('backup-now-btn');
    const backupStatus = document.getElementById('backup-status');
    
    if (backupNowBtn && backupStatus) {
        backupNowBtn.addEventListener('click', async () => {
            // Disable button and show loading state
            backupNowBtn.disabled = true;
            backupNowBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running backup...';
            backupStatus.innerHTML = '';
            
            try {
                const response = await fetch('/api/backup/now', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    backupStatus.innerHTML = `<div class="alert alert-success alert-dismissible fade show" role="alert">${data.message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
                } else {
                    backupStatus.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">Backup failed: ${data.error}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
                }
            } catch (error) {
                console.error('Error running backup:', error);
                backupStatus.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">An error occurred while running the backup.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
            } finally {
                // Re-enable button
                backupNowBtn.disabled = false;
                backupNowBtn.innerHTML = '<span class="mdi mdi-database-export"></span> Run Backup Now';
            }
        });
    }
    
    // --- Manage Backups Button Handler ---
    const manageBackupsBtn = document.getElementById('manage-backups-btn');
    
    if (manageBackupsBtn) {
        manageBackupsBtn.addEventListener('click', () => {
            const backupModal = new bootstrap.Modal(document.getElementById('backupModal'));
            loadBackupFiles();
            backupModal.show();
        });
    }
    
    // Helper function to escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Function to load backup files into the modal
    async function loadBackupFiles() {
        const tableBody = document.getElementById('backup-files-table-body');
        const alertDiv = document.getElementById('backup-modal-alert');
        
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading backup files...</td></tr>';
        alertDiv.style.display = 'none';
        
        try {
            const response = await fetch('/api/backup/files');
            const data = await response.json();
            
            if (data.success) {
                if (data.files.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No backup files found.</td></tr>';
                } else {
                    tableBody.innerHTML = data.files.map(file => {
                        const safeFilename = escapeHtml(file.filename);
                        const safeSizeMb = escapeHtml(String(file.size_mb));
                        const safeCreated = escapeHtml(file.created);
                        return `
                        <tr>
                            <td style="word-break: break-all;">${safeFilename}</td>
                            <td>${safeSizeMb} MB</td>
                            <td>${safeCreated}</td>
                            <td>
                                <div class="btn-group btn-group-sm" role="group">
                                    <button class="btn btn-outline-primary" onclick="downloadBackup('${safeFilename}')" title="Download backup">
                                        <span class="mdi mdi-download"></span> Download
                                    </button>
                                    <button class="btn btn-outline-danger" onclick="deleteBackup('${safeFilename}')" title="Delete backup">
                                        <span class="mdi mdi-delete"></span> Delete
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `}).join('');
                }
            } else {
                const safeError = escapeHtml(data.error || 'Unknown error');
                alertDiv.innerHTML = `<div class="alert alert-danger" role="alert">Failed to load backup files: ${safeError}</div>`;
                alertDiv.style.display = 'block';
                tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Failed to load backup files.</td></tr>';
            }
        } catch (error) {
            console.error('Error loading backup files:', error);
            alertDiv.innerHTML = `<div class="alert alert-danger" role="alert">An error occurred while loading backup files.</div>`;
            alertDiv.style.display = 'block';
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Failed to load backup files.</td></tr>';
        }
    }
    
    // Function to download a backup file
    window.downloadBackup = function(filename) {
        window.location.href = `/api/backup/download/${encodeURIComponent(filename)}`;
    };
    
    // Function to delete a backup file
    window.deleteBackup = async function(filename) {
        if (!confirm(`Are you sure you want to delete the backup file "${filename}"? This action cannot be undone.`)) {
            return;
        }
        
        const alertDiv = document.getElementById('backup-modal-alert');
        
        try {
            const response = await fetch(`/api/backup/delete/${encodeURIComponent(filename)}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                const safeMessage = escapeHtml(data.message);
                alertDiv.innerHTML = `<div class="alert alert-success alert-dismissible fade show" role="alert">${safeMessage}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
                alertDiv.style.display = 'block';
                // Reload the backup files list
                loadBackupFiles();
            } else {
                const safeError = escapeHtml(data.error || 'Unknown error');
                alertDiv.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">Failed to delete backup: ${safeError}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
                alertDiv.style.display = 'block';
            }
        } catch (error) {
            console.error('Error deleting backup:', error);
            alertDiv.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">An error occurred while deleting the backup.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
            alertDiv.style.display = 'block';
        }
    };
});

// --- Theme Switcher Logic ---
(function() {
    const themeIcon = document.getElementById('theme-icon');
    const getStoredTheme = () => localStorage.getItem('theme');
    const setStoredTheme = theme => localStorage.setItem('theme', theme);

    const getResolvedTheme = (theme) => {
        // 'auto' should resolve to the system preference
        if (theme === 'auto') {
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        // Christmas theme and other themes pass through as-is
        return theme;
    };

    const setTheme = theme => {
        // Resolve 'auto' to actual theme for Bootstrap
        const resolvedTheme = getResolvedTheme(theme);
        document.documentElement.setAttribute('data-bs-theme', resolvedTheme);
        
        // Update icon based on stored theme (not resolved) to show user's selection
        if (theme === 'dark') themeIcon.className = 'mdi mdi-weather-night';
        else if (theme === 'light') themeIcon.className = 'mdi mdi-weather-sunny';
        else if (theme === 'christmas') themeIcon.className = 'mdi mdi-pine-tree';
        else if (theme === 'summer-christmas') themeIcon.className = 'mdi mdi-white-balance-sunny';
        else themeIcon.className = 'mdi mdi-desktop-classic';
        
        // Enable/disable Christmas snow effect for both Christmas themes
        if (typeof window.snowEffect !== 'undefined') {
            if (theme === 'christmas' || theme === 'summer-christmas') {
                window.snowEffect.start();
            } else {
                window.snowEffect.stop();
            }
        }
    };

    // Set initial theme on page load
    setTheme(getStoredTheme() || 'dark');

    // Handle theme selection from dropdown
    document.querySelectorAll('[data-theme-value]').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const theme = toggle.getAttribute('data-theme-value');
            setStoredTheme(theme);
            setTheme(theme);
        });
    });

    // Listen for system preference changes (for 'auto' mode)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const storedTheme = getStoredTheme();
        if (storedTheme === 'auto') {
            setTheme('auto');
        }
    });
})();

// --- Changelog Modal Logic ---
document.addEventListener('DOMContentLoaded', () => {
    const changelogModal = document.getElementById('changelogModal');
    const changelogContent = document.getElementById('changelog-content');
    const versionToggle = document.getElementById('changelog-version-toggle');

    const converter = new showdown.Converter({ simplifiedAutoLink: true, openLinksInNewWindow: true });

    async function determineAndLoadChangelog() {
        const internalVersion = window.Librarrarian.version;
        const mainVersionUrl = "https://raw.githubusercontent.com/m1ckyb/Librarrarian/refs/heads/main/VERSION.txt";

        try {
            const response = await fetch(mainVersionUrl);
            const latestStableVersion = (await response.text()).trim();

            // Use localeCompare with numeric option for proper version comparison (e.g., "0.10.7b" > "0.10.7")
            const comparison = internalVersion.localeCompare(latestStableVersion, undefined, { numeric: true });

            if (comparison > 0) {
                // Current version is newer than main, default to develop
                versionToggle.checked = true;
            } else {
                // Current version is same or older, default to main
                versionToggle.checked = false;
            }
        } catch (error) {
            console.error("Could not fetch latest stable version, defaulting to main branch.", error);
            versionToggle.checked = false;
        } finally {
            // Load the changelog based on the determined default
            await loadChangelog();
        }
    }

    let changelogReleases = [];
    let currentPage = 1;
    const releasesPerPage = 5;

    async function loadChangelog() {
        const isDevelop = versionToggle.checked;
        const branch = isDevelop ? 'develop' : 'main';
        const url = `https://raw.githubusercontent.com/m1ckyb/Librarrarian/refs/heads/${branch}/CHANGELOG.md`;

        changelogContent.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const markdown = await response.text();
            
            // Split changelog into releases (sections starting with ##)
            const sections = markdown.split(/(?=^## \[)/gm);
            changelogReleases = sections.filter(s => s.trim().startsWith('## ['));
            
            currentPage = 1;
            renderChangelogPage();
        } catch (error) {
            console.error('Error fetching changelog:', error);
            changelogContent.innerHTML = '<div class="alert alert-danger">Failed to load changelog. Please check your internet connection.</div>';
        }
    }

    function renderChangelogPage() {
        const startIdx = (currentPage - 1) * releasesPerPage;
        const endIdx = startIdx + releasesPerPage;
        const pageReleases = changelogReleases.slice(startIdx, endIdx);
        const totalPages = Math.ceil(changelogReleases.length / releasesPerPage);

        // Convert markdown to HTML for current page
        const pageMarkdown = pageReleases.join('\n\n');
        const html = converter.makeHtml(pageMarkdown);

        // Add pagination controls
        let paginationHtml = '';
        if (totalPages > 1) {
            paginationHtml = '<nav class="mt-3"><ul class="pagination justify-content-center">';
            
            // Previous button
            paginationHtml += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${currentPage - 1}">&laquo; Previous</a>
            </li>`;
            
            // Page numbers
            for (let i = 1; i <= totalPages; i++) {
                paginationHtml += `<li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>`;
            }
            
            // Next button
            paginationHtml += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" data-page="${currentPage + 1}">Next &raquo;</a>
            </li>`;
            
            paginationHtml += '</ul></nav>';
        }

        changelogContent.innerHTML = html + paginationHtml;

        // Add click handlers to pagination links
        changelogContent.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const newPage = parseInt(e.target.getAttribute('data-page'));
                if (newPage >= 1 && newPage <= totalPages) {
                    currentPage = newPage;
                    renderChangelogPage();
                    // Scroll to top of modal content
                    changelogContent.scrollTop = 0;
                }
            });
        });
    }

    // Load content when the modal is shown
    changelogModal.addEventListener('show.bs.modal', determineAndLoadChangelog);

    // Reload content when the toggle is switched
    versionToggle.addEventListener('change', loadChangelog);

    // ===== Backup Settings Toggle =====
    const backupEnabledCheckbox = document.getElementById('backup_enabled');
    const backupScheduleFields = document.getElementById('backup-schedule-fields');
    
    if (backupEnabledCheckbox && backupScheduleFields) {
        // Function to toggle visibility
        function toggleBackupFields() {
            if (backupEnabledCheckbox.checked) {
                backupScheduleFields.style.display = 'block';
            } else {
                backupScheduleFields.style.display = 'none';
            }
        }
        
        // Set initial state
        toggleBackupFields();
        
        // Listen for changes
        backupEnabledCheckbox.addEventListener('change', toggleBackupFields);
    }
    
    // ===== Slider Value Display =====
    const rescanDelaySlider = document.getElementById('rescan_delay_hours');
    const rescanDelayValue = document.getElementById('rescan_delay_hours_value');
    
    if (rescanDelaySlider && rescanDelayValue) {
        // Function to update display value
        function updateRescanDelayDisplay() {
            const hours = parseFloat(rescanDelaySlider.value);
            if (hours === 0) {
                rescanDelayValue.textContent = 'Disabled';
            } else if (hours < 1) {
                const minutes = Math.round(hours * 60);
                rescanDelayValue.textContent = `${minutes} min`;
            } else {
                rescanDelayValue.textContent = `${hours} hrs`;
            }
        }
        
        // Set initial value
        updateRescanDelayDisplay();
        
        // Update on change
        rescanDelaySlider.addEventListener('input', updateRescanDelayDisplay);
    }
    
    const pollIntervalSlider = document.getElementById('worker_poll_interval');
    const pollIntervalValue = document.getElementById('worker_poll_interval_value');
    
    if (pollIntervalSlider && pollIntervalValue) {
        // Function to update display value
        function updatePollIntervalDisplay() {
            const seconds = parseInt(pollIntervalSlider.value);
            if (seconds === 0) {
                pollIntervalValue.textContent = 'Disabled';
            } else {
                pollIntervalValue.textContent = `${seconds}s`;
            }
        }
        
        // Set initial value
        updatePollIntervalDisplay();
        
        // Update on change
        pollIntervalSlider.addEventListener('input', updatePollIntervalDisplay);
    }
}); // End of main DOMContentLoaded block

// --- Debug Settings Modal (DEVMODE only) ---
// This section handles the debug settings modal that shows database settings
// Use a function that works whether DOM is already loaded or not
function initDebugSettingsModal() {
    const debugSettingsModal = document.getElementById('debugSettingsModal');
    if (!debugSettingsModal) {
        console.log('Debug Settings Modal: Element not found, DEVMODE likely disabled');
        return; // Exit if modal doesn't exist (DEVMODE disabled)
    }
    
    console.log('Debug Settings Modal: Initializing');
    const debugSettingsContent = document.getElementById('debug-settings-content');
    const debugSettingsTimestamp = document.getElementById('debug-settings-timestamp');
    const copyDebugSettingsBtn = document.getElementById('copy-debug-settings-btn');
    const reloadDebugSettingsBtn = document.getElementById('reload-debug-settings-btn');
    
    // Function to load settings from the API
    async function loadSettings() {
        console.log('Debug Settings Modal: Loading settings...');
        // Show loading state
        debugSettingsContent.textContent = 'Loading settings...';
        
        // Disable reload button during load
        if (reloadDebugSettingsBtn) {
            reloadDebugSettingsBtn.disabled = true;
        }
        
        try {
            console.log('Debug Settings Modal: Fetching /api/settings');
            const response = await fetch('/api/settings');
            console.log('Debug Settings Modal: Received response', response.status, response.statusText);
            
            if (!response.ok) {
                const errorText = `HTTP Error: ${response.status} ${response.statusText}`;
                console.error('Debug Settings Modal:', errorText);
                debugSettingsContent.textContent = errorText;
                return;
            }
            
            const data = await response.json();
            console.log('Debug Settings Modal: Parsed JSON data', data);
            
            if (data.error) {
                console.error('Debug Settings Modal: API returned error:', data.error);
                debugSettingsContent.textContent = `Error: ${data.error}`;
            } else if (!data.settings) {
                console.warn('Debug Settings Modal: data.settings is undefined or null');
                debugSettingsContent.textContent = `Error: No settings object in API response.\n\nRaw API response:\n${JSON.stringify(data, null, 2)}`;
            } else if (Object.keys(data.settings).length === 0) {
                console.warn('Debug Settings Modal: settings object is empty');
                debugSettingsContent.textContent = 'No settings found in database.\n\nThe worker_settings table appears to be empty.\n\nThis could indicate:\n1. Fresh installation (settings not yet initialized)\n2. Database connection issue\n3. Database migration not completed';
            } else {
                // Format the settings as pretty JSON
                console.log('Debug Settings Modal: Successfully loaded', Object.keys(data.settings).length, 'settings');
                const settingsCount = Object.keys(data.settings).length;
                debugSettingsContent.textContent = JSON.stringify(data.settings, null, 2);
                // Update timestamp
                const now = new Date();
                debugSettingsTimestamp.textContent = `Last loaded: ${now.toLocaleString()} (${settingsCount} settings)`;
            }
        } catch (error) {
            console.error('Debug Settings Modal: Exception caught:', error);
            // Show user-friendly error message, full details only in console
            debugSettingsContent.textContent = `Failed to load settings: ${error.message}\n\nPlease check the browser console (F12) for more details.`;
        } finally {
            // Re-enable reload button after load completes (success or failure)
            if (reloadDebugSettingsBtn) {
                reloadDebugSettingsBtn.disabled = false;
            }
        }
    }
    
    // Load settings when modal is shown
    // Use Bootstrap's event listener on the modal element
    if (debugSettingsModal) {
        debugSettingsModal.addEventListener('show.bs.modal', () => {
            console.log('Debug Settings Modal: show.bs.modal event fired');
            loadSettings();
        });
        
        // Also trigger load immediately if DEVMODE users open the page with the modal already visible
        // This handles edge cases where the modal might be pre-opened via URL hash or other means
        if (debugSettingsModal.classList.contains('show')) {
            console.log('Debug Settings Modal: Modal already shown on page load, loading settings');
            loadSettings();
        }
    }
    
    // Reload settings when reload button is clicked
    if (reloadDebugSettingsBtn) {
        reloadDebugSettingsBtn.addEventListener('click', loadSettings);
    }
    
    // Copy to clipboard functionality
    if (copyDebugSettingsBtn) {
        copyDebugSettingsBtn.addEventListener('click', function() {
            const text = debugSettingsContent.textContent;
            navigator.clipboard.writeText(text).then(() => {
                // Visual feedback
                const originalText = copyDebugSettingsBtn.innerHTML;
                copyDebugSettingsBtn.innerHTML = '<span class="mdi mdi-check"></span> Copied!';
                copyDebugSettingsBtn.classList.remove('btn-outline-primary');
                copyDebugSettingsBtn.classList.add('btn-outline-success');
                
                setTimeout(() => {
                    copyDebugSettingsBtn.innerHTML = originalText;
                    copyDebugSettingsBtn.classList.remove('btn-outline-success');
                    copyDebugSettingsBtn.classList.add('btn-outline-primary');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text:', err);
                alert('Failed to copy to clipboard');
            });
        });
    }
}

// Initialize the debug modal - works whether DOM is already loaded or not
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDebugSettingsModal);
} else {
    // DOM is already loaded, run immediately
    initDebugSettingsModal();
}