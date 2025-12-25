// static/js/notifications.js
function showNotification(message, type = 'success') {
    // Удаляем предыдущие уведомления
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    // Создаем уведомление
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;

    const icon = type === 'success' ? '✓' :
                 type === 'error' ? '✗' :
                 type === 'warning' ? '⚠' : 'ℹ';

    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-icon">${icon}</span>
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        </div>
    `;

    // Добавляем в DOM
    document.body.appendChild(notification);

    // Анимация появления
    setTimeout(() => notification.classList.add('show'), 10);

    // Кнопка закрытия
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    });

    // Автоматическое закрытие
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// CSS для уведомлений (добавить в base.html)
const notificationStyles = `
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 300px;
    max-width: 400px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.15);
    transform: translateX(400px);
    opacity: 0;
    transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.notification.show {
    transform: translateX(0);
    opacity: 1;
}

.notification-content {
    display: flex;
    align-items: center;
    padding: 16px 20px;
    gap: 12px;
}

.notification-icon {
    font-size: 20px;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    flex-shrink: 0;
}

.notification-success .notification-icon {
    background: rgba(76, 175, 80, 0.1);
    color: #4caf50;
}

.notification-error .notification-icon {
    background: rgba(244, 67, 54, 0.1);
    color: #f44336;
}

.notification-warning .notification-icon {
    background: rgba(255, 152, 0, 0.1);
    color: #ff9800;
}

.notification-info .notification-icon {
    background: rgba(33, 150, 243, 0.1);
    color: #2196f3;
}

.notification-message {
    flex: 1;
    font-size: 14px;
    line-height: 1.4;
    color: #333;
}

.notification-close {
    background: none;
    border: none;
    font-size: 20px;
    color: #999;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.2s;
}

.notification-close:hover {
    background: rgba(0, 0, 0, 0.05);
    color: #333;
}
`;

// Добавить стили в head
const styleSheet = document.createElement('style');
styleSheet.textContent = notificationStyles;
document.head.appendChild(styleSheet);