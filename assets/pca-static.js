/*! PCA static runtime: small first-party replacement for WordPress/Divi JavaScript behavior. */
(function () {
  var PHONE_MAX_WIDTH = 767;
  var REVEAL_SELECTOR = '.et_animated,.et_had_animation,.et_pb_animation_top,.et_pb_animation_bottom,.et_pb_animation_left,.et_pb_animation_right,.et_pb_animation_fade_in';

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
    root.querySelectorAll('.mobile_nav.opened').forEach(function (nav) {
      nav.classList.remove('opened');
      nav.classList.add('closed');
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
    root.classList.toggle('et-fixed-header', window.scrollY > 10);
  }

  function initMobileMenu() {
    document.querySelectorAll('.mobile_menu_bar_toggle, .mobile_menu_bar').forEach(function (toggle) {
      if (toggle.dataset.pcaBound === '1') return;
      toggle.dataset.pcaBound = '1';

      toggle.addEventListener('click', function (event) {
        var nav = toggle.closest('.mobile_nav');
        if (!nav) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        var shouldOpen = !nav.classList.contains('opened');
        nav.classList.toggle('opened', shouldOpen);
        nav.classList.toggle('closed', !shouldOpen);
      }, true);
    });
  }

  function revealNow(node) {
    node.classList.add('pca-in-view');
    node.classList.remove('et-waypoint');
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
        ? 'Thank you. Your message has been sent.'
        : 'Sorry, your message could not be sent. Please check your e-mail address and try again.';

      form.insertBefore(message, form.firstChild);
    });
  }

  function refresh() {
    updateHeaderMode();
    updateFixedHeader();
  }

  function init() {
    initMobileMenu();
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
