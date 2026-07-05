/*! PCA static runtime: small first-party behavior for navigation, reveal effects, and contact messages. */
(function () {
  var PHONE_MAX_WIDTH = 900;
  var REVEAL_SELECTOR = '.pca-reveal, .pca-card, .pca-contact';

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  function rafDebounce(callback) {
    var frame = 0;
    return function () {
      if (frame) window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(function () {
        frame = 0;
        callback();
      });
    };
  }

  function isPhoneLayout() {
    return window.matchMedia('(max-width: ' + PHONE_MAX_WIDTH + 'px)').matches;
  }

  function header() {
    return document.getElementById('main-header');
  }

  function closeMobileMenu(root) {
    root.querySelectorAll('.pca-mobile-nav.opened').forEach(function (nav) {
      nav.classList.remove('opened');
      nav.classList.add('closed');
      var toggle = nav.querySelector('.pca-mobile-menu-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
  }

  function updateHeaderMode() {
    var root = header();
    if (!root) return;

    var phone = isPhoneLayout();
    root.classList.toggle('pca-mobile-nav-active', phone);
    root.classList.toggle('pca-desktop-nav-active', !phone);
    document.body.classList.toggle('pca-mobile-nav-active', phone);

    if (!phone) {
      closeMobileMenu(root);
    }
  }

  function updateFixedHeader() {
    var root = header();
    if (!root) return;
    root.classList.toggle('pca-header-compact', window.scrollY > 10);

    document.querySelectorAll('.pca-scroll-top').forEach(function (button) {
      button.classList.toggle('is-visible', window.scrollY > 400);
    });
  }

  function initMobileMenu() {
    document.querySelectorAll('.pca-mobile-menu-toggle').forEach(function (toggle) {
      if (toggle.dataset.pcaBound === '1') return;
      toggle.dataset.pcaBound = '1';

      toggle.addEventListener('click', function (event) {
        var nav = toggle.closest('.pca-mobile-nav');
        if (!nav) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        var shouldOpen = !nav.classList.contains('opened');
        nav.classList.toggle('opened', shouldOpen);
        nav.classList.toggle('closed', !shouldOpen);
        toggle.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
      }, true);
    });
  }

  function initScrollTop() {
    document.querySelectorAll('.pca-scroll-top').forEach(function (button) {
      if (button.dataset.pcaBound === '1') return;
      button.dataset.pcaBound = '1';
      button.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    });
  }

  function revealNow(node) {
    node.classList.add('pca-in-view');
  }

  function initReveals() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll(REVEAL_SELECTOR));
    if (!nodes.length) return;

    if (!('IntersectionObserver' in window)) {
      nodes.forEach(revealNow);
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        revealNow(entry.target);
        observer.unobserve(entry.target);
      });
    }, {
      root: null,
      rootMargin: '0px 0px -12% 0px',
      threshold: 0.15
    });

    nodes.forEach(function (node) {
      observer.observe(node);
    });
  }

  function initContactMessages() {
    var sent = new URLSearchParams(location.search).get('sent');
    if (sent !== '1' && sent !== '0') return;

    document.querySelectorAll('form.static_contact_form').forEach(function (form) {
      if (form.querySelector('.static-form-message')) return;

      var message = document.createElement('div');
      message.className = 'static-form-message';
      message.textContent = sent === '1'
        ? form.dataset.messageSuccess
        : form.dataset.messageError;

      form.insertBefore(message, form.firstChild);
    });
  }

  function refresh() {
    updateHeaderMode();
    updateFixedHeader();
  }

  function init() {
    initMobileMenu();
    initScrollTop();
    initContactMessages();
    initReveals();
    refresh();

    var refreshLater = rafDebounce(refresh);
    window.addEventListener('scroll', updateFixedHeader, { passive: true });
    window.addEventListener('resize', refreshLater, { passive: true });
    window.addEventListener('orientationchange', refreshLater);
    window.addEventListener('load', refreshLater);

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(refreshLater);
    }
  }

  ready(init);
})();