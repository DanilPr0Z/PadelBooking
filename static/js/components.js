/**
 * Библиотека переиспользуемых UI компонентов
 */

// ==================== TOAST NOTIFICATIONS ====================
class ToastNotification {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Создаем контейнер для toast-ов если его нет
        if (!document.querySelector('.toast-container')) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.querySelector('.toast-container');
        }
    }

    show(message, type = 'success', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const titles = {
            success: 'Успешно!',
            error: 'Ошибка!',
            warning: 'Внимание!',
            info: 'Информация'
        };

        toast.innerHTML = `
            <i class="fas ${icons[type]}"></i>
            <div class="toast-content">
                <strong>${titles[type]}</strong>
                <p>${message}</p>
            </div>
            <button class="toast-close">&times;</button>
            <div class="toast-progress"></div>
        `;

        this.container.appendChild(toast);

        // Закрытие по клику на крестик
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => this.remove(toast));

        // Автоматическое удаление
        if (duration > 0) {
            setTimeout(() => this.remove(toast), duration);
        }

        return toast;
    }

    success(message, duration) {
        return this.show(message, 'success', duration);
    }

    error(message, duration) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration) {
        return this.show(message, 'info', duration);
    }

    remove(toast) {
        toast.style.animation = 'slideOutRight 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }
}

// Глобальный экземпляр
const toast = new ToastNotification();

// Добавляем анимацию выхода
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ==================== АНИМИРОВАННЫЙ СЧЕТЧИК ====================
function animateCounter(element, target, duration = 2000) {
    const start = parseInt(element.textContent) || 0;
    const increment = (target - start) / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= target) || (increment < 0 && current <= target)) {
            element.textContent = Math.round(target);
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, 16);
}

// Автоматически анимируем все счетчики при скролле в видимость
function initCounters() {
    const counters = document.querySelectorAll('.animated-counter');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.animated) {
                const target = parseInt(entry.target.dataset.target) || 0;
                animateCounter(entry.target, target);
                entry.target.dataset.animated = 'true';
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => observer.observe(counter));
}

// ==================== RIPPLE EFFECT ====================
function createRipple(event) {
    const button = event.currentTarget;

    // Удаляем старый ripple если есть
    const existingRipple = button.querySelector('.ripple');
    if (existingRipple) {
        existingRipple.remove();
    }

    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;

    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${event.clientX - button.offsetLeft - radius}px`;
    circle.style.top = `${event.clientY - button.offsetTop - radius}px`;
    circle.classList.add('ripple');

    button.appendChild(circle);

    setTimeout(() => circle.remove(), 600);
}

// Добавляем ripple effect ко всем кнопкам с классом .btn-ripple
document.addEventListener('DOMContentLoaded', function() {
    const rippleButtons = document.querySelectorAll('.btn-ripple');
    rippleButtons.forEach(button => {
        button.addEventListener('click', createRipple);
    });

    // Инициализируем счетчики
    initCounters();
});

// Стили для ripple
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: ripple-animation 0.6s ease-out;
        pointer-events: none;
    }

    @keyframes ripple-animation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(rippleStyle);

// ==================== SKELETON LOADER ====================
function showSkeleton(element) {
    element.classList.add('skeleton-loading');
    element.innerHTML = `
        <div class="skeleton-loader">
            <div class="skeleton-line"></div>
            <div class="skeleton-line medium"></div>
            <div class="skeleton-line short"></div>
        </div>
    `;
}

function hideSkeleton(element, content) {
    element.classList.remove('skeleton-loading');
    element.innerHTML = content;
}

// Skeleton для списка кортов
function showCourtsSkeleton(container, count = 3) {
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'skeleton-court';
        skeleton.innerHTML = `
            <div class="skeleton-court-header">
                <div class="skeleton-court-title"></div>
                <div class="skeleton-court-price"></div>
            </div>
            <div class="skeleton-court-desc"></div>
            <div class="skeleton-court-desc short"></div>
        `;
        container.appendChild(skeleton);
    }
}

// Skeleton для временных слотов
function showSlotsSkeleton(container, count = 8) {
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'skeleton-slot';
        container.appendChild(skeleton);
    }
}

// ==================== КОНФИРМ ДИАЛОГ ====================
function showConfirmDialog(options = {}) {
    const defaults = {
        title: 'Подтверждение',
        message: 'Вы уверены?',
        confirmText: 'Да',
        cancelText: 'Отмена',
        onConfirm: () => {},
        onCancel: () => {},
        type: 'warning'
    };

    const settings = { ...defaults, ...options };

    const modal = document.createElement('div');
    modal.className = 'modal modal-modern';
    modal.style.display = 'flex';

    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const colors = {
        success: '#4caf50',
        error: '#f44336',
        warning: '#ff9800',
        info: '#2196f3'
    };

    modal.innerHTML = `
        <div class="modal-backdrop" style="backdrop-filter: blur(8px); background: rgba(0, 0, 0, 0.5);"></div>
        <div class="modal-content" style="
            background: white;
            padding: 30px;
            border-radius: 15px;
            max-width: 450px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            position: relative;
            z-index: 1;
            text-align: center;
        ">
            <i class="fas ${icons[settings.type]}" style="
                font-size: 64px;
                color: ${colors[settings.type]};
                margin-bottom: 20px;
            "></i>
            <h2 style="margin-bottom: 15px; color: #333;">${settings.title}</h2>
            <p style="margin-bottom: 30px; color: #666; font-size: 16px;">${settings.message}</p>
            <div style="display: flex; gap: 15px; justify-content: center;">
                <button class="btn-cancel" style="
                    flex: 1;
                    padding: 12px 30px;
                    border-radius: 8px;
                    border: 2px solid #ddd;
                    background: white;
                    color: #666;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s;
                ">${settings.cancelText}</button>
                <button class="btn-confirm" style="
                    flex: 1;
                    padding: 12px 30px;
                    border-radius: 8px;
                    border: none;
                    background: linear-gradient(135deg, ${colors[settings.type]}, ${colors[settings.type]}dd);
                    color: white;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s;
                ">${settings.confirmText}</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    const btnConfirm = modal.querySelector('.btn-confirm');
    const btnCancel = modal.querySelector('.btn-cancel');
    const backdrop = modal.querySelector('.modal-backdrop');

    btnConfirm.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
        this.style.boxShadow = `0 5px 15px ${colors[settings.type]}50`;
    });

    btnConfirm.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = 'none';
    });

    btnCancel.addEventListener('mouseenter', function() {
        this.style.borderColor = '#999';
        this.style.background = '#f5f5f5';
    });

    btnCancel.addEventListener('mouseleave', function() {
        this.style.borderColor = '#ddd';
        this.style.background = 'white';
    });

    btnConfirm.addEventListener('click', () => {
        settings.onConfirm();
        modal.remove();
    });

    btnCancel.addEventListener('click', () => {
        settings.onCancel();
        modal.remove();
    });

    backdrop.addEventListener('click', () => {
        settings.onCancel();
        modal.remove();
    });

    return modal;
}

// ==================== PROGRESS BAR ====================
function updateProgressBar(element, value, animated = true) {
    const fill = element.querySelector('.progress-fill');
    const label = element.querySelector('.progress-label');

    if (animated) {
        setTimeout(() => {
            fill.style.width = `${value}%`;
            if (label) {
                let current = 0;
                const increment = value / 50;
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= value) {
                        label.textContent = `${Math.round(value)}%`;
                        clearInterval(timer);
                    } else {
                        label.textContent = `${Math.round(current)}%`;
                    }
                }, 20);
            }
        }, 100);
    } else {
        fill.style.width = `${value}%`;
        if (label) label.textContent = `${Math.round(value)}%`;
    }
}

// ==================== LOADING OVERLAY ====================
let loadingOverlay = null;

function showLoading(message = 'Загрузка...') {
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(5px);
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        loadingOverlay.innerHTML = `
            <div style="
                background: white;
                padding: 30px 40px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            ">
                <i class="fas fa-spinner fa-spin" style="
                    font-size: 48px;
                    color: var(--primary-color, #9ef01a);
                    margin-bottom: 15px;
                "></i>
                <p class="loading-message" style="
                    margin: 0;
                    font-size: 16px;
                    font-weight: 600;
                    color: #333;
                ">${message}</p>
            </div>
        `;

        document.body.appendChild(loadingOverlay);
    } else {
        loadingOverlay.querySelector('.loading-message').textContent = message;
        loadingOverlay.style.display = 'flex';
    }
}

function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

// Экспортируем в глобальную область
window.toast = toast;
window.animateCounter = animateCounter;
window.showSkeleton = showSkeleton;
window.hideSkeleton = hideSkeleton;
window.showCourtsSkeleton = showCourtsSkeleton;
window.showSlotsSkeleton = showSlotsSkeleton;
window.showConfirmDialog = showConfirmDialog;
window.updateProgressBar = updateProgressBar;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
