
document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для навигации по профилю
    const profileLink = document.getElementById('profile-link');
    const bookingsLink = document.getElementById('bookings-link');
    const ratingLink = document.getElementById('rating-link');

    // При клике на "Профиль" - просто переходим на страницу профиля
    // (по умолчанию откроется первая вкладка "Данные профиля")
    if (profileLink) {
        profileLink.addEventListener('click', function(e) {
            // Можно добавить хеш #profile для явного указания, но это не обязательно
            // window.location.href = "{% url 'profile' %}#profile";
        });
    }

    // При клике на "Мои записи" - добавляем хеш #bookings к URL
    if (bookingsLink) {
        bookingsLink.addEventListener('click', function(e) {
            e.preventDefault(); // Предотвращаем стандартный переход
            window.location.href = "{% url 'profile' %}#bookings";
        });
    }

    // При клике на "Мой рейтинг" - добавляем хеш #rating к URL
    if (ratingLink) {
        ratingLink.addEventListener('click', function(e) {
            e.preventDefault(); // Предотвращаем стандартный переход
            window.location.href = "{% url 'profile' %}#rating";
        });
    }

    // ========== УПРАВЛЕНИЕ МОДАЛЬНЫМИ ОКНАМИ ==========

    // Получаем элементы модальных окон
    const logoutModal = document.getElementById('logoutModal');
    const openLogoutModalBtn = document.getElementById('openLogoutModal');
    const closeModalBtns = document.querySelectorAll('.close-modal');
    const cancelLogoutBtn = document.getElementById('cancelLogout');
    const confirmLogoutBtn = document.getElementById('confirmLogout');

    // Открытие модального окна выхода
    if (openLogoutModalBtn) {
        openLogoutModalBtn.addEventListener('click', function() {
            if (logoutModal) {
                logoutModal.style.display = 'flex';
            }
        });
    }

    // Закрытие модальных окон при клике на крестик
    closeModalBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            this.closest('.modal').style.display = 'none';
        });
    });

    // Закрытие модальных окон при клике вне окна
    window.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            e.target.style.display = 'none';
        }
    });

    // Отмена выхода
    if (cancelLogoutBtn) {
        cancelLogoutBtn.addEventListener('click', function() {
            if (logoutModal) {
                logoutModal.style.display = 'none';
            }
        });
    }

    // Подтверждение выхода
    if (confirmLogoutBtn) {
        confirmLogoutBtn.addEventListener('click', function() {
            window.location.href = "{% url 'logout' %}";
        });
    }

    // ========== ОТКРЫТИЕ МОДАЛЬНЫХ ОКОН ВХОДА/РЕГИСТРАЦИИ ==========
    // (если они есть на странице)
    const openLoginModalBtn = document.getElementById('openLoginModal');
    const openRegisterModalBtn = document.getElementById('openRegisterModal');

    if (openLoginModalBtn) {
        openLoginModalBtn.addEventListener('click', function() {
            // Проверяем, есть ли глобальная функция для открытия модального окна входа
            if (typeof window.openLoginModal === 'function') {
                window.openLoginModal();
            }
        });
    }

    if (openRegisterModalBtn) {
        openRegisterModalBtn.addEventListener('click', function() {
            // Проверяем, есть ли глобальная функция для открытия модального окна регистрации
            if (typeof window.openRegisterModal === 'function') {
                window.openRegisterModal();
            }
        });
    }
});