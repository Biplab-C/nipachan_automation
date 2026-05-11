# TC_001: Shopping list
# URL: https://www.heb.com/
# Created: 2026-05-10
# Data: TC_001_shopping_list.json

Feature: Shopping list

  Scenario: Shopping list
    Given I am on the application home page
    And the page is analyzed
    Then I verify "Shopping List" link is visible
    When I search for "Cake"
    And the page is analyzed
    Then I verify "cake" is visible in the first item name
