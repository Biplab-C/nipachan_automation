# TC_003: Click recipe link
# URL: https://www.heb.com/
# Created: 2026-05-01
# Data: TC_003_click_recipe_link.json

Feature: Click recipe link

  Scenario: Click recipe link
    Given I verify the "Recipe and Meals" link is visible
    When I click on the "Recipe and Meals" link
    And I search for "Recipes"
    Then I verify the "Seasonal favorites" link is visible
    And I verify there are 5 items