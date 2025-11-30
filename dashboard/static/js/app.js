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

    // Show scan buttons, hide cancel buttons for Sonarr
    if(sonarrRenameScanButton) sonarrRenameScanButton.style.display = 'inline-block';
    if(sonarrRenameScanButton) sonarrRenameScanButton.disabled = false;
    if(sonarrQualityScanButton) sonarrQualityScanButton.disabled = false;
    if(sonarrQualityScanButton) sonarrQualityScanButton.style.display = 'inline-block';
    if(sonarrCancelScanButton) sonarrCancelScanButton.style.display = 'none';

    // Show scan buttons, hide cancel buttons for Radarr
    if(radarrRenameScanButton) radarrRenameScanButton.style.display = 'inline-block';
    if(radarrRenameScanButton) radarrRenameScanButton.disabled = false;
    if(radarrCancelScanButton) radarrCancelScanButton.style.display = 'none';

    // Show scan buttons, hide cancel buttons for Lidarr
    if(lidarrRenameScanButton) lidarrRenameScanButton.style.display = 'inline-block';
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
                if(timeEl) timeEl.textContent = `Elapsed: ${elapsedSeconds}s`;

                if (data.is_running) {
                    const progressPercent = data.total_steps > 0 ? ((data.progress / data.total_steps) * 100).toFixed(1) : 0;
                    if (progressBarEl) progressBarEl.style.width = `${progressPercent}%`;
                    if (progressBarEl) progressBarEl.textContent = `${progressPercent}%`;
                    if (progressTextEl) progressTextEl.textContent = data.current_step || 'Scanning...';
                } else {
                    // Scan finished
                    stopProgressPolling();
                    if (progressBarEl) progressBarEl.style.width = '100%';
                    if (progressBarEl) progressBarEl.textContent = '100%';
                    if (progressTextEl) progressTextEl.textContent = 'Scan complete.';
                    showScanFeedback(data.current_step || 'Scan finished.', 'success', scanType, scanSource);
                    setTimeout(resetScanUI, 5000);
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
            
            // Hide all scan buttons, show appropriate cancel button
            if (sonarrRenameScanButton) sonarrRenameScanButton.style.display = 'none';
            if (sonarrQualityScanButton) sonarrQualityScanButton.style.display = 'none';
            if (radarrRenameScanButton) radarrRenameScanButton.style.display = 'none';
            if (lidarrRenameScanButton) lidarrRenameScanButton.style.display = 'none';
            
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
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', activeScanType, activeScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', activeScanType, activeScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', activeScanType, activeScanSource);
        }
    });
}

if (radarrCancelScanButton) {
    radarrCancelScanButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', activeScanType, activeScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', activeScanType, activeScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', activeScanType, activeScanSource);
        }
    });
}

if (lidarrCancelScanButton) {
    lidarrCancelScanButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/scan/cancel', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showScanFeedback('Scan cancellation requested.', 'warning', activeScanType, activeScanSource);
                resetScanUI();
            } else {
                showScanFeedback('Failed to send cancellation signal.', 'danger', activeScanType, activeScanSource);
            }
        } catch (error) {
            showScanFeedback('Error sending cancellation signal.', 'danger', activeScanType, activeScanSource);
        }
    });
}

// On page load, check if a scan is already running and resume polling
fetch('/api/scan/progress').then(r => r.json()).then(data => {
    if (data.is_running) {
        // This is a bit tricky since we don't know which scan type was running.
        // We can make an educated guess or just default to one.
        // For now, let's just log it. A more advanced implementation could store the activeScanType.
        console.log("A scan was already in progress on page load. Polling will not resume automatically without knowing the type.");
        // Or, we could try to infer from the 'current_step' message.
        let runningScanType = 'rename'; // default
        let runningScanSource = 'sonarr'; // default
        if (data.current_step) {
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
        handleScanButtonClick(runningScanType, runningScanSource); // This will effectively resume the UI state
    }
});

// Function to create an HTML element for a single node
function createNodeCard(node) {
    const isIdle = node.status === 'idle' || node.percent === 0;
    return `
    <div class="card mb-3">
        <div id="node-${node.hostname}" class="card-header fs-5 d-flex justify-content-between align-items-center">
            <span>
                <span class="health-icon me-2" title="Calculating...">●</span>${node.hostname}
                ${node.version_mismatch ? `<strong class="text-warning ms-3">** Version Mismatch **</strong>` : ''}
            </span>
            <div>
                <button class="btn btn-sm btn-outline-secondary me-2" onclick="showNodeOptions('${node.hostname}')">Options</button>
                <button class="btn btn-sm btn-success" onclick="startNode('${node.hostname}')" ${node.status === 'running' || node.status === 'paused' ? 'disabled' : ''}>Start</button>
                <button class="btn btn-sm btn-danger" onclick="stopNode('${node.hostname}')" ${node.status === 'idle' || node.status === 'finishing' ? 'disabled' : ''}>Stop</button>
                <button class="btn btn-sm btn-warning" onclick="pauseResumeNode('${node.hostname}', '${node.status}')" ${node.status === 'idle' ? 'disabled' : ''}>${node.status === 'paused' ? 'Resume' : 'Pause'}</button>
                <span class="badge ${node.version_mismatch ? 'bg-danger' : 'bg-info'}">${node.version || 'N/A'}</span>
            </div>
        </div>
        <div class="card-body">
            ${node.percent > 0 ? `
                <p class="card-text text-body-secondary mb-2" style="font-family: monospace;">${node.current_file || 'N/A'}</p>
                <div class="progress" role="progressbar">
                    <div class="progress-bar progress-bar-striped progress-bar-animated text-bg-${node.color}" style="width: ${node.percent}%">
                        <b>${node.percent}%</b>
                    </div>
                </div>
            ` : `
                <div class="text-center p-3">
                    <h5 class="card-title text-muted">${node.status === 'paused' ? 'Paused' : (node.status === 'finishing' ? 'Finishing...' : (node.current_file || 'Idle'))}</h5>
                </div>
            `}
        </div>
        <div class="card-footer d-flex justify-content-between align-items-center bg-transparent">
            <span class="text-muted small">Uptime: ${node.uptime_str || 'N/A'}</span>
            <div>
            ${node.percent > 0 ? `
                <span class="badge text-bg-secondary me-2">FPS: ${node.fps || 'N/A'}</span>
                <span class="badge text-bg-secondary me-2">Speed: ${node.speed}x</span>
                <span class="badge text-bg-${node.color}">Codec: ${node.codec}</span>
            ` : `
                <span class="badge text-bg-secondary">${node.status === 'paused' ? 'Paused' : (node.current_file || 'Idle')}</span>
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
        viewErrorsBtn.classList.remove('btn-danger', 'btn-success', 'btn-warning');
        const clearErrorsBtn = document.getElementById('clear-errors-btn');
        clearErrorsBtn.style.display = (failCount > 0) ? 'inline-block' : 'none';

        // If there are errors, the button is always red.
        if (failCount > 0) {
            viewErrorsBtn.classList.add('btn-danger');
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
            pauseQueueBtn.classList.remove('btn-warning');
            pauseQueueBtn.classList.add('btn-success');
            pauseQueueBtn.innerHTML = `<span class="mdi mdi-play"></span> Resume Queue`;
            pauseQueueBtn.title = "Resume the distribution of new jobs to workers";
        } else {
            pauseQueueBtn.classList.remove('btn-success');
            pauseQueueBtn.classList.add('btn-warning');
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
document.getElementById('view-errors-btn').addEventListener('click', async () => {
    const tableBody = document.getElementById('failures-table-body');
    tableBody.innerHTML = '<tr><td colspan="4" class="text-center">Loading...</td></tr>';
    try {
        const response = await fetch('/api/failures');
        const data = await response.json();
        if (data.files && data.files.length > 0) {
            tableBody.innerHTML = data.files.map((file, index) => `
                <tr>
                    <td style="word-break: break-all;">${file.filename}</td>
                    <td>${file.reason}</td>
                    <td>${file.reported_at}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-log-${index}">
                            View Log
                        </button>
                    </td>
                </tr>
                <tr class="collapse" id="collapse-log-${index}">
                    <td colspan="4"><pre class="bg-dark text-white-50 p-3 rounded" style="max-height: 300px; overflow-y: auto;">${file.log || 'No log available.'}</pre></td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = '<tr><td colspan="3" class="text-center">No failed files found.</td></tr>';
        }
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Failed to load errors.</td></tr>';
    }
});

// Function to clear all failures
document.getElementById('clear-errors-btn').addEventListener('click', async () => {
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
});

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
                    <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: ${progressPercent}%" aria-valuenow="${progressPercent}" aria-valuemin="0" aria-valuemax="100">${progressPercent}%</div>
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
        hour12: !window.CodecShift.settings.use24HourClock
    };
    const timeString = new Date().toLocaleTimeString([], timeOptions);
    if (clockContainer) clockContainer.innerHTML = `<span class="badge text-bg-secondary fs-6">Updated: ${timeString}</span>`;
}, 1000); // Runs every second.

// 2. A separate, independent loop for polling scan progress so it doesn't block other updates.
setInterval(() => { if (isPollingForScan) pollScanProgress(); }, 1000); // Polls every second

// Run initial update on page load
updateStatus();

// Initialize all tooltips on the page after the DOM is ready
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
});

// Function to clear all history
document.getElementById('clear-history-btn').addEventListener('click', async () => {
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

// Function to update the job queue
let jobQueueCurrentPage = 1; // Keep track of the current page
async function updateJobQueue(page = 1) {
    jobQueueCurrentPage = page;
    try {
        const response = await fetch(`/api/jobs?page=${page}`);
        const data = await response.json();
        const tableBody = document.getElementById('job-queue-table-body');
        tableBody.innerHTML = ''; // Clear existing rows

        if (data.db_error) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-danger">Database Error: ${data.db_error}</td></tr>`;
            return;
        }

        if (data.jobs.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No jobs in the queue.</td></tr>';
            return;
        }

        // Build the entire table HTML at once and set it. This is much more efficient
        // and prevents the "ghost row" rendering bug.
        const rowsHtml = data.jobs.map(job => `
            <tr>
                <td>
                    ${(job.job_type === 'cleanup' || job.job_type === 'Rename Job') && job.status === 'awaiting_approval' ? 
                        `<input type="checkbox" class="form-check-input approval-checkbox" data-job-id="${job.id}">` : 
                        job.id 
                    }
                </td>
                <td style="word-break: break-all;">${job.filepath}</td>
                <td><span class="badge bg-info text-dark">${job.job_type}</span></td>
                <td>
                    ${job.status === 'encoding' ? 
                        `<span class="badge text-bg-primary"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Encoding</span>` :
                    job.status === 'awaiting_approval' ?
                        `<span class="badge text-bg-warning">Awaiting Approval</span>` :
                    job.status === 'pending' ?
                        `<span class="badge text-bg-secondary">Pending</span>` :
                    job.status === 'failed' ?
                        `<span class="badge text-bg-danger">Failed</span>` :
                    job.status === 'completed' ?
                        `<span class="badge text-bg-success">Completed</span>` :
                        `<span class="badge text-bg-warning">${job.status}</span>`
                    }
                </td>
                <td>${job.assigned_to || 'N/A'}</td>
                <td>${new Date(job.created_at).toLocaleString()}</td>
                <td>
                    ${['pending', 'awaiting_approval', 'failed'].includes(job.status) ?
                        `<button class="btn btn-xs btn-outline-danger" onclick="deleteJob(${job.id})" title="Delete Job">&times;</button>` :
                        ''
                    }
                    ${job.status === 'encoding' && job.age_minutes > 10 ?
                        `<button class="btn btn-xs btn-danger" onclick="deleteJob(${job.id})" title="Force Remove Stuck Job">Force Remove</button>` :
                        ''
                    }
                </td>
            </tr>
        `).join('');
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
document.getElementById('create-cleanup-jobs-btn').addEventListener('click', async () => {
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

// --- History & Stats Page Logic ---
let fullHistoryData = [];
let historyCurrentPage = 1;
const historyItemsPerPage = 15;

// Combined function to fetch and display stats and history
async function updateHistoryAndStats() {
    const statsCardsContainer = document.getElementById('stats-cards-container');
    const historyBody = document.getElementById('history-table-body');

    try {
        // Fetch both stats and history in parallel
        const [statsResponse, historyResponse] = await Promise.all([
            fetch('/api/stats'),
            fetch('/api/history')
        ]);

        // Process Stats
        const statsData = await statsResponse.json();
        const reductionPercent = parseFloat(statsData.stats.total_reduction_percent);
        let reductionColorClass = 'bg-success';
        if (reductionPercent < 50) {
            reductionColorClass = 'bg-danger';
        } else if (reductionPercent < 75) {
            reductionColorClass = 'bg-warning text-dark'; // Add text-dark for better contrast on yellow
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
            <div class="col-md-3"><div class="card ${reductionColorClass}"><div class="card-body">
                <h5 class="card-title">${statsData.stats.total_reduction_percent}%</h5><p class="card-text">Average Reduction</p>
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

// Function to render the history table with search and pagination
function renderHistoryTable() {
    const historyBody = document.getElementById('history-table-body');
    const paginationContainer = document.getElementById('history-pagination');
    const searchTerm = document.getElementById('history-search-input').value.toLowerCase();

    const filteredData = fullHistoryData.filter(item => 
        item.filename.toLowerCase().includes(searchTerm) ||
        item.hostname.toLowerCase().includes(searchTerm)
    );

    const totalPages = Math.ceil(filteredData.length / historyItemsPerPage);
    if (historyCurrentPage > totalPages) {
        historyCurrentPage = totalPages || 1;
    }
    const startIndex = (historyCurrentPage - 1) * historyItemsPerPage;
    const paginatedData = filteredData.slice(startIndex, startIndex + historyItemsPerPage);

    // Render table rows
    if (paginatedData.length > 0) {
        historyBody.innerHTML = paginatedData.map(item => `
            <tr>
                <td>${item.id}</td>
                <td style="word-break: break-all;">${item.filename}</td>
                <td>${item.hostname}</td>
                <td><span class="badge text-bg-secondary">${item.codec}</span></td>
                ${item.status === 'encoding' ? `
                    <td colspan="2" class="text-center"><span class="badge text-bg-primary">In Progress</span></td>
                ` : `
                    <td>${item.original_size_gb} → ${item.new_size_gb}</td>
                    <td><span class="badge text-bg-success">${item.reduction_percent}%</span></td>
                `}
                <td>${item.encoded_at}</td>
                <td><button class="btn btn-xs btn-outline-danger" title="Delete this entry">&times;</button></td>
            </tr>
        `).join('');
    } else {
        historyBody.innerHTML = `<tr><td colspan="7" class="text-center">${searchTerm ? 'No matching files found.' : 'No encoded files found.'}</td></tr>`;
    }

    // Render pagination
    paginationContainer.innerHTML = '';
    if (totalPages > 1) {
        for (let i = 1; i <= totalPages; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === historyCurrentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.addEventListener('click', (e) => {
                e.preventDefault();
                historyCurrentPage = i;
                renderHistoryTable();
            });
            paginationContainer.appendChild(li);
        }
    }
}

// Event listener for the search input
document.getElementById('history-search-input').addEventListener('input', () => {
    historyCurrentPage = 1; // Reset to first page on search
    renderHistoryTable();
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
    updateJobQueue();
});

// Load *arr stats when Tools tab is shown
const toolsTab = document.querySelector('#tools-tab');
toolsTab.addEventListener('shown.bs.tab', () => {
    loadArrStats();
});

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
async function pauseResumeNode(hostname, currentStatus) {
    const action = currentStatus === 'paused' ? 'resume' : 'pause';
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

    if (mainTabs && advancedSwitchContainer) {
        mainTabs.addEventListener('shown.bs.tab', function (event) {
            if (event.target.id === 'options-tab') {
                advancedSwitchContainer.classList.remove('d-none');
            } else {
                advancedSwitchContainer.classList.add('d-none');
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
            window.CodecShift.settings.use24HourClock = event.target.checked;
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
    const plexLogoutBtn = document.getElementById('plex-logout-btn');
    const plexSignInBtn = document.getElementById('plex-signin-btn');

    if (plexLoginBtn) {
        plexLoginBtn.addEventListener('click', () => {
            const loginModal = new bootstrap.Modal(document.getElementById('plexLoginModal'));
            loginModal.show();
        });
    }

    if (plexSignInBtn) {
        plexSignInBtn.addEventListener('click', async () => {
            const usernameInput = document.getElementById('plex-username');
            const passwordInput = document.getElementById('plex-password');
            const urlInput = document.getElementById('plex_url'); // Get the URL input
            const statusDiv = document.getElementById('plex-login-status');
            statusDiv.innerHTML = `<div class="spinner-border spinner-border-sm"></div> Signing in...`;

            const response = await fetch('/api/plex/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username: usernameInput.value, 
                    password: passwordInput.value,
                    plex_url: urlInput.value // Send the URL along with credentials
                })
            });
            const data = await response.json();
            if (data.success) {
                statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                setTimeout(() => window.location.href = '/#options-tab-pane', 1500);
            } else {
                statusDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            }
        });
    }

    if (plexLogoutBtn) {
        plexLogoutBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to unlink your Plex account?')) {
                await fetch('/api/plex/logout', { method: 'POST' });
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

        const applyVisibility = () => {
            if (!listContainer) return;
            const showIgnored = toggle.checked;
            listContainer.querySelectorAll('.media-source-item').forEach(item => {
                // Check if the media type dropdown is set to "none" (ignored)
                const typeDropdown = item.querySelector('select');
                const isIgnored = typeDropdown ? typeDropdown.value === 'none' : false;
                
                if (isIgnored && !showIgnored) {
                    item.style.display = 'none';
                } else {
                    item.style.display = 'flex';
                }
            });
        };

        toggle.addEventListener('change', applyVisibility);

        // Also listen for changes on any of the dropdown selects within the list
        listContainer.addEventListener('change', (e) => {
            if (e.target.matches('select')) {
                applyVisibility();
            }
        });

        // Return the function so it can be called after loading to set the initial state
        return applyVisibility;
    }
    const applyPlexVisibility = setupShowIgnoredToggle('plex-show-hidden-toggle', 'plex-libraries-list');
    const applyInternalVisibility = setupShowIgnoredToggle('internal-show-hidden-toggle', 'internal-folders-list');

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
        const hasToken = window.CodecShift.settings.plexToken !== "";

        if (!hasToken) {
            container.innerHTML = `<p class="text-muted">Enter your Plex Server URL and link your account to see libraries.</p>`;
            return;
        }

        const response = await fetch('/api/plex/libraries');
        const data = await response.json();
        const currentLibs = window.CodecShift.settings.plexLibraries;

        if (data.libraries && data.libraries.length > 0) {
            container.innerHTML = data.libraries.map(lib => `
                <div class="d-flex align-items-center mb-2 media-source-item">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" name="plex_libraries" value="${lib.title}" id="lib-${lib.key}" ${currentLibs.includes(lib.title) ? 'checked' : ''}>
                        <label class="form-check-label" for="lib-${lib.key}">${lib.title}</label>
                    </div>
                    <div class="ms-auto d-flex align-items-center me-2">
                        ${createDropdown(`type_plex_${lib.title}`, lib.plex_type, lib.type)}
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `<p class="text-muted">${data.error || 'No video libraries found.'}</p>`;
        }

        // Apply the initial visibility based on the toggle's state
        if (typeof applyPlexVisibility === 'function') {
            applyPlexVisibility();
        }
    }
    if (document.getElementById('plex-libraries-container').style.display !== 'none') {
        loadPlexLibraries();
    }

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
        const currentPaths = window.CodecShift.settings.internalScanPaths;

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
    internalTab.addEventListener('shown.bs.tab', () => {
        loadInternalFolders();
    });

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
        const hasPlexToken = window.CodecShift.settings.plexToken !== "";
        if (scannerPlexRadio.checked && !hasPlexToken) {
            manualScanBtn.disabled = true;
            manualScanBtn.title = "Plex account must be linked to run a scan.";
        } else {
            manualScanBtn.disabled = false;
            manualScanBtn.title = "Trigger a manual scan of the active media integration";
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

    // --- Manual Plex Scan Logic ---
    const manualScanBtn = document.getElementById('manual-scan-btn');
    const scanStatusDiv = document.getElementById('scan-status');
    const forceRescanCheckbox = document.getElementById('force-rescan-checkbox');

    manualScanBtn.addEventListener('click', async () => {
        manualScanBtn.disabled = true;
        manualScanBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Scanning...`;
        scanStatusDiv.innerHTML = '';
        const isForced = forceRescanCheckbox.checked;

        try {
            const response = await fetch('/api/scan/trigger', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ force: isForced }) });
            const data = await response.json();
            const alertClass = data.success ? 'alert-success' : 'alert-warning';
            scanStatusDiv.innerHTML = `<div class="alert ${alertClass} alert-dismissible fade show" role="alert">${data.message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
            // Refresh the job queue to show any newly added jobs
            updateJobQueue();
        } catch (error) {
            scanStatusDiv.innerHTML = `<div class="alert alert-danger alert-dismissible fade show" role="alert">Error communicating with the server.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
        } finally {
            manualScanBtn.disabled = false;
            manualScanBtn.innerHTML = `<span class="mdi mdi-sync"></span> Manual Scan`;
        }
    });

    // --- Sonarr Options Logic ---
    const sendToQueueSwitch = document.getElementById('sonarr_send_to_queue');
    const sonarrStatusDiv = document.getElementById('sonarr-test-status');
    const rescanValueSpan = document.getElementById('sonarr-rescan-value');

    // This element might not exist if the user has old settings, so check for it.
    const sonarrRescanSlider = document.getElementById('sonarr_rescan_hours');
    if (sonarrRescanSlider) {
        sonarrRescanSlider.addEventListener('input', (event) => { rescanValueSpan.textContent = event.target.value; });
    }

    // --- *Arr Integration Enable/Disable Logic ---
    function setupArrToggle(arrType) {
        const enableToggle = document.getElementById(`${arrType}_enabled`);
        const integrationPane = document.getElementById(`${arrType}-integration-pane`);
        if (!enableToggle || !integrationPane) return;

        const inputs = integrationPane.querySelectorAll('input:not([type=checkbox]), select, button, input[type=range]');

        function updateInputsState() {
            inputs.forEach(input => {
                if (input.id !== `${arrType}_enabled`) input.disabled = !enableToggle.checked;
            });
            // Special handling for Sonarr tools
            if (arrType === 'sonarr') {
                const renameBtn = document.getElementById('sonarr-rename-scan-button');
                const qualityBtn = document.getElementById('sonarr-quality-scan-button');
                if (renameBtn && qualityBtn) [renameBtn, qualityBtn].forEach(btn => btn.disabled = !enableToggle.checked);
            }
        }
        enableToggle.addEventListener('change', updateInputsState);
        updateInputsState(); // Set initial state on page load
    }
    ['sonarr', 'radarr', 'lidarr'].forEach(setupArrToggle);

    const releaseSelectedBtn = document.getElementById('release-selected-btn');
    const releaseAllCleanupBtn = document.getElementById('release-all-cleanup-btn');
    const releaseAllRenameBtn = document.getElementById('release-all-rename-btn');

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

    releaseAllCleanupBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to release ALL cleanup jobs that are awaiting approval?')) {
            await releaseJobs({ release_all: true, job_type: 'cleanup' });
        }
    });

    releaseAllRenameBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to release ALL rename jobs that are awaiting approval? They will be processed automatically.')) {
            await releaseJobs({ release_all: true, job_type: 'Rename Job' });
        }
    });

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
    clearJobsBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to permanently clear the entire job queue? This action cannot be undone.')) {
            return;
        }
        try {
            const response = await fetch('/api/jobs/clear', { method: 'POST' });
            if (response.ok) {
                updateJobQueue(1); // Refresh the queue to show it's empty
            }
        } catch (error) {
            alert('An error occurred while trying to clear the job queue.');
        }
    });

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

    // --- Pause Queue Button Logic ---
    const pauseQueueBtn = document.getElementById('pause-queue-btn');
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
        return theme;
    };

    const setTheme = theme => {
        // Resolve 'auto' to actual theme for Bootstrap
        const resolvedTheme = getResolvedTheme(theme);
        document.documentElement.setAttribute('data-bs-theme', resolvedTheme);
        
        // Update icon based on stored theme (not resolved) to show user's selection
        if (theme === 'dark') themeIcon.className = 'mdi mdi-weather-night';
        else if (theme === 'light') themeIcon.className = 'mdi mdi-weather-sunny';
        else themeIcon.className = 'mdi mdi-desktop-classic';
    };

    setTheme(getStoredTheme() || 'dark'); // Set initial theme

    document.querySelectorAll('[data-theme-value]').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const theme = toggle.getAttribute('data-theme-value');
            setStoredTheme(theme);
            setTheme(theme);
        });
    });
})();

// --- Changelog Modal Logic ---
document.addEventListener('DOMContentLoaded', () => {
    const changelogModal = document.getElementById('changelogModal');
    const changelogContent = document.getElementById('changelog-content');
    const versionToggle = document.getElementById('changelog-version-toggle');

    const converter = new showdown.Converter({ simplifiedAutoLink: true, openLinksInNewWindow: true });

    async function determineAndLoadChangelog() {
        const internalVersion = window.CodecShift.version;
        const mainVersionUrl = "https://raw.githubusercontent.com/m1ckyb/CodecShift/refs/heads/main/VERSION.txt";

        try {
            const response = await fetch(mainVersionUrl);
            const latestStableVersion = await response.text().trim();

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

    async function loadChangelog() {
        const isDevelop = versionToggle.checked;
        const branch = isDevelop ? 'develop' : 'main';
        const url = `https://raw.githubusercontent.com/m1ckyb/CodecShift/refs/heads/${branch}/CHANGELOG.md`;

        changelogContent.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const markdown = await response.text();
            const html = converter.makeHtml(markdown);
            changelogContent.innerHTML = html;
        } catch (error) {
            console.error('Error fetching changelog:', error);
            changelogContent.innerHTML = '<div class="alert alert-danger">Failed to load changelog. Please check your internet connection.</div>';
        }
    }

    // Load content when the modal is shown
    changelogModal.addEventListener('show.bs.modal', determineAndLoadChangelog);

    // Reload content when the toggle is switched
    versionToggle.addEventListener('change', loadChangelog);
});