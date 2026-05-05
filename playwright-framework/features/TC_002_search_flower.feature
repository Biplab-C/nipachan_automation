# TC_002: Search flower
# URL: https://www.heb.com/
# Created: 2026-05-01
# Data: TC_002_search_flower.json

Feature: Search flower

  Scenario: Search flower
    Then I verify the "Shopping List" link is visible
    When I search for "flower"
    Then I verify the first item name contains "Flower"