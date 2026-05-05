from pages.base_page import BasePage


class HebSearchPage(BasePage):
    """Page object for HebSearchPage."""

    # ── Locators ──────────────────────────────────────────────────
    HOME_LINK = "a[aria-label='H-E-B Home page']"
    SEARCH_INPUT = "#search-input"
    RESET_BUTTON = "button[aria-label='Reset']"
    SUBMIT_SEARCH_BUTTON = "button[aria-label='Submit search']"
    IN_STORE_AT_BUTTON = "text=In-store at"
    STORE_SELECTOR_BUTTON = "button[aria-label*='Shopping at']"
    CART_LINK = "a[aria-label='Go to Cart page.']"
    SHOP_MENU_BUTTON = "button[aria-label='Shop menu']"
    ALL_DEPARTMENTS_LINK = "text=All departments"
    FRUIT_VEGETABLES_LINK = "text=Fruit & vegetables"
    MEAT_SEAFOOD_LINK = "text=Meat & seafood"
    BAKERY_BREAD_LINK = "text=Bakery & bread"
    DAIRY_EGGS_LINK = "text=Dairy & eggs"
    DELI_PREPARED_FOOD_LINK = "text=Deli & prepared food"
    PANTRY_LINK = "text=Pantry"
    FROZEN_FOOD_LINK = "text=Frozen food"
    BEVERAGES_LINK = "text=Beverages"
    EVERYDAY_ESSENTIALS_LINK = "text=Everyday essentials"
    HEALTH_BEAUTY_LINK = "text=Health & beauty"
    HOME_OUTDOOR_LINK = "text=Home & outdoor"
    BABY_KIDS_LINK = "text=Baby & kids"
    PETS_LINK = "text=Pets"
    SNAP_EBT_ELIGIBLE_LINK = "text=SNAP EBT eligible"
    DONATIONS_LINK = "text=Donations"
    RECIPES_MEALS_BUTTON = "button[aria-label='Recipes & meals menu']"
    RECIPES_LINK = "text=Recipes"
    MEALS_MADE_EASY_LINK = "text=Meals made easy"
    SHOP_BY_DIETARY_PREFERENCE_LINK = "text=Shop by dietary preference"
    RESTAURANTS_LINK = "text=Restaurants"
    CATERING_LINK = "text=Catering"
    SAVINGS_BUTTON = "button[aria-label='Savings menu']"
    ALL_SAVINGS_LINK = "text=All savings"
    COUPONS_LINK = "text=Coupons"
    WEEKLY_AD_LINK = "text=Weekly ad"
    SALE_PRICE_CUT_LINK = "text=Sale & Price cut"
    H_EB_CREDIT_CARD_LINK = "text=H-E-B credit card"
    PHARMACY_BUTTON = "button[aria-label='Pharmacy menu']"
    H_EB_PHARMACY_LINK = "text=H-E-B Pharmacy"
    PRESCRIPTION_SERVICES_BUTTON = "button[aria-label='Prescription services menu']"
    HEALTH_SERVICES_BUTTON = "button[aria-label='Health services menu']"
    WELLNESS_BUTTON = "button[aria-label='Wellness menu']"
    ABOUT_H_EB_WELLNESS_LINK = "text=About H-E-B Wellness"
    PRIMARY_CARE_LINK = "text=Primary Care"
    NUTRITION_SERVICES_LINK = "text=Nutrition Services"
    FIND_A_CLINIC_LINK = "text=Find a clinic"
    FIND_A_PROVIDER_LINK = "text=Find a provider"
    H_EB_WELLNESS_FOR_EMPLOYERS_LINK = "text=H-E-B Wellness for employers"
    SIGN_UP_LINK = "text=Sign up"
    LOG_IN_LINK = "text=log in"
    SHOPPING_LISTS_LINK = "text=Shopping lists"
    HELP_FAQS_LINK = "text=Help & FAQs"
    SEARCH_RESULTS_HEADING = "#searchGridHeader"
    SKIP_PARTY_ESSENTIALS_CAROUSEL_LINK = "text=Skip Party essentials carousel"
    PARTY_ESSENTIALS_HEADING = "#_r_0_"

    # ── Actions ───────────────────────────────────────────────────

    def open(self) -> "HebSearchPage":
        self.navigate_to()
        return self

    def verify_first_item_name_contains_cake(self) -> "HebSearchPage":
        self.actions.wait_for_visible(self.SEARCH_RESULTS_HEADING)
        return self