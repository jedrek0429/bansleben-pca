/*! PCA static-site compatibility loader. The replacement runtime lives in /assets/pca-static.js. */
(function () {
  window.et_animation_data = window.et_animation_data || [];

  if (window.__pcaStaticRuntimeLoading) return;
  window.__pcaStaticRuntimeLoading = true;

  function staticRuntimeUrl() {
    var current = document.currentScript && document.currentScript.src;
    if (current) {
      return current.replace(/\/wp-content\/themes\/Divi\/js\/custom\.unified\.js(?:\?.*)?$/, '/assets/pca-static.js');
    }
    return '/assets/pca-static.js';
  }

  var script = document.createElement('script');
  script.defer = true;
  script.src = staticRuntimeUrl();
  script.id = 'pca-static-runtime-js';
  document.head.appendChild(script);
})();
