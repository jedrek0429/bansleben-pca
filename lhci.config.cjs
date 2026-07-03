module.exports = {
  ci: {
    collect: {
      startServerCommand: 'python -m http.server 4174 --directory ../site-dist',
      startServerReadyPattern: 'Serving HTTP',
      startServerReadyTimeout: 10000,
      url: [
        'http://127.0.0.1:4174/en/',
        'http://127.0.0.1:4174/fr/',
        'http://127.0.0.1:4174/hr/',
        'http://127.0.0.1:4174/en/contact/',
        'http://127.0.0.1:4174/fr/formulaire/',
        'http://127.0.0.1:4174/hr/kontakt/'
      ],
      numberOfRuns: 3,
      settings: {
        preset: 'desktop',
        throttlingMethod: 'simulate'
      }
    },
    assert: {
      assertions: {
        'categories:performance': ['warn', { minScore: 0.7 }],
        'categories:accessibility': ['warn', { minScore: 0.85 }],
        'total-byte-weight': ['warn', { maxNumericValue: 900000 }],
        'unused-javascript': ['warn', { maxLength: 2 }],
        'unused-css-rules': ['warn', { maxLength: 2 }],
        'render-blocking-resources': ['warn', { maxLength: 2 }]
      }
    },
    upload: {
      target: 'temporary-public-storage'
    }
  }
};
