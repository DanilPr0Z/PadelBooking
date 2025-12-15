document.addEventListener('DOMContentLoaded', function() {
    // ==================== ОБЩИЕ ПЕРЕМЕННЫЕ ====================
    const loginModal = document.getElementById('loginModal');
    const registerModal = document.getElementById('registerModal');
    const logoutModal = document.getElementById('logoutModal');
    const openLoginBtn = document.getElementById('openLoginModal');
    const openRegisterBtn = document.getElementById('openRegisterModal');
    const openLogoutBtn = document.getElementById('openLogoutModal');
    const closeButtons = document.querySelectorAll('.close-modal');
    const cancelLogoutBtn = document.getElementById('cancelLogout');
    const confirmLogoutBtn = document.getElementById('confirmLogout');

    // URLs (должны быть определены в шаблоне или хардкодим)
    const URLS = {
        logout: '/users/logout/',
        ajax_login: '/users/ajax/login/',
        ajax_register: '/users/ajax/register/'
    };

    // ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

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

    function showMessage(type, text) {
        // Удаляем старые сообщения
        document.querySelectorAll('.custom-message').forEach(msg => msg.remove());

        // Создаем элемент сообщения
        const messageDiv = document.createElement('div');
        messageDiv.className = `custom-message ${type}-message`;
        messageDiv.textContent = text;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 10000;
            max-width: 300px;
            animation: slideIn 0.3s ease;
            color: white;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;

        if (type === 'success') {
            messageDiv.style.backgroundColor = '#28a745';
            messageDiv.style.borderLeft = '4px solid #1e7e34';
        } else {
            messageDiv.style.backgroundColor = '#dc3545';
            messageDiv.style.borderLeft = '4px solid #bd2130';
        }

        document.body.appendChild(messageDiv);

        // Удаляем сообщение через 5 секунд
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 5000);
    }

    function closeAllModals() {
        [loginModal, registerModal, logoutModal].forEach(modal => {
            if (modal) modal.style.display = 'none';
        });
        document.body.style.overflow = 'auto';
    }

    // ==================== УПРАВЛЕНИЕ МОДАЛЬНЫМИ ОКНАМИ ====================

    // Открытие модальных окон
    if (openLoginBtn) {
        openLoginBtn.addEventListener('click', function(e) {
            e.preventDefault();
            closeAllModals();
            if (loginModal) loginModal.style.display = 'block';
        });
    }

    if (openRegisterBtn) {
        openRegisterBtn.addEventListener('click', function(e) {
            e.preventDefault();
            closeAllModals();
            if (registerModal) registerModal.style.display = 'block';
        });
    }

    if (openLogoutBtn) {
        openLogoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            closeAllModals();
            if (logoutModal) logoutModal.style.display = 'block';
        });
    }

    // Закрытие
    closeButtons.forEach(button => {
        button.addEventListener('click', closeAllModals);
    });

    window.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            closeAllModals();
        }
    });

    if (cancelLogoutBtn) {
        cancelLogoutBtn.addEventListener('click', closeAllModals);
    }

    // Переключение между формами
    document.querySelectorAll('.switch-to-register').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            closeAllModals();
            if (registerModal) registerModal.style.display = 'block';
        });
    });

    document.querySelectorAll('.switch-to-login').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            closeAllModals();
            if (loginModal) loginModal.style.display = 'block';
        });
    });

    // ==================== AJAX ФОРМЫ ====================

    // Вход
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const submitBtn = loginForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Вход...';

            fetch(URLS.ajax_login, {
                method: 'POST',
                body: new FormData(loginForm),
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('success', data.message);
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    showMessage('error', data.message);
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            })
            .catch(error => {
                showMessage('error', 'Ошибка при входе');
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
        });
    }

    // ==================== AJAX РЕГИСТРАЦИЯ ====================
// ==================== AJAX РЕГИСТРАЦИЯ (ИСПРАВЛЕННАЯ) ====================
const registerForm = document.getElementById('registerForm');
if (registerForm) {
    registerForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(registerForm);
        const submitBtn = registerForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;

        // Показываем индикатор загрузки
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Регистрация...';

        fetch('/users/ajax/register/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('Ответ сервера:', data); // Для отладки

            if (data.success) {
                showMessage('success', data.message);
                closeAllModals();

                // Обновляем страницу через 1.5 секунды
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                // Очищаем старые ошибки
                document.querySelectorAll('.error-message').forEach(error => error.remove());

                // ИСПРАВЛЕНО: правильное отображение ошибок
                if (data.errors) {
                    for (const field in data.errors) {
                        const input = document.querySelector(`[name="${field}"]`);
                        if (input) {
                            // Получаем массив ошибок для этого поля
                            const fieldErrors = data.errors[field];

                            // Берем первую ошибку (обычно там только одна)
                            if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
                                const errorText = fieldErrors[0];

                                const errorDiv = document.createElement('div');
                                errorDiv.className = 'error-message';
                                errorDiv.textContent = errorText;
                                input.parentNode.appendChild(errorDiv);

                                // Добавляем красную рамку полю с ошибкой
                                input.style.borderColor = '#dc3545';
                                input.style.boxShadow = '0 0 0 0.2rem rgba(220,53,69,.25)';

                                // Убираем красную рамку при исправлении
                                input.addEventListener('input', function() {
                                    this.style.borderColor = '';
                                    this.style.boxShadow = '';
                                    const errorMsg = this.parentNode.querySelector('.error-message');
                                    if (errorMsg) errorMsg.remove();
                                }, { once: true });
                            }
                        }
                    }
                }

                // Показываем общее сообщение об ошибке
                showMessage('error', data.message || 'Пожалуйста, исправьте ошибки');

                // Восстанавливаем кнопку
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('error', 'Произошла ошибка при регистрации');
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        });
    });
}
    // ==================== ВЫХОД ИЗ АККАУНТА (ФИКСИРОВАННЫЙ) ====================
    if (confirmLogoutBtn) {
        confirmLogoutBtn.addEventListener('click', function() {
            const originalText = confirmLogoutBtn.textContent;
            confirmLogoutBtn.disabled = true;
            confirmLogoutBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Выход...';

            // Создаем форму для POST запроса
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = URLS.logout;  // Используем хардкодный URL
            form.style.display = 'none';

            // CSRF токен
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = getCookie('csrftoken');
            form.appendChild(csrfInput);

            document.body.appendChild(form);
            form.submit();  // Отправляем форму
        });
    }


    // ==================== ВЫПАДАЮЩЕЕ МЕНЮ ====================
    const userDropdowns = document.querySelectorAll('.user-dropdown');

    userDropdowns.forEach(dropdown => {
        const button = dropdown.querySelector('.user-btn');
        const menu = dropdown.querySelector('.dropdown-content');

        if (button && menu) {
            button.addEventListener('click', function(e) {
                e.stopPropagation();
                menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
            });
        }
    });

    document.addEventListener('click', function() {
        document.querySelectorAll('.dropdown-content').forEach(menu => {
            menu.style.display = 'none';
        });
    });

    // ==================== CSS АНИМАЦИИ ====================
    if (!document.querySelector('#custom-styles')) {
        const style = document.createElement('style');
        style.id = 'custom-styles';
        style.textContent = `
            @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            .modal-content { animation: fadeIn 0.3s ease; }
            .fa-spinner { margin-right: 8px; animation: fa-spin 1s infinite linear; }
            @keyframes fa-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        `;
        document.head.appendChild(style);
    }

    console.log('Paddle Booking JS loaded');
});