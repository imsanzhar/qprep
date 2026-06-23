// --- 1. МГНОВЕННАЯ ТЕМА (Чтобы экран не моргал) ---
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);

// --- 2. ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ ВСЕХ СТРАНИЦ ---
window.saveActivityMinutes = function(minutesSpent) {
    if (minutesSpent < 1) minutesSpent = 1;
    const activityLog = JSON.parse(localStorage.getItem('study_activity')) || {};
    const today = new Date();
    const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    
    activityLog[dateStr] = (activityLog[dateStr] || 0) + minutesSpent;
    localStorage.setItem('study_activity', JSON.stringify(activityLog));
    console.log(`Активность сохранена: ${minutesSpent} мин.`);
};
window.saveModuleResult = function(moduleType, score, maxScore) {
    const history = JSON.parse(localStorage.getItem('module_history')) || [];
    const today = new Date();
    const dateStr = `${String(today.getDate()).padStart(2, '0')}.${String(today.getMonth() + 1).padStart(2, '0')}.${today.getFullYear()}`;
    
    history.push({
        type: moduleType,
        score: score,
        maxScore: maxScore,
        date: dateStr
    });
    localStorage.setItem('module_history', JSON.stringify(history));
};

document.addEventListener('DOMContentLoaded', () => {
    // --- 3. КНОПКА СМЕНЫ ТЕМЫ ---
    const themeToggleBtn = document.getElementById('themeToggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            let current = document.documentElement.getAttribute('data-theme');
            let newTheme = current === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    // --- 4. ВЫПАДАЮЩЕЕ МЕНЮ ПРОФИЛЯ ---
    const profileBtn = document.getElementById('userProfileBtn');
    const dropdown = document.getElementById('profileDropdown');
    
    if (profileBtn && dropdown) {
        profileBtn.addEventListener('click', (e) => {
            if(e.target.closest('#profileDropdown')) return; 
            dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
        });

        document.addEventListener('click', (e) => {
            if (!profileBtn.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    }
});

// Единая функция — вызывай её где угодно после изменения профиля
window.loadHeaderProfile = function() {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const profile = JSON.parse(localStorage.getItem('user_profile')) || {};

    // Имя
    const nameEl = document.getElementById('user-display-name');
    if (nameEl && profile.firstName) {
        nameEl.innerText = profile.firstName;
    }

    // Буква аватара
    const letterEl = document.getElementById('avatar-letter') || document.getElementById('header-avatar-letter');
    if (letterEl && profile.firstName) {
        letterEl.innerText = profile.firstName.charAt(0).toUpperCase();
    }

    // Фото аватара — всегда применяем последним, чтобы перекрыть букву
    const imgEl = document.getElementById('header-avatar-img');
    if (imgEl) {
        if (profile.avatar) {
            imgEl.src = profile.avatar;
            imgEl.style.display = 'block';
            if (letterEl) letterEl.style.display = 'none';
        } else {
            imgEl.style.display = 'none';
            if (letterEl) letterEl.style.display = '';
        }
    }
}

document.addEventListener('DOMContentLoaded', window.loadHeaderProfile);