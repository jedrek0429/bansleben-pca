(function () {
  function onReady(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  function debounceFrame(callback) {
    var frame = null;

    return function () {
      if (frame) window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(function () {
        frame = null;
        callback();
      });
    };
  }

  function initHeader() {
    var body = document.body;
    var header = document.getElementById('main-header');
    if (!header) return;

    var container = header.querySelector('.container.et_menu_container') || header;
    var logo = header.querySelector('.logo_container');
    var topMenu = header.querySelector('#top-menu');
    var topMenuNav = header.querySelector('#top-menu-nav');
    var mobileNav = header.querySelector('#et_mobile_nav_menu');

    function updateFixedHeader() {
      header.classList.toggle('et-fixed-header', window.scrollY > 10);
    }

    function visibleMenuItems() {
      if (!topMenu) return [];

      return Array.prototype.slice.call(topMenu.children).filter(function (item) {
        return item.offsetWidth || item.offsetHeight;
      });
    }

    function menuItemsWrap(items) {
      items = items || visibleMenuItems();
      if (items.length < 2) return false;

      var firstTop = items[0].getBoundingClientRect().top;
      return items.some(function (item) {
        return Math.abs(item.getBoundingClientRect().top - firstTop) > 2;
      });
    }

    function menuItemsWidth(items) {
      return items.reduce(function (total, item) {
        return total + item.getBoundingClientRect().width;
      }, 0);
    }

    function closeMobileMenu() {
      header.querySelectorAll('.mobile_nav.opened').forEach(function (nav) {
        nav.classList.remove('opened');
        nav.classList.add('closed');
      });
    }

    function setResponsiveNav(useMobile) {
      header.classList.toggle('pca-mobile-nav-active', useMobile);
      header.classList.toggle('pca-desktop-nav-active', !useMobile);
      body.classList.toggle('pca-mobile-nav-active', useMobile);

      if (!useMobile) closeMobileMenu();
    }

    function desktopMenuDoesNotFit() {
      if (!topMenu || !topMenuNav || !mobileNav) return false;

      body.classList.add('pca-measuring-nav');
      header.classList.remove('pca-mobile-nav-active', 'pca-desktop-nav-active');
      body.classList.remove('pca-mobile-nav-active');

      var containerBox = container.getBoundingClientRect();
      var logoBox = logo ? logo.getBoundingClientRect() : { right: containerBox.left, width: 0 };
      var menuBox = topMenu.getBoundingClientRect();
      var items = visibleMenuItems();
      var safeGap = 16;
      var reservedLeft = Math.max(212, logoBox.width + safeGap);
      var menuWidth = Math.max(menuItemsWidth(items), topMenu.scrollWidth || 0);
      var fitsAvailableWidth = reservedLeft + menuWidth <= containerBox.width + 1;
      var fitsRight = menuBox.right <= containerBox.right + 1;
      var fitsLeft = menuBox.left >= logoBox.right + safeGap;
      var fitsOneLine = !menuItemsWrap(items);

      body.classList.remove('pca-measuring-nav');

      return !(fitsAvailableWidth && fitsRight && fitsLeft && fitsOneLine);
    }

    function updateResponsiveNav() {
      updateFixedHeader();
      setResponsiveNav(desktopMenuDoesNotFit());
    }

    var refreshResponsiveNav = debounceFrame(updateResponsiveNav);

    document.querySelectorAll('.mobile_menu_bar_toggle').forEach(function (toggle) {
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

    updateResponsiveNav();
    window.addEventListener('scroll', updateFixedHeader, { passive: true });
    window.addEventListener('resize', refreshResponsiveNav, { passive: true });
    window.addEventListener('orientationchange', refreshResponsiveNav);
    window.addEventListener('load', refreshResponsiveNav);

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(refreshResponsiveNav);
    }

    if (window.ResizeObserver) {
      new ResizeObserver(refreshResponsiveNav).observe(container);
    }
  }

  function showStaticFormMessage() {
    var sent = new URLSearchParams(location.search).get('sent');
    if (sent !== '1' && sent !== '0') return;

    document.querySelectorAll('form.static_contact_form').forEach(function (form) {
      var container = form.closest('.et_pb_contact_form_container');
      var diviMessage = container ? container.querySelector('.et-pb-contact-message') : null;

      if (diviMessage) {
        diviMessage.textContent = '';
        diviMessage.style.display = '';
      }

      if (form.querySelector('.static-form-message')) return;

      var message = document.createElement('div');
      message.className = 'static-form-message';
      message.textContent = sent === '1'
        ? 'Thank you. Your message has been sent.'
        : 'Sorry, your message could not be sent. Please check your e-mail address and try again.';

      form.insertBefore(message, form.firstChild);
    });
  }

  onReady(function () {
    initHeader();
    showStaticFormMessage();
  });
})();
