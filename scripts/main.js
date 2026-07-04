/* ============================================================
   ClipForge AI — Main JavaScript
   Handles: nav scroll, particles, counter animation, 
   testimonial slider, scroll reveal, hamburger menu
   ============================================================ */

'use strict';

// ── Nav scroll effect ────────────────────────────────────────────
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }, { passive: true });
}

// ── Hamburger Menu ───────────────────────────────────────────────
const hamburger   = document.getElementById('hamburger');
const mobileMenu  = document.getElementById('mobileMenu');

if (hamburger && mobileMenu) {
  hamburger.addEventListener('click', () => {
    const isOpen = mobileMenu.classList.toggle('open');
    hamburger.setAttribute('aria-expanded', isOpen);
  });

  // Close on mobile link click
  mobileMenu.querySelectorAll('.mobile-link').forEach(link => {
    link.addEventListener('click', () => {
      mobileMenu.classList.remove('open');
    });
  });
}

// ── Particle System ──────────────────────────────────────────────
function initParticles() {
  const container = document.getElementById('particles');
  if (!container) return;

  const PARTICLE_COUNT = 35;
  const colors = ['#7c3aed', '#06b6d4', '#f59e0b', '#10b981', '#ec4899'];

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const p = document.createElement('div');
    p.className = 'particle';

    const size   = Math.random() * 4 + 1;
    const color  = colors[Math.floor(Math.random() * colors.length)];
    const left   = Math.random() * 100;
    const delay  = Math.random() * 12;
    const duration = Math.random() * 15 + 10;

    p.style.cssText = `
      width: ${size}px;
      height: ${size}px;
      background: ${color};
      left: ${left}%;
      bottom: -20px;
      animation-duration: ${duration}s;
      animation-delay: -${delay}s;
      opacity: ${Math.random() * 0.6 + 0.2};
      box-shadow: 0 0 ${size * 3}px ${color};
    `;
    container.appendChild(p);
  }
}
initParticles();

// ── Counter Animation ─────────────────────────────────────────────
function animateCounter(el, target, suffix = '') {
  let start = 0;
  const duration = 2000;
  const step = 16;
  const increment = target / (duration / step);

  const timer = setInterval(() => {
    start += increment;
    if (start >= target) {
      start = target;
      clearInterval(timer);
    }
    el.textContent = Math.floor(start).toLocaleString() + suffix;
  }, step);
}

function initCounters() {
  const counterEls = document.querySelectorAll('[data-target]');
  if (!counterEls.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el     = entry.target;
          const target = parseInt(el.dataset.target, 10);
          const suffix = el.dataset.suffix || (target === 98 ? '%' : '+');
          animateCounter(el, target, suffix);
          observer.unobserve(el);
        }
      });
    },
    { threshold: 0.5 }
  );

  counterEls.forEach(el => observer.observe(el));
}
initCounters();

// ── Scroll Reveal ────────────────────────────────────────────────
function initScrollReveal() {
  const revealEls = document.querySelectorAll('.reveal');
  if (!revealEls.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
  );

  revealEls.forEach((el, i) => {
    el.style.transitionDelay = `${(i % 4) * 0.08}s`;
    observer.observe(el);
  });
}
initScrollReveal();

// ── Testimonial Slider ───────────────────────────────────────────
function initTestimonialSlider() {
  const track   = document.getElementById('testimonialsTrack');
  const prevBtn = document.getElementById('testiPrev');
  const nextBtn = document.getElementById('testiNext');
  const dotsContainer = document.getElementById('testiDots');
  if (!track) return;

  const cards = track.querySelectorAll('.testimonial-card');
  let current = 0;
  let autoPlayInterval;

  // Build dots
  if (dotsContainer) {
    cards.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.className = 'testi-dot' + (i === 0 ? ' active' : '');
      dot.setAttribute('aria-label', `Go to testimonial ${i + 1}`);
      dot.addEventListener('click', () => goTo(i));
      dotsContainer.appendChild(dot);
    });
  }

  function goTo(index) {
    current = Math.max(0, Math.min(index, cards.length - 1));
    const cardWidth = cards[0].offsetWidth + 24; // gap
    track.scrollTo({ left: cardWidth * current, behavior: 'smooth' });

    dotsContainer?.querySelectorAll('.testi-dot').forEach((dot, i) => {
      dot.classList.toggle('active', i === current);
    });
  }

  function next() { goTo(current < cards.length - 1 ? current + 1 : 0); }
  function prev() { goTo(current > 0 ? current - 1 : cards.length - 1); }

  if (nextBtn) nextBtn.addEventListener('click', () => { next(); resetAutoPlay(); });
  if (prevBtn) prevBtn.addEventListener('click', () => { prev(); resetAutoPlay(); });

  function startAutoPlay() {
    autoPlayInterval = setInterval(next, 5000);
  }
  function resetAutoPlay() {
    clearInterval(autoPlayInterval);
    startAutoPlay();
  }
  startAutoPlay();

  // Keyboard support
  document.addEventListener('keydown', (e) => {
    if (document.querySelector('.testimonials:hover')) {
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft')  prev();
    }
  });
}
initTestimonialSlider();

// ── Smooth anchor scroll ─────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', (e) => {
    const href = anchor.getAttribute('href');
    if (href === '#') return;
    const target = document.querySelector(href);
    if (target) {
      e.preventDefault();
      const offset = 80;
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  });
});

// ── Toast system ─────────────────────────────────────────────────
window.ClipForge = window.ClipForge || {};

window.ClipForge.toast = function(msg, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✅', error: '❌', info: '⚡' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || '⚡'}</span>
    <span class="toast-msg">${msg}</span>
    <button class="toast-close" aria-label="Close">✕</button>
  `;

  const closeBtn = toast.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => removeToast(toast));

  container.appendChild(toast);
  setTimeout(() => removeToast(toast), duration);
};

function removeToast(toast) {
  toast.style.opacity = '0';
  toast.style.transform = 'translateX(100%)';
  toast.style.transition = 'all 0.3s ease';
  setTimeout(() => toast.remove(), 300);
}

// ── Dashboard sidebar mobile ─────────────────────────────────────
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar       = document.querySelector('.sidebar');
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('mobile-open');
  });
}

// ── Upload Zone drag & drop ──────────────────────────────────────
function initUploadZone() {
  const zone = document.querySelector('.upload-zone');
  if (!zone) return;

  ['dragenter', 'dragover'].forEach(evt => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(evt => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (evt === 'drop') {
        const files = e.dataTransfer.files;
        if (files.length) handleFileSelect(files[0]);
      }
    });
  });

  const fileInput = document.getElementById('fileInput');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) handleFileSelect(e.target.files[0]);
    });
  }

  zone.addEventListener('click', () => fileInput?.click());
}

function handleFileSelect(file) {
  const allowed = ['video/mp4', 'video/webm', 'video/mov', 'video/avi', 'video/mkv'];
  if (!allowed.some(t => file.type.includes(t.split('/')[1]))) {
    window.ClipForge?.toast('Please upload a valid video file (MP4, MOV, AVI, MKV)', 'error');
    return;
  }
  window.ClipForge?.toast(`📁 File loaded: ${file.name}`, 'success');
  const zone = document.querySelector('.upload-zone');
  if (zone) {
    zone.innerHTML = `
      <div class="upload-zone-icon">🎬</div>
      <p class="upload-zone-title">${file.name}</p>
      <p class="upload-zone-sub">${(file.size / 1024 / 1024).toFixed(1)} MB • Click to change</p>
    `;
  }
}
initUploadZone();

// ── Game selector ────────────────────────────────────────────────
function initGameSelector() {
  const options = document.querySelectorAll('.game-option');
  options.forEach(opt => {
    opt.addEventListener('click', () => {
      options.forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
    });
  });
  // Default select first
  if (options.length) options[0].classList.add('selected');
}
initGameSelector();

// ── Toggle buttons ───────────────────────────────────────────────
document.querySelectorAll('.toggle').forEach(toggle => {
  toggle.addEventListener('click', () => {
    toggle.classList.toggle('on');
  });
});

// ── Settings tabs ────────────────────────────────────────────────
function initSettingsTabs() {
  const tabs    = document.querySelectorAll('.settings-tab');
  const panels  = document.querySelectorAll('.settings-panel');
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.style.display = 'none');
      tab.classList.add('active');
      const panel = document.getElementById(`panel-${target}`);
      if (panel) panel.style.display = 'block';
    });
  });

  // Show first
  if (tabs.length) tabs[0].click();
}
initSettingsTabs();

// ── Export clip selector ─────────────────────────────────────────
function initExportSelector() {
  const items = document.querySelectorAll('.export-clip-item');
  items.forEach(item => {
    item.addEventListener('click', () => {
      item.classList.toggle('selected');
      updateExportCount();
    });
  });
}
function updateExportCount() {
  const selected = document.querySelectorAll('.export-clip-item.selected').length;
  const counter  = document.getElementById('exportCount');
  if (counter) counter.textContent = selected;
}
initExportSelector();

// ── Modal ────────────────────────────────────────────────────────
window.ClipForge.openModal = function(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
};
window.ClipForge.closeModal = function(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
};

document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
});
document.querySelectorAll('.modal-close').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.closest('.modal-overlay')?.classList.remove('open');
  });
});

// ── Chart bars ───────────────────────────────────────────────────
function initCharts() {
  const chartArea = document.querySelector('.chart-area');
  if (!chartArea) return;

  const data = [3, 7, 5, 12, 9, 15, 11, 18, 14, 22, 19, 25, 21, 28];
  const max  = Math.max(...data);

  chartArea.innerHTML = '';
  data.forEach((val, i) => {
    const bar = document.createElement('div');
    bar.className = 'chart-bar' + (i === data.length - 1 ? ' highlight' : '');
    bar.style.height = `${(val / max) * 85}%`;
    bar.dataset.val  = val;
    chartArea.appendChild(bar);
  });
}
initCharts();

// ── AI Progress simulation ───────────────────────────────────────
window.ClipForge.simulateAnalysis = function() {
  const steps = document.querySelectorAll('.progress-step');
  if (!steps.length) return;

  const progressBar = document.getElementById('analysisProgressBar');
  const statusText  = document.getElementById('analysisStatus');

  const stepMeta = [
    { label: '✓ Download complete (2.1 GB)', time: 1500 },
    { label: '✓ Audio peaks detected: 14', time: 3000 },
    { label: '✓ YOLO scanning complete — 8 events', time: 6000 },
    { label: '✓ Rendering 5 clips in 9:16', time: 9000 },
    { label: '✓ Music sync & SFX applied', time: 11000 },
  ];

  steps.forEach(s => { s.classList.remove('step-done', 'step-active'); });

  if (steps[0]) {
    steps[0].classList.add('step-active');
    if (progressBar) progressBar.style.width = '5%';
    if (statusText)  statusText.textContent  = 'Downloading...';
  }

  stepMeta.forEach(({ label, time }, i) => {
    setTimeout(() => {
      if (steps[i]) {
        steps[i].classList.remove('step-active');
        steps[i].classList.add('step-done');
        const detail = steps[i].querySelector('.p-step-detail');
        if (detail) detail.textContent = label;
      }
      if (steps[i + 1]) steps[i + 1].classList.add('step-active');

      const pct = Math.round(((i + 1) / stepMeta.length) * 100);
      if (progressBar) progressBar.style.width = `${pct}%`;
      if (statusText)  statusText.textContent  = i < stepMeta.length - 1
        ? ['Downloading...', 'Analyzing audio...', 'Running YOLO...', 'Rendering clips...', 'Applying music...'][i + 1]
        : '✅ Clips ready!';

      if (i === stepMeta.length - 1) {
        window.ClipForge?.toast('🎬 5 clips are ready to preview!', 'success');
      }
    }, time);
  });
};

// ── Pricing toggle (annual/monthly) ─────────────────────────────
function initPricingToggle() {
  const toggle = document.getElementById('billingToggle');
  const prices = document.querySelectorAll('[data-monthly][data-annual]');

  if (!toggle || !prices.length) return;

  toggle.addEventListener('click', () => {
    const isAnnual = toggle.classList.toggle('on');
    prices.forEach(el => {
      el.textContent = isAnnual ? el.dataset.annual : el.dataset.monthly;
    });
    const label = document.getElementById('billingLabel');
    if (label) label.textContent = isAnnual ? 'Annual (save 20%)' : 'Monthly';
  });
}
initPricingToggle();

// ── Active nav link (dashboard) ──────────────────────────────────
function initActiveNavLinks() {
  const links = document.querySelectorAll('.sidebar-link[data-page]');
  const current = window.location.pathname.split('/').pop() || 'index.html';

  links.forEach(link => {
    if (link.dataset.page === current) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}
initActiveNavLinks();

console.log('%c⚡ ClipForge AI', 'color:#7c3aed;font-size:18px;font-weight:bold');
console.log('%cBuilt for gamers, by gamers. 🎮', 'color:#06b6d4;font-size:12px');
