// =========================================================================
// COMMON.JS — Utilitaires partagés entre toutes les pages
// =========================================================================

const API_BASE = '';

// Couleurs officielles des écuries F1
const TEAM_COLORS = {
    'Red Bull Racing': '#3671C6',
    'Ferrari': '#E80020',
    'McLaren': '#FF8000',
    'Mercedes': '#27F4D2',
    'Aston Martin': '#229971',
    'Alpine': '#FF87BC',
    'Williams': '#64C4FF',
    'Racing Bulls': '#6692FF',
    'RB': '#6692FF',
    'Haas F1 Team': '#B6BABD',
    'Kick Sauber': '#52E252',
    'Audi': '#52E252',
    'Cadillac': '#FFD700',
};

// =========================================================================
// THEME TOGGLE (Light / Dark)
// =========================================================================
function initTheme() {
    const saved = localStorage.getItem('f1-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('f1-theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.querySelector('.theme-toggle');
    if (btn) {
        btn.innerHTML = theme === 'dark' 
            ? '<span class="icon">☀️</span><span>Mode Clair</span>'
            : '<span class="icon">🌙</span><span>Mode Sombre</span>';
    }
}

// =========================================================================
// NAVIGATION — Mettre en surbrillance le lien actif
// =========================================================================
function initNavigation() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === path || 
            (path === '/' && link.getAttribute('href') === '/')) {
            link.classList.add('active');
        }
    });
}

// =========================================================================
// FETCH HELPER
// =========================================================================
async function apiFetch(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        return null;
    }
}

// =========================================================================
// LOADING STATE
// =========================================================================
function showLoading(containerId) {
    const el = document.getElementById(containerId);
    if (el) {
        if (el.tagName.toLowerCase() === 'div' && !el.classList.contains('skeleton-container')) {
            el.innerHTML = `
                <div class="skeleton-container" style="padding: 12px 0;">
                    <div class="skeleton skeleton-table-row"></div>
                    <div class="skeleton skeleton-table-row"></div>
                    <div class="skeleton skeleton-table-row"></div>
                    <div class="skeleton skeleton-table-row" style="opacity: 0.5;"></div>
                </div>`;
        }
    }
}

function hideLoading(containerId) {
    const el = document.getElementById(containerId);
    if (el) {
        const loader = el.querySelector('.skeleton-container');
        if (loader) loader.remove();
    }
}

// =========================================================================
// TOAST NOTIFICATIONS
// =========================================================================
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    
    container.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after 3s
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400); // wait for exit animation
    }, 3000);
}

// =========================================================================
// POSITION BADGE
// =========================================================================
function positionBadge(pos) {
    const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
    return `<span class="position-badge ${cls}">P${pos}</span>`;
}

// =========================================================================
// SIDEBAR HTML (injecté dans chaque page)
// =========================================================================
function renderSidebar() {
    return `
        <aside class="sidebar">
            <a href="/" class="sidebar-logo">
                <span>F1<span class="accent">Pred</span> <small style="font-size:11px;color:var(--text-muted);font-weight:400;">by Tsihoarana</small></span>
            </a>
            <nav class="sidebar-nav">
                <a href="/" class="nav-link">
                    <span class="icon">📊</span>
                    <span class="nav-text">Dashboard</span>
                </a>
                <a href="/prediction" class="nav-link">
                    <span class="icon">🔮</span>
                    <span class="nav-text">Prédiction</span>
                </a>
                <a href="/perso" class="nav-link">
                    <span class="icon">👤</span>
                    <span class="nav-text">Perso</span>
                </a>
            </nav>
            <button class="theme-toggle" onclick="toggleTheme()">
                <span class="icon">🌙</span>
                <span>Mode Sombre</span>
            </button>
        </aside>`;
}

// =========================================================================
// INIT — Appelé au chargement de chaque page
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
});
