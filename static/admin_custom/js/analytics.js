/**
 * Analytics Dashboard JavaScript Utilities
 */

// Utility: Format number with thousands separator
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

// Utility: Format currency
function formatCurrency(num) {
    return formatNumber(Math.round(num)) + ' ₽';
}

// Utility: Get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Auto-refresh dashboard data (optional)
let refreshInterval = null;

function enableAutoRefresh(intervalMinutes = 5) {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(() => {
        console.log('Auto-refreshing dashboard data...');
        refreshDashboardData();
    }, intervalMinutes * 60 * 1000);
}

function disableAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Refresh dashboard data via API
async function refreshDashboardData() {
    const params = new URLSearchParams(window.location.search);
    const period = params.get('period') || '30days';

    try {
        const response = await fetch(`/admin-panel/api/dashboard-stats/?period=${period}`, {
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch dashboard stats');
        }

        const data = await response.json();
        updateDashboard(data);

    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

// Update dashboard with new data
function updateDashboard(data) {
    // This function can be expanded to update specific metrics
    // without full page reload
    console.log('Dashboard data updated:', data);

    // Example: Update metric values
    // document.querySelector('.total-revenue').textContent = formatCurrency(data.financial.total_revenue);
}

// Export current view as image (optional feature)
async function exportDashboardAsImage() {
    // Requires html2canvas library
    if (typeof html2canvas === 'undefined') {
        alert('Export feature requires html2canvas library');
        return;
    }

    const dashboard = document.querySelector('.analytics-dashboard');
    const canvas = await html2canvas(dashboard);

    const link = document.createElement('a');
    link.download = `dashboard-${new Date().toISOString().split('T')[0]}.png`;
    link.href = canvas.toDataURL();
    link.click();
}

// Print dashboard
function printDashboard() {
    window.print();
}

// Initialize tooltips (if using a tooltip library)
function initTooltips() {
    // Example: Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Document ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Analytics dashboard loaded');

    // Initialize any tooltips
    // initTooltips();

    // Optional: Enable auto-refresh (disabled by default)
    // enableAutoRefresh(5); // Refresh every 5 minutes
});

// Export functions for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatNumber,
        formatCurrency,
        getCookie,
        refreshDashboardData,
        enableAutoRefresh,
        disableAutoRefresh
    };
}
