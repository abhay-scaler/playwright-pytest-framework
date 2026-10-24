class HomePageLocators:
    # Docusaurus serves `<html ... data-has-hydrated=false>` and flips the attribute
    # to "true" once the client bundle has hydrated the page (confirmed against the
    # served HTML and in the browser: false at domcontentloaded, true ~120ms later,
    # at the same moment DocSearch fills in the button's keyboard-shortcut hint).
    # Until then the search button is already rendered, visible and enabled, but
    # carries no click handler - so this is the app's own readiness signal, not a
    # proxy for elapsed time.
    HYDRATED = 'html[data-has-hydrated="true"]'
    # DocSearch's DocSearch-* classnames are Algolia's documented, stable public
    # theming API (used for CSS customization across thousands of sites), so they
    # are a safer bet than any of DocSearch's internal element ids.
    SEARCH_BUTTON = ".DocSearch-Button"
    SEARCH_INPUT = ".DocSearch-Modal input[type='search']"
    RESULTS = ".DocSearch-Hits"
