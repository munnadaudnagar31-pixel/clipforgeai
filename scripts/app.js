/**
 * ClipForge AI — API Client & Auth Layer
 * ───────────────────────────────────────
 * Provides:
 *   CF.api.post/get/del      — authenticated fetch wrappers
 *   CF.auth.register()       — POST /api/auth/register
 *   CF.auth.login()          — POST /api/auth/login
 *   CF.auth.me()             — GET  /api/auth/me
 *   CF.auth.logout()         — clear token + redirect
 *   CF.auth.requireAuth()    — redirect to auth.html if no token
 *   CF.auth.populateDash()   — fill sidebar/stats from real API data
 *   CF.videos.submitUrl()    — POST /api/videos/ingest-url
 *   CF.videos.pollStatus()   — GET  /api/videos/{id}/status
 */

'use strict';

const CF = window.ClipForge = window.ClipForge || {};

// ── Config ────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000';
const TOKEN_KEY = 'token';
const USER_KEY  = 'cf_user_profile';

// ── Token Helpers ─────────────────────────────────────────────────
CF.token = {
  get()        { return localStorage.getItem(TOKEN_KEY); },
  set(t)       { localStorage.setItem(TOKEN_KEY, t); },
  clear()      { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); },
  headers()    {
    const t = this.get();
    return t
      ? { 'Content-Type': 'application/json', 'Authorization': `Bearer ${t}` }
      : { 'Content-Type': 'application/json' };
  },
};

// ── Storage Helpers ───────────────────────────────────────────────
CF.storage = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(`cf_${key}`); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(`cf_${key}`, JSON.stringify(value)); } catch(e) { console.warn('Storage error', e); }
  },
  remove(key) { localStorage.removeItem(`cf_${key}`); },
};

// ── API Fetch Wrappers ────────────────────────────────────────────
CF.api = {
  async post(path, body = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: CF.token.headers(),
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
    return data;
  },

  async get(path) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'GET',
      headers: CF.token.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) {
        CF.token.clear();
        window.location.href = 'auth.html';
        return;
      }
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    return data;
  },

  async del(path) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'DELETE',
      headers: CF.token.headers(),
    });
    return res.ok;
  },
};

// ── Auth ──────────────────────────────────────────────────────────
CF.auth = {
  /**
   * Register: POST /api/auth/register
   * Stores JWT, redirects to dashboard.
   */
  async register(name, email, password) {
    const data = await CF.api.post('/api/auth/register', { name, email, password });
    CF.token.set(data.access_token);
    // Fetch profile right away
    const profile = await CF.api.get('/api/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(profile));
    return profile;
  },

  /**
   * Login: POST /api/auth/login (JSON)
   * Stores JWT, returns user profile.
   */
  async login(email, password) {
    const data = await CF.api.post('/api/auth/login', { email, password });
    CF.token.set(data.access_token);
    const profile = await CF.api.get('/api/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(profile));
    return profile;
  },

  /**
   * Fetch current user profile (reads from cache first).
   * If token is invalid, clears it and returns null.
   */
  async me(forceRefresh = false) {
    const cached = localStorage.getItem(USER_KEY);
    if (cached && !forceRefresh) {
      try { return JSON.parse(cached); } catch { /**/ }
    }
    try {
      const profile = await CF.api.get('/api/auth/me');
      localStorage.setItem(USER_KEY, JSON.stringify(profile));
      return profile;
    } catch {
      CF.token.clear();
      return null;
    }
  },

  /**
   * Logout: clear token + redirect.
   */
  logout() {
    CF.api.post('/api/auth/logout').catch(() => {});
    CF.token.clear();
    window.location.href = 'auth.html';
  },

  /**
   * Route guard: call this on every protected page.
   * If not authenticated → redirect to auth.html.
   * Returns the user profile if authenticated.
   */
  async requireAuth() {
    if (!CF.token.get()) {
      window.location.href = 'auth.html';
      return null;
    }
    const user = await CF.auth.me();
    if (!user) {
      window.location.href = 'auth.html';
      return null;
    }
    return user;
  },

  /**
   * Populate dashboard sidebar and stat cards with live API data.
   */
  async populateDash() {
    const user = await CF.auth.requireAuth();
    if (!user) return;

    // ── Sidebar ────────────────────────────────────────────────
    const nameEl = document.querySelector('.user-name');
    const planEl = document.querySelector('.user-plan');
    const avEl   = document.querySelector('.user-avatar');
    const initials = user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    if (nameEl) nameEl.textContent = user.name;
    if (planEl) planEl.textContent = `⚡ ${user.plan.charAt(0).toUpperCase() + user.plan.slice(1)} Plan`;
    if (avEl)   avEl.textContent   = initials;

    // ── Logout button ──────────────────────────────────────────
    document.querySelectorAll('[data-action="logout"]').forEach(btn => {
      btn.addEventListener('click', e => { e.preventDefault(); CF.auth.logout(); });
    });

    // ── Stat cards (if on dashboard) ──────────────────────────
    try {
      const [clips, videos] = await Promise.all([
        CF.api.get('/api/clips/'),
        CF.api.get('/api/videos/'),
      ]);

      const totalViews = clips.reduce((s, c) => s + (c.view_count || 0), 0);
      const readyClips = clips.filter(c => c.status === 'ready').length;

      const $$ = id => document.getElementById(id);
      if ($$('stat-clips'))     $$('stat-clips').textContent     = clips.length;
      if ($$('stat-views'))     $$('stat-views').textContent     = CF.ui.formatNum(totalViews);
      if ($$('stat-published')) $$('stat-published').textContent = clips.filter(c => c.cdn_url).length;
      if ($$('stat-usage'))     $$('stat-usage').textContent     = `${user.clips_used_this_month}/${_planLimit(user.plan)}`;

      const pct = Math.round((user.clips_used_this_month / _planLimit(user.plan)) * 100);
      const bar = $$('planBar');
      if (bar) {
        bar.style.width = pct + '%';
        bar.className = 'usage-bar-fill' + (pct > 90 ? ' danger' : pct > 70 ? ' warning' : '');
      }
      const planText = $$('planUsageText');
      if (planText) planText.textContent = `${user.clips_used_this_month} / ${_planLimit(user.plan)}`;

    } catch (e) {
      console.warn('[CF.auth.populateDash] Could not load stats:', e.message);
    }

    return user;
  },
};

function _planLimit(plan) {
  return { free: 3, pro: 30, creator: 9999, agency: 9999 }[plan] || 3;
}

// ── Videos (clip generation) ──────────────────────────────────────
CF.videos = CF.videos || {};

/**
 * Submit a URL for processing.
 * Returns { video_id, status }
 */
CF.videos.submitUrl = async function(url, options = {}) {
  return CF.api.post('/api/videos/ingest-url', {
    url,
    game:          options.game          || 'BGMI',
    max_clips:     options.max_clips     || 5,
    clip_duration: options.clip_duration || 30,
    quality:       options.quality       || '1080p',
    aspect:        options.aspect        || '9:16',
    watermark:     options.watermark     !== false,
  });
};

/**
 * Poll video processing status.
 * Returns { status, clips_count, clips[] }
 */
CF.videos.pollStatus = async function(videoId) {
  return CF.api.get(`/api/videos/${videoId}/status`);
};

/**
 * Start polling and call callbacks on progress and completion.
 * @param {string} videoId
 * @param {function} onProgress  — called with { status, clips_count }
 * @param {function} onComplete  — called with clips[]
 * @param {function} onError     — called with error message string
 * @param {number}   intervalMs  — poll every N ms (default 3000)
 */
CF.videos.startPolling = function(videoId, { onProgress, onComplete, onError, intervalMs = 3000 } = {}) {
  let timer;

  async function poll() {
    try {
      const data = await CF.videos.pollStatus(videoId);
      onProgress && onProgress(data);

      if (data.status === 'done') {
        clearInterval(timer);
        onComplete && onComplete(data.clips || []);
      } else if (data.status === 'failed') {
        clearInterval(timer);
        onError && onError(data.error_msg || 'Processing failed.');
      }
    } catch (e) {
      clearInterval(timer);
      onError && onError(e.message);
    }
  }

  poll();  // immediate first check
  timer = setInterval(poll, intervalMs);
  return () => clearInterval(timer);  // return cancel function
};

// ── UI Helpers ────────────────────────────────────────────────────
CF.ui = CF.ui || {};
CF.ui.formatNum = function(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000)    return (n / 1000).toFixed(1) + 'K';
  return String(n);
};

CF.ui.statusBadge = function(status) {
  const map = {
    ready:     '<span class="status-badge status-done">Ready</span>',
    rendering: '<span class="status-badge status-render">Rendering</span>',
    queued:    '<span class="status-badge status-queue">Queued</span>',
    failed:    '<span class="status-badge status-fail">Failed</span>',
  };
  return map[status] || '';
};

CF.ui.clipGradient = function(type) {
  const map = {
    kill:    'linear-gradient(135deg,rgba(124,58,237,0.25),rgba(6,182,212,0.1))',
    funny:   'linear-gradient(135deg,rgba(245,158,11,0.2),rgba(236,72,153,0.1))',
    victory: 'linear-gradient(135deg,rgba(16,185,129,0.2),rgba(6,182,212,0.1))',
    audio:   'linear-gradient(135deg,rgba(6,182,212,0.2),rgba(124,58,237,0.1))',
  };
  return map[type] || map.kill;
};

// ── Toast system ──────────────────────────────────────────────────
CF.toast = function(msg, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: '⚡' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || '⚡'}</span><span class="toast-msg">${msg}</span><button class="toast-close" onclick="this.parentElement.remove()">✕</button>`;
  container.appendChild(toast);
  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s';
      setTimeout(() => toast.remove(), 300);
    }
  }, duration);
};

// ── Modal ─────────────────────────────────────────────────────────
CF.openModal  = id => document.getElementById(id)?.classList.add('open');
CF.closeModal = id => document.getElementById(id)?.classList.remove('open');

// ── Active nav ────────────────────────────────────────────────────
CF.setActiveNav = function() {
  const page = window.location.pathname.split('/').pop();
  document.querySelectorAll('.sidebar-link[data-page]').forEach(link => {
    link.classList.toggle('active', link.dataset.page === page);
  });
};

// ── Settings toggles ──────────────────────────────────────────────
CF.syncSettingToggles = function() {
  const stored = CF.storage.get('settings', {});
  document.querySelectorAll('.toggle[data-setting]').forEach(toggle => {
    const key = toggle.dataset.setting;
    if (stored[key]) toggle.classList.add('on'); else toggle.classList.remove('on');
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('on');
      CF.storage.set('settings', { ...CF.storage.get('settings', {}), [key]: toggle.classList.contains('on') });
    });
  });
};

CF.syncFormInputs = function() {
  const stored = CF.storage.get('settings', {});
  document.querySelectorAll('[data-setting-input]').forEach(input => {
    const key = input.dataset.settingInput;
    if (stored[key] !== undefined) input.value = stored[key];
    input.addEventListener('change', () => {
      CF.storage.set('settings', { ...CF.storage.get('settings', {}), [key]: input.value });
    });
  });
};

// ── AI Job Simulation (fallback if API unavailable) ───────────────
CF.simulateJob = function(videoId, onProgress, onComplete) {
  const steps = [
    { label:'Downloading stream...', detail:'yt-dlp downloading...', pct:8,  delay:0    },
    { label:'Download complete',     detail:'✓ Video ready',         pct:18, delay:1800 },
    { label:'Analyzing audio...',    detail:'librosa RMS peaks...',   pct:32, delay:3200 },
    { label:'Audio peaks: 14 found', detail:'✓ 14 spikes detected',  pct:45, delay:5000 },
    { label:'YOLO scanning frames...', detail:'Game UI detection...', pct:60, delay:6500 },
    { label:'8 game events found',   detail:'✓ 5 kills, 1 victory',  pct:74, delay:9500 },
    { label:'Scoring highlights...', detail:'Fusion weighting...',    pct:82, delay:11000},
    { label:'Rendering 9:16 clips...', detail:'FFmpeg encoding...',   pct:90, delay:13000},
    { label:'Finalising clips',       detail:'Almost done...',        pct:96, delay:15500},
    { label:'✅ Done!',               detail:'5 clips ready',         pct:100,delay:17000},
  ];

  steps.forEach(({ label, detail, pct, delay }) => {
    setTimeout(() => { onProgress && onProgress({ label, detail, pct }); }, delay);
  });

  setTimeout(() => {
    const game = CF.storage.get('lastSelectedGame') || 'BGMI';
    const clips = [
      { title:'AI-Generated Kill Highlight', clip_type:'kill',    status:'ready', duration:30, ai_score:parseFloat((8+Math.random()).toFixed(1)) },
      { title:'Funny Moment Detected',       clip_type:'funny',   status:'ready', duration:15, ai_score:parseFloat((7+Math.random()).toFixed(1)) },
      { title:'Victory Screen Clip',         clip_type:'victory', status:'ready', duration:35, ai_score:parseFloat((9+Math.random()).toFixed(1)) },
    ];
    onComplete && onComplete(clips);
  }, 17500);
};

// ── Global init ───────────────────────────────────────────────────
CF.init = function() {
  CF.setActiveNav();
  CF.syncSettingToggles();
  CF.syncFormInputs();
};

document.addEventListener('DOMContentLoaded', () => CF.init());
