document.addEventListener('DOMContentLoaded', function() {
    // ========== ОБРАБОТКА URL ПАРАМЕТРОВ И ХЕША ==========
    function handleUrlNavigation() {
        const urlTab = getUrlParameter('tab');
        const hashTab = window.location.hash.substring(1);

        console.log('URL параметры: tab=', urlTab, 'hash=', hashTab);

        // Приоритет: хеш > параметр > по умолчанию
        let targetTab = hashTab || urlTab || 'profile';

        if (targetTab === 'bookings' || targetTab === 'rating') {
            setTimeout(() => {
                const tabBtn = document.querySelector(`.tab-btn[data-tab="${targetTab}"]`);
                if (tabBtn && !tabBtn.classList.contains('active')) {
                    console.log('Открываем вкладку:', targetTab);
                    tabBtn.click();
                }
            }, 300);
        }
    }

    // ========== ЗАКРЫТИЕ СООБЩЕНИЙ ==========
    document.querySelectorAll('.close-message').forEach(btn => {
        btn.addEventListener('click', function() {
            const message = this.closest('.message');
            if (message) {
                message.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => {
                    message.remove();
                }, 300);
            }
        });
    });

    // Автоматическое скрытие сообщений через 5 секунд
    setTimeout(() => {
        document.querySelectorAll('.message').forEach(msg => {
            msg.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => msg.remove(), 300);
        });
    }, 5000);

    // ========== ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК ==========
    const tabBtns = document.querySelectorAll('.profile-tabs .tab-btn');
    const tabContents = document.querySelectorAll('.profile-content .tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.dataset.tab;

            // Убираем активный класс у всех кнопок и контента
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Добавляем активный класс текущей кнопке
            this.classList.add('active');

            // Показываем соответствующий контент
            const activeContent = document.getElementById(`${tabId}-tab`);
            if (activeContent) {
                activeContent.classList.add('active');

                // ФИКС: Сбрасываем прогресс бар к правильной ширине
                if (tabId === 'rating') {
                    setTimeout(() => {
                        const progressBar = document.getElementById('progressBarFill');
                        if (progressBar) {
                            const currentWidth = progressBar.style.width;
                            // Принудительно обновляем ширину для сброса анимации
                            progressBar.style.transition = 'none';
                            progressBar.style.width = '0%';
                            setTimeout(() => {
                                progressBar.style.transition = 'width 0.5s ease-in-out';
                                progressBar.style.width = currentWidth;
                            }, 50);
                        }
                    }, 100);
                }
            }

            // Обновляем URL с хешем
            if (tabId !== 'profile') {
                window.history.pushState(null, '', `#${tabId}`);
            } else {
                window.history.pushState(null, '', window.location.pathname);
            }

            // Если переключаемся на вкладку бронирований, инициализируем фильтрацию
            if (tabId === 'bookings') {
                setTimeout(() => {
                    initializeBookingFilters();
                    initializeBookingActions();
                }, 100);
            }

            // Если переключаемся на вкладку рейтинга, инициализируем обновление
            if (tabId === 'rating') {
                setTimeout(() => {
                    initializeRatingTab();
                }, 100);
            }
        });
    });

    // ========== ФИЛЬТРАЦИЯ БРОНИРОВАНИЙ ==========
    function initializeBookingFilters() {
        const filterButtons = document.querySelectorAll('.booking-filters .filter-btn');
        const bookingCards = document.querySelectorAll('.bookings-list .booking-card');
        const filterCount = document.querySelector('.filter-count');

        if (!filterButtons.length || !bookingCards.length) return;

        filterButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Убираем активный класс у всех кнопок
                filterButtons.forEach(btn => btn.classList.remove('active'));
                // Добавляем активный класс текущей кнопке
                this.classList.add('active');

                const filter = this.dataset.filter;
                let visibleCount = 0;

                // Фильтруем карточки
                bookingCards.forEach(card => {
                    if (filter === 'all' || card.dataset.status === filter) {
                        card.style.display = 'block';
                        visibleCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });

                // Обновляем счетчик
                if (filterCount) {
                    filterCount.textContent = `Найдено бронирований: ${visibleCount}`;
                }
            });
        });
    }

    // ========== ДЕЙСТВИЯ С БРОНИРОВАНИЯМИ ==========
    function initializeBookingActions() {
        const confirmModal = document.getElementById('confirmModal');
        const cancelModal = document.getElementById('cancelModal');
        const successNotification = document.getElementById('successNotification');

        // Закрытие модальных окон профиля
        document.querySelectorAll('.profile-close-modal').forEach(closeBtn => {
            closeBtn.addEventListener('click', function() {
                this.closest('.profile-modal').style.display = 'none';
            });
        });

        // Закрытие модальных окон профиля при клике вне их
        window.addEventListener('click', function(e) {
            if (e.target.classList.contains('profile-modal')) {
                e.target.style.display = 'none';
            }
        });

        // Закрытие уведомления
        const closeNotificationBtn = document.querySelector('.close-notification');
        if (closeNotificationBtn) {
            closeNotificationBtn.addEventListener('click', function() {
                successNotification.style.display = 'none';
            });
        }

        // ========== ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ ==========
        document.querySelectorAll('.confirm-booking-btn').forEach(button => {
            button.addEventListener('click', function() {
                const bookingId = this.dataset.bookingId;

                fetch(`/booking/booking-info/${bookingId}/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const booking = data.booking;

                            // Заполняем модальное окно
                            document.getElementById('confirm-court-name').textContent = booking.court_name;
                            document.getElementById('confirm-date').textContent = booking.date;
                            document.getElementById('confirm-time').textContent = booking.time;
                            document.querySelector('#confirmModal .confirm-action').dataset.bookingId = bookingId;

                            // Показываем модальное окно
                            confirmModal.style.display = 'flex';
                        } else {
                            showErrorNotification('Ошибка загрузки информации о бронировании');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showErrorNotification('Ошибка загрузки информации о бронировании');
                    });
            });
        });

        // ========== ОТМЕНА БРОНИРОВАНИЯ ==========
        document.querySelectorAll('.cancel-booking-btn').forEach(button => {
            button.addEventListener('click', function() {
                const bookingId = this.dataset.bookingId;

                fetch(`/booking/booking-info/${bookingId}/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const booking = data.booking;

                            // Заполняем модальное окно
                            document.getElementById('cancel-court-name').textContent = booking.court_name;
                            document.getElementById('cancel-date').textContent = booking.date;
                            document.getElementById('cancel-time').textContent = booking.time;
                            document.querySelector('#cancelModal .confirm-action').dataset.bookingId = bookingId;

                            // Показываем модальное окно
                            cancelModal.style.display = 'flex';
                        } else {
                            showErrorNotification('Ошибка загрузки информации о бронировании');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showErrorNotification('Ошибка загрузки информации о бронировании');
                    });
            });
        });

        // ========== ОБРАБОТЧИКИ ПОДТВЕРЖДЕНИЯ ==========
        const confirmActionBtn = document.querySelector('#confirmModal .confirm-action');
        if (confirmActionBtn) {
            confirmActionBtn.addEventListener('click', function() {
                const bookingId = this.dataset.bookingId;
                const button = this;

                // Показываем индикатор загрузки
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Подтверждение...';
                button.disabled = true;

                fetch(`/booking/confirm/${bookingId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Закрываем модальное окно
                        confirmModal.style.display = 'none';
                        // Показываем уведомление
                        showSuccessNotification(data.message);
                        // Обновляем страницу через 2 секунды
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        // Показываем ошибку
                        showErrorNotification(data.message);
                        // Восстанавливаем кнопку
                        button.innerHTML = 'Да, подтвердить';
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showErrorNotification('Ошибка при подтверждении бронирования');
                    button.innerHTML = 'Да, подтвердить';
                    button.disabled = false;
                });
            });
        }

        // ========== ОБРАБОТЧИКИ ОТМЕНЫ ==========
        const cancelActionBtn = document.querySelector('#cancelModal .confirm-action');
        if (cancelActionBtn) {
            cancelActionBtn.addEventListener('click', function() {
                const bookingId = this.dataset.bookingId;
                const button = this;

                // Показываем индикатор загрузки
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отмена...';
                button.disabled = true;

                fetch(`/booking/cancel/${bookingId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Закрываем модальное окно
                        cancelModal.style.display = 'none';
                        // Показываем уведомление
                        showSuccessNotification(data.message);
                        // Обновляем страницу через 2 секунды
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        // Показываем ошибку
                        showErrorNotification(data.message);
                        // Восстанавливаем кнопку
                        button.innerHTML = 'Да, отменить';
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showErrorNotification('Ошибка при отмене бронирования');
                    button.innerHTML = 'Да, отменить';
                    button.disabled = false;
                });
            });
        }

        // ========== ОТМЕНА ДЕЙСТВИЙ ==========
        document.querySelectorAll('.cancel-action').forEach(button => {
            button.addEventListener('click', function() {
                this.closest('.profile-modal').style.display = 'none';
            });
        });
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ВКЛАДКИ РЕЙТИНГА ==========
    function initializeRatingTab() {
        const refreshBtn = document.getElementById('refreshRatingHistory');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                refreshRatingInfo();
            });
        }

        // Настройка обновления рейтинга для тренеров
        const ratingUpdateModal = document.getElementById('ratingUpdateModal');
        if (ratingUpdateModal) {
            // Настройка закрытия модального окна
            ratingUpdateModal.querySelector('.profile-close-modal').addEventListener('click', function() {
                ratingUpdateModal.style.display = 'none';
            });

            // Настройка кнопки отмены
            ratingUpdateModal.querySelector('.cancel-action').addEventListener('click', function() {
                ratingUpdateModal.style.display = 'none';
            });

            // Настройка сохранения рейтинга
            document.getElementById('saveRatingBtn').addEventListener('click', function() {
                savePlayerRating();
            });
        }

        // ФИКС: Правильно инициализируем прогресс бар при загрузке вкладки
        const progressBar = document.getElementById('progressBarFill');
        if (progressBar) {
            // Получаем значение ширины из инлайн-стиля
            const currentWidth = progressBar.style.width;
            console.log('Текущая ширина прогресс бара:', currentWidth);

            // Если ширина пустая или 0%, устанавливаем правильное значение
            if (!currentWidth || currentWidth === '0%') {
                // Получаем значение из текста
                const progressText = document.querySelector('.progress-bar-text');
                if (progressText) {
                    const percentageText = progressText.textContent.replace('%', '');
                    const percentage = parseFloat(percentageText);
                    if (!isNaN(percentage)) {
                        progressBar.style.width = percentage + '%';
                        console.log('Установлена ширина прогресс бара:', percentage + '%');
                    }
                }
            }

            // Добавляем анимацию
            progressBar.style.transition = 'width 0.5s ease-in-out';
        }
    }

    // ========== ОБНОВЛЕНИЕ ИНФОРМАЦИИ О РЕЙТИНГЕ ==========
    function refreshRatingInfo() {
        const refreshBtn = document.getElementById('refreshRatingHistory');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обновление...';
            refreshBtn.disabled = true;
        }

        // Обновляем данные через AJAX
        fetch('/users/ajax/rating-info/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Обновляем основные данные
                    updateRatingDisplay(data);
                    showSuccessNotification('Данные рейтинга обновлены');
                } else {
                    showErrorNotification('Ошибка обновления рейтинга');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showErrorNotification('Ошибка обновления рейтинга');
            })
            .finally(() => {
                if (refreshBtn) {
                    setTimeout(() => {
                        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Обновить';
                        refreshBtn.disabled = false;
                    }, 1000);
                }
            });
    }

    function updateRatingDisplay(data) {
        console.log('Обновление отображения рейтинга с данными:', data);

        // Обновляем отображение рейтинга
        document.querySelectorAll('.rating-level').forEach(el => {
            el.textContent = data.level;
        });

        document.querySelectorAll('.rating-numeric').forEach(el => {
            el.textContent = data.numeric_rating;
        });

        document.querySelectorAll('.rating-level-large').forEach(el => {
            el.textContent = data.level;
        });

        document.querySelectorAll('.rating-numeric-large').forEach(el => {
            el.textContent = data.numeric_rating;
        });

        // Обновляем уровень описания
        document.querySelectorAll('.rating-level-description h3').forEach(el => {
            el.textContent = data.level_display_full || data.level_display || el.textContent;
        });

        // Обновляем прогресс бар - ФИКС ДЛЯ ПРАВИЛЬНОГО ОТОБРАЖЕНИЯ
        const progressBar = document.getElementById('progressBarFill');
        const progressText = document.querySelector('.progress-bar-text');
        const progressPercentage = document.querySelector('.progress-percentage');

        if (progressBar) {
            // Убедимся, что значение в пределах 0-100
            let width = parseFloat(data.progress_percentage);
            if (isNaN(width)) width = 0;
            if (width < 0) width = 0;
            if (width > 100) width = 100;

            console.log('Устанавливаем ширину прогресс бара:', width + '%');

            // Анимируем изменение ширины
            progressBar.style.transition = 'width 0.5s ease-in-out';
            progressBar.style.width = width + '%';
        }

        if (progressText) {
            progressText.textContent = Math.round(data.progress_percentage) + '%';
        }

        if (progressPercentage) {
            progressPercentage.textContent = Math.round(data.progress_percentage) + '%';
        }

        // Обновляем текущее значение рейтинга в диапазоне
        const rangeCurrent = document.querySelector('.range-current');
        if (rangeCurrent) {
            rangeCurrent.textContent = data.numeric_rating;
        }

        // Обновляем диапазоны если они пришли
        if (data.range_min !== undefined && data.range_max !== undefined) {
            const rangeMin = document.querySelector('.range-min');
            const rangeMax = document.querySelector('.range-max');
            if (rangeMin) rangeMin.textContent = data.range_min.toFixed(2);
            if (rangeMax) rangeMax.textContent = data.range_max.toFixed(2);
        }
    }

    // ========== СОХРАНЕНИЕ РЕЙТИНГА (для тренеров) ==========
    function savePlayerRating() {
        const playerId = document.getElementById('playerId').value;
        const numericRating = document.getElementById('numeric_rating').value;
        const coachComment = document.getElementById('coach_comment').value;
        const saveBtn = document.getElementById('saveRatingBtn');

        if (!numericRating || numericRating < 1.00 || numericRating > 7.00) {
            showErrorNotification('Пожалуйста, введите корректный рейтинг (1.00-7.00)');
            return;
        }

        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение...';
        saveBtn.disabled = true;

        fetch(`/users/ajax/update-rating/${playerId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `numeric_rating=${encodeURIComponent(numericRating)}&coach_comment=${encodeURIComponent(coachComment)}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Закрываем модальное окно
                document.getElementById('ratingUpdateModal').style.display = 'none';
                // Показываем уведомление
                showSuccessNotification(data.message);
                // Обновляем страницу через 2 секунды
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                // Показываем ошибку
                showErrorNotification(data.message || 'Ошибка при обновлении рейтинга');
                // Восстанавливаем кнопку
                saveBtn.innerHTML = 'Сохранить изменения';
                saveBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showErrorNotification('Ошибка сервера при обновлении рейтинга');
            saveBtn.innerHTML = 'Сохранить изменения';
            saveBtn.disabled = false;
        });
    }

    // ========== ОТКРЫТИЕ МОДАЛЬНОГО ОКНА ДЛЯ ИЗМЕНЕНИЯ РЕЙТИНГА ==========
    function openRatingUpdateModal(playerId, playerName, currentRating) {
        const modal = document.getElementById('ratingUpdateModal');
        if (!modal) return;

        document.getElementById('playerId').value = playerId;
        document.getElementById('playerNameModal').textContent = playerName;
        document.getElementById('numeric_rating').value = currentRating;
        document.getElementById('currentRatingValue').textContent = currentRating;
        document.getElementById('coach_comment').value = '';

        modal.style.display = 'flex';
    }

    // ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
    function showSuccessNotification(message) {
        const successNotification = document.getElementById('successNotification');
        const successMessage = document.getElementById('success-message');

        if (successMessage && successNotification) {
            successMessage.textContent = message;
            successNotification.style.display = 'block';

            // Автоматически скрываем через 5 секунд
            setTimeout(() => {
                successNotification.style.display = 'none';
            }, 5000);
        }
    }

    function showErrorNotification(message) {
        alert(message);
    }

    // ========== АВАТАРКА ==========
    const avatarWrapper = document.getElementById('avatarWrapper');
    const avatarInput = document.getElementById('avatarInput');
    const avatarImage = document.getElementById('avatarImage');
    const avatarPlaceholder = document.getElementById('avatarPlaceholder');
    const avatarControls = document.getElementById('avatarControls');
    const confirmAvatarBtn = document.getElementById('confirmAvatarBtn');
    const cancelAvatarBtn = document.getElementById('cancelAvatarBtn');
    const deleteAvatarBtn = document.getElementById('deleteAvatarBtn');
    const avatarMessage = document.getElementById('avatarMessage');

    let selectedFile = null;
    let previewUrl = null;

    // Обработчик клика на аватарку
    if (avatarWrapper) {
        avatarWrapper.addEventListener('click', function(e) {
            if (e.target !== avatarInput) {
                avatarInput.click();
            }
        });

        // Показываем оверлей при наведении
        avatarWrapper.addEventListener('mouseenter', function() {
            this.querySelector('.avatar-overlay').style.opacity = '1';
        });

        avatarWrapper.addEventListener('mouseleave', function() {
            if (!selectedFile) {
                this.querySelector('.avatar-overlay').style.opacity = '0';
            }
        });
    }

    // Обработчик выбора файла
    if (avatarInput) {
        avatarInput.addEventListener('change', function(e) {
            if (this.files && this.files[0]) {
                selectedFile = this.files[0];

                // Валидация файла
                if (!validateAvatarFile(selectedFile)) {
                    showAvatarMessage('Недопустимый файл. Разрешены: JPG, PNG, GIF, WebP до 5MB', 'error');
                    resetAvatarSelection();
                    return;
                }

                // Создаем превью
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewUrl = e.target.result;

                    // Показываем превью
                    if (avatarImage) {
                        avatarImage.src = previewUrl;
                    } else if (avatarPlaceholder) {
                        // Скрываем плейсхолдер и создаем изображение
                        avatarPlaceholder.style.display = 'none';
                        const newImg = document.createElement('img');
                        newImg.src = previewUrl;
                        newImg.className = 'avatar-image avatar-preview';
                        newImg.alt = 'Превью аватарки';
                        avatarWrapper.insertBefore(newImg, avatarWrapper.firstChild);
                    }

                    // Показываем кнопки управления
                    if (avatarControls) {
                        avatarControls.style.display = 'flex';
                    }

                    // Показываем оверлей постоянно
                    const overlay = document.querySelector('.avatar-overlay');
                    if (overlay) {
                        overlay.style.opacity = '1';
                        overlay.innerHTML = '<i class="fas fa-check"></i><span>Подтвердить выбор</span>';
                    }
                };
                reader.readAsDataURL(selectedFile);

                showAvatarMessage('Файл выбран. Нажмите "Сохранить" для загрузки', 'info');
            }
        });
    }

    // Подтверждение загрузки
    if (confirmAvatarBtn) {
        confirmAvatarBtn.addEventListener('click', function() {
            if (!selectedFile) {
                showAvatarMessage('Сначала выберите файл', 'error');
                return;
            }

            uploadAvatar(selectedFile);
        });
    }

    // Отмена выбора
    if (cancelAvatarBtn) {
        cancelAvatarBtn.addEventListener('click', function() {
            resetAvatarSelection();
            showAvatarMessage('Выбор отменен', 'info');
        });
    }

    // Удаление аватарки
    if (deleteAvatarBtn) {
        deleteAvatarBtn.addEventListener('click', function() {
            if (confirm('Вы уверены, что хотите удалить аватарку?')) {
                deleteAvatar();
            }
        });
    }

    // Функции для работы с аватаркой
    function validateAvatarFile(file) {
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        const maxSize = 5 * 1024 * 1024; // 5MB

        if (!allowedTypes.includes(file.type)) {
            return false;
        }

        if (file.size > maxSize) {
            return false;
        }

        return true;
    }

    function resetAvatarSelection() {
        selectedFile = null;
        previewUrl = null;

        // Сбрасываем input файла
        if (avatarInput) {
            avatarInput.value = '';
        }

        // Восстанавливаем исходное состояние
        if (avatarImage && avatarImage.src.includes('blob:')) {
            // Если было превью, удаляем его
            const preview = avatarWrapper.querySelector('.avatar-preview');
            if (preview) {
                preview.remove();
            }

            // Показываем плейсхолдер
            if (avatarPlaceholder) {
                avatarPlaceholder.style.display = 'flex';
            }

            // Восстанавливаем оригинальную аватарку если есть
            const originalSrc = avatarImage.getAttribute('data-original-src');
            if (originalSrc) {
                avatarImage.src = originalSrc;
            }
        }

        // Скрываем кнопки управления
        if (avatarControls) {
            avatarControls.style.display = 'none';
        }

        // Восстанавливаем оверлей
        const overlay = document.querySelector('.avatar-overlay');
        if (overlay) {
            overlay.innerHTML = '<i class="fas fa-plus"></i><span>Изменить аватар</span>';
            overlay.style.opacity = '0';
        }
    }

    function uploadAvatar(file) {
        // Показываем индикатор загрузки
        if (confirmAvatarBtn) {
            confirmAvatarBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            confirmAvatarBtn.disabled = true;
        }

        // Создаем FormData
        const formData = new FormData();
        formData.append('avatar', file);

        // Отправляем запрос
        fetch('/users/ajax/upload-avatar/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAvatarMessage(data.message, 'success');

                // Обновляем аватарку на странице
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                showAvatarMessage(data.message, 'error');

                // Восстанавливаем кнопку
                if (confirmAvatarBtn) {
                    confirmAvatarBtn.innerHTML = '<i class="fas fa-check"></i>';
                    confirmAvatarBtn.disabled = false;
                }
            }
        })
        .catch(error => {
            showAvatarMessage('Ошибка при загрузке файла', 'error');

            // Восстанавливаем кнопку
            if (confirmAvatarBtn) {
                confirmAvatarBtn.innerHTML = '<i class="fas fa-check"></i>';
                confirmAvatarBtn.disabled = false;
            }
        });
    }

    function deleteAvatar() {
        // Показываем индикатор загрузки
        if (deleteAvatarBtn) {
            deleteAvatarBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            deleteAvatarBtn.disabled = true;
        }

        // Отправляем запрос
        fetch('/users/ajax/delete-avatar/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAvatarMessage(data.message, 'success');

                // Обновляем страницу
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                showAvatarMessage(data.message, 'error');

                // Восстанавливаем кнопку
                if (deleteAvatarBtn) {
                    deleteAvatarBtn.innerHTML = '<i class="fas fa-trash"></i>';
                    deleteAvatarBtn.disabled = false;
                }
            }
        })
        .catch(error => {
            showAvatarMessage('Ошибка при удалении аватарки', 'error');

            // Восстанавливаем кнопку
            if (deleteAvatarBtn) {
                deleteAvatarBtn.innerHTML = '<i class="fas fa-trash"></i>';
                deleteAvatarBtn.disabled = false;
            }
        });
    }

    function showAvatarMessage(message, type) {
        if (avatarMessage) {
            avatarMessage.textContent = message;
            avatarMessage.className = `avatar-message ${type}`;
            avatarMessage.style.display = 'block';

            // Автоматически скрываем через 5 секунд
            setTimeout(() => {
                avatarMessage.style.opacity = '0';
                avatarMessage.style.transition = 'opacity 0.5s';
                setTimeout(() => {
                    avatarMessage.style.display = 'none';
                    avatarMessage.style.opacity = '1';
                }, 500);
            }, 5000);
        }
    }

    // ========== EMAIL И ТЕЛЕФОН ==========
    const editEmailBtn = document.getElementById('editEmailBtn');
    const saveEmailBtn = document.getElementById('saveEmailBtn');
    const cancelEmailBtn = document.getElementById('cancelEmailBtn');
    const emailInput = document.getElementById('emailInput');
    const emailValue = document.getElementById('emailValue');
    const emailDisplay = document.getElementById('emailDisplay');
    const emailError = document.getElementById('emailError');
    const emailContainer = document.querySelector('.email-container');

    // Если email уже есть, добавляем кнопку редактирования
    if (editEmailBtn) {
        editEmailBtn.addEventListener('click', function() {
            // Получаем текущий email (убираем теги pending)
            let currentEmail = emailValue.textContent.trim();
            // Убираем текст "(ожидает подтверждения)" если есть
            currentEmail = currentEmail.replace(/\s*\(ожидает подтверждения\)/g, '').trim();

            // Заменяем отображение на поле ввода
            emailContainer.innerHTML = `
                <div class="email-input-container">
                    <input type="email" id="emailInput" class="email-input"
                           value="${currentEmail}" placeholder="Введите ваш email">
                    <button id="saveEmailBtn" class="save-btn" title="Сохранить email">
                        <i class="fas fa-check"></i>
                    </button>
                    <button id="cancelEmailBtn" class="cancel-btn" title="Отмена">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div id="emailError" class="error-message" style="display: none;"></div>
            `;

            // Добавляем обработчики для новых кнопок
            setupEmailEditHandlers();
        });
    }

    // Функция для настройки обработчиков редактирования email
    function setupEmailEditHandlers() {
        const newSaveBtn = document.getElementById('saveEmailBtn');
        const newCancelBtn = document.getElementById('cancelEmailBtn');
        const newEmailInput = document.getElementById('emailInput');
        const newEmailError = document.getElementById('emailError');

        if (newSaveBtn) {
            newSaveBtn.addEventListener('click', function() {
                const email = newEmailInput.value.trim();

                // Валидация email
                if (!email) {
                    showEmailError('Пожалуйста, введите email');
                    return;
                }

                if (!isValidEmail(email)) {
                    showEmailError('Введите корректный email адрес');
                    return;
                }

                // Показываем индикатор загрузки
                newSaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                newSaveBtn.disabled = true;

                // Отправляем запрос на сервер
                fetch('/users/ajax/update-email/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `email=${encodeURIComponent(email)}`
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Если email изменился, нужно подтверждение
                        if (data.email_pending) {
                            showSuccessMessage('Код подтверждения отправлен на новый email. Пожалуйста, подтвердите email.');
                            
                            // Перезагружаем страницу, чтобы показать блок подтверждения
                            setTimeout(() => {
                                window.location.reload();
                            }, 2000);
                        } else {
                            // Email не изменился или уже подтвержден
                            emailContainer.innerHTML = `
                                <span id="emailValue" class="email-value">${data.email}</span>
                                <button id="editEmailBtn" class="edit-btn" title="Изменить email">
                                    <i class="fas fa-edit"></i>
                                </button>
                            `;

                            // Обновляем email в заголовке профиля
                            if (emailDisplay) {
                                emailDisplay.textContent = data.email;
                                emailDisplay.className = '';
                            }

                            // Показываем сообщение об успехе
                            showSuccessMessage('Email успешно обновлен!');

                            // Возвращаем обработчик для кнопки редактирования
                            document.getElementById('editEmailBtn').addEventListener('click', function () {
                                const currentEmail = document.getElementById('emailValue').textContent;
                                emailContainer.innerHTML = `
                                <div class="email-input-container">
                                    <input type="email" id="emailInput" class="email-input"
                                           value="${currentEmail}" placeholder="Введите ваш email">
                                    <button id="saveEmailBtn" class="save-btn" title="Сохранить email">
                                        <i class="fas fa-check"></i>
                                    </button>
                                    <button id="cancelEmailBtn" class="cancel-btn" title="Отмена">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </div>
                                <div id="emailError" class="error-message" style="display: none;"></div>
                            `;
                                setupEmailEditHandlers();
                            });
                        } else {
                        // Ошибка
                        showEmailError(data.message || 'Ошибка при обновлении email');
                        newSaveBtn.innerHTML = '<i class="fas fa-check"></i>';
                        newSaveBtn.disabled = false;
                    }
                }
                .catch(error => {
                    showEmailError('Произошла ошибка при обновлении email');
                    newSaveBtn.innerHTML = '<i class="fas fa-check"></i>';
                    newSaveBtn.disabled = false;
                });
            });
        });

        if (newCancelBtn) {
            newCancelBtn.addEventListener('click', function() {
                const currentEmail = emailValue ? emailValue.textContent : '';

                if (currentEmail) {
                    // Возвращаем к отображению email
                    emailContainer.innerHTML = `
                        <span id="emailValue" class="email-value">${currentEmail}</span>
                        <button id="editEmailBtn" class="edit-btn" title="Изменить email">
                            <i class="fas fa-edit"></i>
                        </button>
                    `;

                    // Возвращаем обработчик
                    document.getElementById('editEmailBtn').addEventListener('click', function() {
                        const currentEmail = document.getElementById('emailValue').textContent;
                        emailContainer.innerHTML = `
                            <div class="email-input-container">
                                <input type="email" id="emailInput" class="email-input"
                                       value="${currentEmail}" placeholder="Введите ваш email">
                                <button id="saveEmailBtn" class="save-btn" title="Сохранить email">
                                    <i class="fas fa-check"></i>
                                </button>
                                <button id="cancelEmailBtn" class="cancel-btn" title="Отмена">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                            <div id="emailError" class="error-message" style="display: none;"></div>
                        `;
                        setupEmailEditHandlers();
                    });
                } else {
                    // Если email не был установлен, показываем поле ввода заново
                    emailContainer.innerHTML = `
                        <div class="email-input-container">
                            <input type="email" id="emailInput" class="email-input"
                                   placeholder="Введите ваш email">
                            <button id="saveEmailBtn" class="save-btn" title="Сохранить email">
                                <i class="fas fa-check"></i>
                            </button>
                        </div>
                        <div id="emailError" class="error-message" style="display: none;"></div>
                    `;
                    setupEmailEditHandlers();
                }
            });
        }

        // Валидация при вводе
        if (newEmailInput) {
            newEmailInput.addEventListener('input', function() {
                newEmailInput.classList.remove('invalid');
                if (newEmailError) newEmailError.style.display = 'none';
            });

            // Сохранение по Enter
            newEmailInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    if (newSaveBtn) newSaveBtn.click();
                }
            });
        }
    }

    // Если изначально нет email, настраиваем обработчики
    if (saveEmailBtn && emailInput) {
        setupEmailEditHandlers();
    }

    // ========== ПОДТВЕРЖДЕНИЕ ТЕЛЕФОНА ==========
    const verificationForm = document.getElementById('verificationForm');
    const resendBtn = document.getElementById('resendCode');
    const verificationMessage = document.getElementById('verificationMessage');

    if (verificationForm) {
        verificationForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(verificationForm);
            const code = formData.get('verification_code');

            if (!code || code.trim() === '') {
                showVerificationMessage('Введите код подтверждения', 'error');
                return;
            }

            // Показываем индикатор загрузки
            const submitBtn = verificationForm.querySelector('.btn-primary');
            const originalText = submitBtn.textContent;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Подтверждение...';
            submitBtn.disabled = true;

            // Отправляем AJAX запрос
            fetch('/users/ajax/verify-phone/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `verification_code=${encodeURIComponent(code)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Успешное подтверждение
                    showVerificationMessage(data.message, 'success');

                    // Обновляем интерфейс
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    // Ошибка
                    showVerificationMessage(data.message || 'Ошибка при подтверждении', 'error');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            })
            .catch(error => {
                showVerificationMessage('Произошла ошибка при подтверждении', 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }

    if (resendBtn) {
        resendBtn.addEventListener('click', function() {
            // Показываем индикатор загрузки
            resendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
            resendBtn.disabled = true;

            fetch('/users/ajax/resend-verification-code/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showVerificationMessage(data.message, 'success');
                } else {
                    showVerificationMessage('Ошибка: ' + data.message, 'error');
                }

                // Возвращаем кнопку в исходное состояние
                setTimeout(() => {
                    resendBtn.innerHTML = 'Отправить код повторно';
                    resendBtn.disabled = false;
                }, 2000);
            })
            .catch(error => {
                showVerificationMessage('Произошла ошибка при отправке кода', 'error');
                resendBtn.innerHTML = 'Отправить код повторно';
                resendBtn.disabled = false;
            });
            });
    }

    // ========== ПОДТВЕРЖДЕНИЕ EMAIL ==========
    const emailVerificationForm = document.getElementById('emailVerificationForm');
    const resendEmailBtn = document.getElementById('resendEmailCode');
    const emailVerificationMessage = document.getElementById('emailVerificationMessage');

    if (emailVerificationForm) {
        emailVerificationForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(emailVerificationForm);
            const code = formData.get('email_verification_code');

            if (!code || code.trim() === '') {
                showEmailVerificationMessage('Введите код подтверждения', 'error');
                return;
            }

            // Показываем индикатор загрузки
            const submitBtn = emailVerificationForm.querySelector('.btn-primary');
            const originalText = submitBtn.textContent;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Подтверждение...';
            submitBtn.disabled = true;

            // Отправляем AJAX запрос
            fetch('/users/ajax/verify-email/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `email_verification_code=${encodeURIComponent(code)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Успешное подтверждение
                    showEmailVerificationMessage(data.message, 'success');

                    // Обновляем интерфейс
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    // Ошибка
                    showEmailVerificationMessage(data.message || 'Ошибка при подтверждении', 'error');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            })
            .catch(error => {
                showEmailVerificationMessage('Произошла ошибка при подтверждении', 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }

    if (resendEmailBtn) {
        resendEmailBtn.addEventListener('click', function() {
            // Показываем индикатор загрузки
            resendEmailBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
            resendEmailBtn.disabled = true;

            fetch('/users/ajax/resend-email-verification-code/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showEmailVerificationMessage(data.message, 'success');
                } else {
                    showEmailVerificationMessage('Ошибка: ' + data.message, 'error');
                }

                // Возвращаем кнопку в исходное состояние
                setTimeout(() => {
                    resendEmailBtn.innerHTML = 'Отправить код повторно';
                    resendEmailBtn.disabled = false;
                }, 2000);
            })
            .catch(error => {
                showEmailVerificationMessage('Произошла ошибка при отправке кода', 'error');
                resendEmailBtn.innerHTML = 'Отправить код повторно';
                resendEmailBtn.disabled = false;
            });
        });
    }

    function showEmailVerificationMessage(message, type) {
        if (emailVerificationMessage) {
            emailVerificationMessage.textContent = message;
            emailVerificationMessage.className = `verification-message ${type}`;
            emailVerificationMessage.style.display = 'block';

            // Автоматически скрываем через 5 секунд для success
            if (type === 'success') {
                setTimeout(() => {
                    emailVerificationMessage.style.display = 'none';
                }, 5000);
            }
        }
    }

    // ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    function showEmailError(message) {
        if (emailError) {
            emailError.textContent = message;
            emailError.style.display = 'block';
        }

        if (emailInput) {
            emailInput.classList.add('invalid');
            emailInput.focus();
        }
    }

    function showSuccessMessage(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
        successDiv.style.display = 'block';

        // Добавляем сообщение под полем email
        const emailItem = document.querySelector('.email-item');
        if (emailItem) {
            // Удаляем предыдущее сообщение если есть
            const existingMessage = emailItem.querySelector('.success-message');
            if (existingMessage) {
                existingMessage.remove();
            }

            emailItem.appendChild(successDiv);

            // Убираем сообщение через 3 секунды
            setTimeout(() => {
                if (successDiv.parentNode) {
                    successDiv.style.opacity = '0';
                    successDiv.style.transition = 'opacity 0.5s';
                    setTimeout(() => {
                        if (successDiv.parentNode) {
                            successDiv.remove();
                        }
                    }, 500);
                }
            }, 3000);
        }
    }

    function showVerificationMessage(message, type) {
        if (verificationMessage) {
            verificationMessage.textContent = message;
            verificationMessage.className = `verification-message ${type}`;
            verificationMessage.style.display = 'block';

            // Автоматически скрываем через 5 секунд
            setTimeout(() => {
                verificationMessage.style.opacity = '0';
                verificationMessage.style.transition = 'opacity 0.5s';
                setTimeout(() => {
                    verificationMessage.style.display = 'none';
                    verificationMessage.style.opacity = '1';
                }, 500);
            }, 5000);
        }
    }

    // ========== УТИЛИТЫ ==========
    function getCsrfToken() {
        const name = 'csrftoken';
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

    function getUrlParameter(name) {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        const results = regex.exec(location.search);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ ==========

    // Проверяем хеш в URL при загрузке
    handleUrlNavigation();

    // Обрабатываем изменения hash в URL
    window.addEventListener('hashchange', handleUrlNavigation);

    // Инициализируем фильтрацию бронирований при загрузке (если активна вкладка бронирований)
    const activeTab = document.querySelector('.profile-tabs .tab-btn.active');
    if (activeTab && activeTab.dataset.tab === 'bookings') {
        initializeBookingFilters();
        initializeBookingActions();
    }

    // Инициализируем вкладку рейтинга при загрузке
    if (activeTab && activeTab.dataset.tab === 'rating') {
        initializeRatingTab();
    }

    // ФИКС: Принудительно обновляем прогресс бар после загрузки страницы
    setTimeout(() => {
        const progressBar = document.getElementById('progressBarFill');
        if (progressBar) {
            const currentWidth = progressBar.style.width;
            console.log('Финальная проверка прогресс бара. Текущая ширина:', currentWidth);

            // Если ширина неправильная, исправляем её
            if (!currentWidth || currentWidth === '0%' || currentWidth === '100%') {
                const progressText = document.querySelector('.progress-bar-text');
                if (progressText) {
                    const percentageText = progressText.textContent.replace('%', '');
                    const percentage = parseFloat(percentageText);
                    if (!isNaN(percentage)) {
                        progressBar.style.transition = 'width 0.5s ease-in-out';
                        progressBar.style.width = percentage + '%';
                        console.log('Исправлена ширина прогресс бара:', percentage + '%');
                    }
                }
            }
        }
    }, 500);
});