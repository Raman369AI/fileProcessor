// Email Monitor Dashboard JavaScript

class EmailMonitorDashboard {
    constructor() {
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.loadStatus();
        this.loadResults();
        this.startAutoRefresh();
    }

    async loadStatus() {
        try {
            const response = await fetch('/status');
            const data = await response.json();
            
            this.updateStatusCards(data);
            this.updateConfiguration(data.config);
            this.updateIdempotencyInfo(data.idempotency_info);
            
        } catch (error) {
            console.error('Error loading status:', error);
            this.showError('Failed to load service status');
        }
    }

    updateStatusCards(data) {
        const stats = data.stats;
        
        // Service status
        const statusElement = document.getElementById('service-status');
        statusElement.textContent = data.status;
        statusElement.className = data.status === 'running' ? 'text-success' : 'text-danger';
        
        // Stats
        document.getElementById('total-runs').textContent = stats.total_runs || 0;
        document.getElementById('messages-processed').textContent = stats.messages_processed || 0;
        document.getElementById('attachments-processed').textContent = stats.attachments_processed || 0;
        document.getElementById('error-count').textContent = stats.errors || 0;
        
        // Last run
        const lastRun = stats.last_run ? new Date(stats.last_run).toLocaleString() : 'Never';
        document.getElementById('last-run').textContent = lastRun;
        
        // Error badge color
        const errorBadge = document.getElementById('error-count');
        errorBadge.className = stats.errors > 0 ? 'badge bg-danger' : 'badge bg-success';
    }

    updateConfiguration(config) {
        document.getElementById('email-groups').textContent = 
            config.email_groups && config.email_groups.length > 0 
                ? config.email_groups.join(', ') 
                : 'All emails';
                
        document.getElementById('file-types').textContent = 
            config.file_types && config.file_types.length > 0 
                ? config.file_types.join(', ') 
                : 'All types';
                
        document.getElementById('attachments-dir').textContent = config.attachments_dir || 'email_attachments';
    }

    updateIdempotencyInfo(idempotencyInfo) {
        const deltaStatus = document.getElementById('delta-status');
        if (idempotencyInfo && idempotencyInfo.delta_link_stored) {
            deltaStatus.textContent = 'Active (Delta Sync)';
            deltaStatus.className = 'badge bg-success';
        } else {
            deltaStatus.textContent = 'First Run';
            deltaStatus.className = 'badge bg-warning';
        }
    }

    async loadResults() {
        try {
            const response = await fetch('/recent-results');
            const data = await response.json();
            
            this.displayResults(data.recent_results || []);
            
        } catch (error) {
            console.error('Error loading results:', error);
            this.showError('Failed to load processing results');
        }
    }

    displayResults(results) {
        const container = document.getElementById('results-container');
        
        if (results.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-inbox fa-3x mb-3"></i>
                    <p>No processing results yet. Email monitoring will begin automatically.</p>
                </div>
            `;
            return;
        }

        const resultsHtml = results.map(result => this.createResultCard(result)).join('');
        container.innerHTML = resultsHtml;
    }

    createResultCard(result) {
        const processedDate = new Date(result.processed_date).toLocaleString();
        const attachmentCount = result.attachments_processed || 0;
        
        return `
            <div class="result-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="email-subject mb-2" onclick="showDetails('${result.message_id}')">
                            <i class="fas fa-envelope me-2"></i>
                            ${this.truncateText(result.subject, 80)}
                        </div>
                        <div class="email-meta">
                            <div class="row">
                                <div class="col-md-6">
                                    <small><strong>From:</strong> ${this.truncateText(result.sender, 40)}</small>
                                </div>
                                <div class="col-md-6">
                                    <small><strong>Processed:</strong> ${processedDate}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="text-end">
                        <span class="attachment-count">${attachmentCount}</span>
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary me-1" onclick="showDetails('${result.message_id}')">
                                <i class="fas fa-eye"></i> Details
                            </button>
                            <button class="btn btn-sm btn-outline-success" onclick="showProcessedJson('${result.message_id}')">
                                <i class="fas fa-code"></i> JSON
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    async showDetails(messageId) {
        try {
            const response = await fetch(`/email-details/${messageId}`);
            const data = await response.json();
            
            const modalContent = document.getElementById('modal-content');
            modalContent.innerHTML = this.createDetailsHtml(data);
            
            const modal = new bootstrap.Modal(document.getElementById('detailsModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading details:', error);
            this.showError('Failed to load email details');
        }
    }

    createDetailsHtml(data) {
        if (data.error) {
            return `<div class="alert alert-danger">${data.error}</div>`;
        }

        const emailInfo = data.email_info;
        const attachments = data.attachments || [];

        let attachmentsHtml = '';
        if (attachments.length > 0) {
            attachmentsHtml = attachments.map(att => `
                <div class="card mb-2">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">
                                    <i class="fas fa-paperclip me-2"></i>
                                    ${att.filename}
                                </h6>
                                <small class="text-muted">
                                    Type: ${att.file_type} | Size: ${this.formatFileSize(att.file_size)}
                                </small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary" onclick="showAttachmentJson('${att.filename}', '${emailInfo.message_id}')">
                                <i class="fas fa-code"></i> View JSON
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            attachmentsHtml = '<p class="text-muted">No attachments processed</p>';
        }

        return `
            <div class="email-details">
                <h6><i class="fas fa-envelope me-2"></i>Email Information</h6>
                <table class="table table-sm">
                    <tr><td><strong>Subject:</strong></td><td>${emailInfo.subject}</td></tr>
                    <tr><td><strong>From:</strong></td><td>${emailInfo.sender}</td></tr>
                    <tr><td><strong>Message ID:</strong></td><td><code>${emailInfo.message_id}</code></td></tr>
                    <tr><td><strong>Processed:</strong></td><td>${new Date(emailInfo.processed_date).toLocaleString()}</td></tr>
                </table>
                
                <h6 class="mt-4"><i class="fas fa-paperclip me-2"></i>Attachments (${attachments.length})</h6>
                ${attachmentsHtml}
            </div>
        `;
    }

    async showProcessedJson(messageId) {
        try {
            const response = await fetch(`/email-json/${messageId}`);
            const data = await response.json();
            
            const jsonContent = document.getElementById('json-content');
            jsonContent.textContent = JSON.stringify(data, null, 2);
            
            const modal = new bootstrap.Modal(document.getElementById('jsonModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading JSON:', error);
            this.showError('Failed to load processing JSON');
        }
    }

    async showAttachmentJson(filename, messageId) {
        try {
            const response = await fetch(`/attachment-json/${messageId}/${encodeURIComponent(filename)}`);
            const data = await response.json();
            
            const jsonContent = document.getElementById('json-content');
            jsonContent.textContent = JSON.stringify(data, null, 2);
            
            // Update modal title
            document.querySelector('#jsonModal .modal-title').textContent = `JSON: ${filename}`;
            
            const modal = new bootstrap.Modal(document.getElementById('jsonModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading attachment JSON:', error);
            this.showError('Failed to load attachment JSON');
        }
    }

    async triggerProcessing() {
        try {
            const button = event.target.closest('button');
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Processing...';
            button.disabled = true;
            
            const response = await fetch('/process-now', { method: 'POST' });
            const data = await response.json();
            
            // Show success message
            this.showSuccess(data.message || 'Processing triggered successfully');
            
            // Refresh data after a short delay
            setTimeout(() => {
                this.loadStatus();
                this.loadResults();
            }, 2000);
            
        } catch (error) {
            console.error('Error triggering processing:', error);
            this.showError('Failed to trigger processing');
        } finally {
            // Reset button
            setTimeout(() => {
                const button = document.querySelector('button[onclick="triggerProcessing()"]');
                if (button) {
                    button.innerHTML = '<i class="fas fa-play me-1"></i>Process Now';
                    button.disabled = false;
                }
            }, 1000);
        }
    }

    refreshResults() {
        this.loadStatus();
        this.loadResults();
    }

    startAutoRefresh() {
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.loadStatus();
            this.loadResults();
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    truncateText(text, maxLength) {
        if (!text) return 'N/A';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1100';
            document.body.appendChild(toastContainer);
        }

        // Create toast
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Show toast
        const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
        bsToast.show();

        // Remove from DOM after hiding
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
}

// Global functions for onclick handlers
function triggerProcessing() {
    dashboard.triggerProcessing();
}

function refreshResults() {
    dashboard.refreshResults();
}

function showDetails(messageId) {
    dashboard.showDetails(messageId);
}

function showProcessedJson(messageId) {
    dashboard.showProcessedJson(messageId);
}

function showAttachmentJson(filename, messageId) {
    dashboard.showAttachmentJson(filename, messageId);
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', function() {
    dashboard = new EmailMonitorDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (dashboard) {
        dashboard.stopAutoRefresh();
    }
});