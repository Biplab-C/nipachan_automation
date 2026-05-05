from pages.base_page import BasePage


class HebHomePage(BasePage):
    """Page object for HebHomePage."""

    # ── Locators ──────────────────────────────────────────────────
    HOME_LINK = "a[aria-label='H-E-B Home page']"
    SEARCH_INPUT = "#search-input"
    SUBMIT_SEARCH_BUTTON = "button[aria-label='Submit search']"
    IN_STORE_AT_BUTTON = "button:has-text('In-store at')"
    STORE_SELECTOR_BUTTON = "button[aria-label*='Shopping at']"
    CART_LINK = "a[aria-label='Go to Cart page.']"
    SHOP_MENU_BUTTON = "button[aria-label='Shop menu']"
    ALL_DEPARTMENTS_LINK = "a:has-text('All departments')"
    FRUIT_VEGETABLES_LINK = "a:has-text('Fruit & vegetables')"
    FRUIT_VEGETABLES_MENU_BUTTON = "button[aria-label='Fruit & vegetables menu']"
    MEAT_SEAFOOD_LINK = "a:has-text('Meat & seafood')"
    MEAT_SEAFOOD_MENU_BUTTON = "button[aria-label='Meat & seafood menu']"
    BAKERY_BREAD_LINK = "a:has-text('Bakery & bread')"
    BAKERY_BREAD_MENU_BUTTON = "button[aria-label='Bakery & bread menu']"
    DAIRY_EGGS_LINK = "a:has-text('Dairy & eggs')"
    DAIRY_EGGS_MENU_BUTTON = "button[aria-label='Dairy & eggs menu']"
    DELI_PREPARED_FOOD_LINK = "a:has-text('Deli & prepared food')"
    DELI_PREPARED_FOOD_MENU_BUTTON = "button[aria-label='Deli & prepared food menu']"
    PANTRY_LINK = "a:has-text('Pantry')"
    PANTRY_MENU_BUTTON = "button[aria-label='Pantry menu']"
    FROZEN_FOOD_LINK = "a:has-text('Frozen food')"
    FROZEN_FOOD_MENU_BUTTON = "button[aria-label='Frozen food menu']"
    BEVERAGES_LINK = "a:has-text('Beverages')"
    BEVERAGES_MENU_BUTTON = "button[aria-label='Beverages menu']"
    EVERYDAY_ESSENTIALS_LINK = "a:has-text('Everyday essentials')"
    EVERYDAY_ESSENTIALS_MENU_BUTTON = "button[aria-label='Everyday essentials menu']"
    HEALTH_BEAUTY_LINK = "a:has-text('Health & beauty')"
    HEALTH_BEAUTY_MENU_BUTTON = "button[aria-label='Health & beauty menu']"
    HOME_OUTDOOR_LINK = "a:has-text('Home & outdoor')"
    HOME_OUTDOOR_MENU_BUTTON = "button[aria-label='Home & outdoor menu']"
    BABY_KIDS_LINK = "a:has-text('Baby & kids')"
    BABY_KIDS_MENU_BUTTON = "button[aria-label='Baby & kids menu']"
    PETS_LINK = "a:has-text('Pets')"
    PETS_MENU_BUTTON = "button[aria-label='Pets menu']"
    SNAP_EBT_ELIGIBLE_LINK = "a:has-text('SNAP EBT eligible')"
    DONATIONS_LINK = "a:has-text('Donations')"
    RECIPES_MEALS_BUTTON = "button[aria-label='Recipes & meals menu']"
    RECIPES_LINK = "a:has-text('Recipes')"
    MEALS_MADE_EASY_LINK = "a:has-text('Meals made easy')"
    SHOP_BY_DIETARY_PREFERENCE_LINK = "a:has-text('Shop by dietary preference')"
    SHOP_BY_DIETARY_PREFERENCE_MENU_BUTTON = "button[aria-label='Shop by dietary preference menu']"
    RESTAURANTS_LINK = "a:has-text('Restaurants')"
    CATERING_LINK = "a:has-text('Catering')"
    SAVINGS_BUTTON = "button[aria-label='Savings menu']"
    ALL_SAVINGS_LINK = "a:has-text('All savings')"
    COUPONS_LINK = "a:has-text('Coupons')"
    WEEKLY_AD_LINK = "a:has-text('Weekly ad')"
    SALE_PRICE_CUT_LINK = "a:has-text('Sale & Price cut')"
    H_EB_CREDIT_CARD_LINK = "a:has-text('H-E-B credit card')"
    PHARMACY_BUTTON = "button[aria-label='Pharmacy menu']"
    H_EB_PHARMACY_LINK = "a:has-text('H-E-B Pharmacy')"
    PRESCRIPTION_SERVICES_BUTTON = "button:has-text('Prescription services')"
    HEALTH_SERVICES_BUTTON = "button:has-text('Health services')"
    WELLNESS_BUTTON = "button[aria-label='Wellness menu']"
    ABOUT_H_EB_WELLNESS_LINK = "a:has-text('About H-E-B Wellness')"
    PRIMARY_CARE_LINK = "a:has-text('Primary Care')"
    NUTRITION_SERVICES_LINK = "a:has-text('Nutrition Services')"
    FIND_A_CLINIC_LINK = "a:has-text('Find a clinic')"
    FIND_A_PROVIDER_LINK = "a:has-text('Find a provider')"
    H_EB_WELLNESS_FOR_EMPLOYERS_LINK = "a:has-text('H-E-B Wellness for employers')"
    SIGN_UP_LINK = "a:has-text('Sign up')"
    LOG_IN_LINK = "a:has-text('log in')"
    SHOPPING_LISTS_LINK = "a[aria-label='Shopping lists menu']"
    HELP_FAQS_LINK = "a[aria-label='Help & FAQs menu']"
    SKIP_BANNER_CAROUSEL_LINK = "a:has-text('Skip banner carousel')"
    BANNER_PROMO_LINK = "a:has-text('Get $4 off $20')"
    BANNER_PROMO_2_LINK = "a:has-text('$10 off $50+')"
    BANNER_PROMO_3_LINK = "a:has-text('Earn 5% cash back')"

    # ── Actions ───────────────────────────────────────────────────

    def open(self) -> "HebHomePage":
        self.navigate_to()
        return self

    def verify_shopping_lists_link(self) -> "HebHomePage":
        self.actions.wait_for_visible(self.SHOPPING_LISTS_LINK)
        return self

    def search_via_search_input(self) -> "HebHomePage":
        self.actions.send_text(self.SEARCH_INPUT, text)
        self.actions.press_key(self.SEARCH_INPUT, 'Enter')
        return self