class HomePageLocators:
    # Both hooks were read out of the HTML that https://www.myntra.com/ served on
    # 2026-10-24, not guessed: the header search field carries a stable,
    # user-visible placeholder, and the search bar wrapper a `desktop-searchBar`
    # class. Neither has been confirmed in a live browser session - Myntra fronts
    # its traffic with Akamai, so exploring it is manual-and-authorized-only (see
    # the `production` marker in pytest.ini).
    SEARCH_INPUT = "input[placeholder='Search for products, brands and more']"
    SEARCH_BAR = ".desktop-searchBar"
