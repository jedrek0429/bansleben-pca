/*! PCA static runtime: small first-party replacement for the WordPress/Divi runtime used by the static site. */
(function () {
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

  function addStaticCss() {
    if (document.getElementById('pca-static-runtime-css')) return;

    var css = [
      '.et_animated,.et_had_animation,.et_pb_animation_top,.et_pb_animation_bottom,.et_pb_animation_left,.et_pb_animation_right,.et_pb_animation_fade_in{opacity:1!important;transform:none!important;animation:none!important;}',
      '.et_pb_section_hague,.et_pb_section_hague *{visibility:visible!important;}',
      '@media (min-width:981px){',
      'body.custom-background{background-color:#fff!important;}',
      'body.et_fixed_nav #page-container{padding-top:87px!important;}',
      '#main-header{position:fixed!important;top:0!important;left:0!important;right:0!important;height:87px!important;background:#fff!important;box-shadow:0 1px 0 rgba(0,0,0,.08)!important;transition:height .25s ease,box-shadow .25s ease!important;}',
      '#main-header.et-fixed-header{height:54px!important;box-shadow:0 0 7px rgba(0,0,0,.1)!important;}',
      '#main-header .container.et_menu_container{display:flex!important;align-items:center!important;justify-content:space-between!important;height:100%!important;}',
      '#main-header .logo_container{position:relative!important;inset:auto!important;height:auto!important;flex:0 0 auto!important;display:flex!important;align-items:center!important;}',
      '#main-header .logo_helper{display:none!important;}',
      '#main-header #logo{display:block!important;width:auto!important;max-width:360px!important;max-height:65px!important;transition:max-height .25s ease!important;}',
      '#main-header.et-fixed-header #logo{max-height:42px!important;}',
      '#et-top-navigation{float:none!important;display:flex!important;align-items:center!important;height:100%!important;width:auto!important;max-width:none!important;margin-left:auto!important;padding:0!important;transition:none!important;}',
      '#main-header.et-fixed-header #et-top-navigation{padding:0!important;}',
      '#top-menu{display:flex!important;align-items:center!important;margin:0!important;padding:0!important;white-space:nowrap!important;}',
      '#top-menu>li{display:flex!important;align-items:center!important;padding-right:22px!important;}',
      '#top-menu>li>a{display:flex!important;align-items:center!important;height:54px!important;padding:0!important;line-height:1.25!important;transition:color .2s ease!important;}',
      '#et_mobile_nav_menu{display:none!important;}',
      '}',
    ].join('\n');

    var style = document.createElement('style');
    style.id = 'pca-static-runtime-css';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function updateFixedHeader() {
    var header = document.getElementById('main-header');
    if (!header) return;
    header.classList.toggle('et-fixed-header', window.scrollY > 10);
  }

  function initMobileMenu() {
    document.querySelectorAll('.mobile_menu_bar_toggle').forEach(function (toggle) {
      if (toggle.dataset.pcaBound === '1') return;
      toggle.dataset.pcaBound = '1';

      toggle.addEventListener('click', function (event) {
        var nav = toggle.closest('.mobile_nav');
        if (!nav) return;

        event.preventDefault();
        event.stopPropagation();

        var shouldOpen = !nav.classList.contains('opened');
        nav.classList.toggle('opened', shouldOpen);
        nav.classList.toggle('closed', !shouldOpen);
      });
    });
  }

  function revealStaticAnimatedContent() {
    document.querySelectorAll('.et_animated,.et_had_animation,.et_pb_animation_top,.et_pb_animation_bottom,.et_pb_animation_left,.et_pb_animation_right,.et_pb_animation_fade_in').forEach(function (node) {
      node.style.opacity = '1';
      node.style.transform = 'none';
      node.style.animation = 'none';
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

  function init() {
    addStaticCss();
    revealStaticAnimatedContent();
    initMobileMenu();
    initContactMessages();
    updateFixedHeader();

    var refresh = rafDebounce(function () {
      addStaticCss();
      revealStaticAnimatedContent();
      updateFixedHeader();
    });

    window.addEventListener('scroll', updateFixedHeader, { passive: true });
    window.addEventListener('resize', refresh, { passive: true });
    window.addEventListener('orientationchange', refresh);
    window.addEventListener('load', refresh);
  }

  addStaticCss();
  ready(init);
})();
