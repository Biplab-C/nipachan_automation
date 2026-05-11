# TC_002: Mobile Search
# URL: https://www.flipkart.com/
# Created: 2026-05-11
# Data: TC_002_mobile_search.json

Feature: Mobile Search

  Scenario: Mobile Search
    Given I am on the application home page
    When I search for "Mobile"
    Then I verify "Mobile" is visible
