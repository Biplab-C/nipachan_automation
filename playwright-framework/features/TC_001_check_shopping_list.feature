# TC_001: Check Shopping List
# URL: https://www.heb.com/
# Created: 2026-05-01
# Data: TC_001_check_shopping_list.json

Feature: Check Shopping List

  Scenario: Check Shopping List
    Then I verify the "Shopping List" link is visible
    When I search for "Cake"
    Then I verify the first item name contains "cake"