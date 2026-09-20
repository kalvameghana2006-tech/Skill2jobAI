# Selenium

> Automating browser tests with WebDriver locators, waits and page objects.
> Category: Testing & QA. Typical effort: about 8 study days.

## WebDriver basics

- **WebDriver** — API that controls a real browser.
- **Locator** — strategy such as id, CSS or XPath to find an element.
- **Driver setup** — launching a browser session from code.

Practice: Open a page and click a button through code.

## Waits and interactions

- **Explicit wait** — waits for a specific condition with a timeout.
- **Implicit wait** — global default wait for finding elements.
- **StaleElementReference** — error when the page changed after you found an element.

Practice: Fix a flaky test by replacing sleeps with explicit waits.

## Framework design

- **Page Object Model** — one class per page holding its locators and actions.
- **TestNG/JUnit** — runner providing assertions and reports.
- **Data-driven test** — same test run with many inputs.

Practice: Refactor scripts into page objects and add a data-driven test.

## Mini project

Automate a login + search + checkout flow on a demo shop with Selenium WebDriver using Page Object Model, explicit waits and a test report.
