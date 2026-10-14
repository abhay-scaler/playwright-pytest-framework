class HomePageLocators:
    # DocSearch's DocSearch-* classnames are Algolia's documented, stable public
    # theming API (used for CSS customization across thousands of sites), so they
    # are a safer bet than any of DocSearch's internal element ids.
    SEARCH_BUTTON = ".DocSearch-Button"
    SEARCH_INPUT = ".DocSearch-Modal input[type='search']"
    RESULTS = ".DocSearch-Hits"
