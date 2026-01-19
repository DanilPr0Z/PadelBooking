/**
 * Schedule JavaScript Utilities
 * Additional helpers for calendar management
 */

// User search with debounce
let userSearchTimeout;
let selectedUsers = [];

function setupUserSearch() {
    const searchInput = document.getElementById('searchUser');
    const suggestionsDiv = document.getElementById('userSuggestions');
    const userIdInput = document.getElementById('userId');

    if (!searchInput) return;

    searchInput.addEventListener('input', function(e) {
        const query = e.target.value.trim();

        clearTimeout(userSearchTimeout);

        if (query.length < 2) {
            suggestionsDiv.classList.remove('active');
            return;
        }

        userSearchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/admin-panel/api/users/search/?q=${encodeURIComponent(query)}`);
                const data = await response.json();

                displayUserSuggestions(data.users || [], suggestionsDiv, searchInput, userIdInput);
            } catch (error) {
                console.error('Error searching users:', error);
                displayUserSuggestions([], suggestionsDiv, searchInput, userIdInput);
            }
        }, 300);
    });

    // Close suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!suggestionsDiv.contains(e.target) && e.target !== searchInput) {
            suggestionsDiv.classList.remove('active');
        }
    });
}

function displayUserSuggestions(users, container, searchInput, userIdInput) {
    if (users.length === 0) {
        container.innerHTML = '<div class="suggestion-item" style="color: #9ca3af;">Пользователи не найдены</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = users.map(user => `
        <div class="suggestion-item" data-user-id="${user.id}" data-user-name="${user.name}">
            <div style="font-weight: 500;">${user.name}</div>
            <div style="font-size: 12px; color: #6b7280;">${user.email}</div>
        </div>
    `).join('');

    container.classList.add('active');

    // Add click handlers
    container.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', function() {
            const userId = this.dataset.userId;
            const userName = this.dataset.userName;

            if (userId && userName) {
                searchInput.value = userName;
                userIdInput.value = userId;
                container.classList.remove('active');
            }
        });
    });
}

// Validate booking time
function validateBookingTime(startTime, endTime) {
    const start = new Date(`1970-01-01T${startTime}`);
    const end = new Date(`1970-01-01T${endTime}`);

    if (end <= start) {
        return { valid: false, error: 'Время окончания должно быть позже времени начала' };
    }

    const duration = (end - start) / (1000 * 60 * 60); // hours

    if (duration < 0.5) {
        return { valid: false, error: 'Минимальная длительность бронирования - 30 минут' };
    }

    if (duration > 4) {
        return { valid: false, error: 'Максимальная длительность бронирования - 4 часа' };
    }

    return { valid: true };
}

// Format date for display
function formatDate(date) {
    return new Date(date).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

// Format time for display
function formatTime(date) {
    return new Date(date).toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Calculate booking duration
function calculateDuration(startTime, endTime) {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const hours = (end - start) / (1000 * 60 * 60);
    return hours;
}

// Calculate booking price
function calculatePrice(courtId, duration) {
    // TODO: Get actual court prices from backend
    // For now, use a default price
    const pricePerHour = 1000; // Default price
    return pricePerHour * duration;
}

// Export calendar to PDF (requires additional library)
async function exportCalendarToPDF() {
    // This would require html2pdf or similar library
    alert('Экспорт в PDF будет доступен в следующей версии');
}

// Print calendar view
function printCalendar() {
    window.print();
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + N - New booking
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        openQuickCreateModal();
    }

    // Escape - Close modal
    if (e.key === 'Escape') {
        closeQuickCreateModal();
        closeDetailsModal();
    }

    // Ctrl/Cmd + R - Refresh
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        refreshCalendar();
    }
});

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    setupUserSearch();

    // Add form validation
    const quickCreateForm = document.getElementById('quickCreateForm');
    if (quickCreateForm) {
        quickCreateForm.addEventListener('submit', function(e) {
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;

            const validation = validateBookingTime(startTime, endTime);
            if (!validation.valid) {
                e.preventDefault();
                showToast(validation.error, 'error');
            }
        });
    }

    console.log('Schedule utilities initialized');
});

// Export functions for use in templates
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        validateBookingTime,
        formatDate,
        formatTime,
        calculateDuration,
        calculatePrice
    };
}
