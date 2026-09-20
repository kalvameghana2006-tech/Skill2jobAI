# Test Automation

> Building maintainable automated test suites and frameworks with BDD and page objects.
> Category: Testing & QA. Typical effort: about 8 study days.

## Automation strategy

- **Test pyramid** — many unit tests, fewer integration tests, fewest UI tests.
- **Regression suite** — tests that guard existing behaviour.
- **Flaky test** — test that passes and fails without code changes.

Practice: Decide which five manual tests to automate first.

## Framework design

- **Page Object Model** — one class per page holding locators and actions.
- **Fixture** — setup and teardown shared by tests.
- **Data-driven testing** — same test run with many inputs.

Practice: Refactor a script into page objects.

## Reporting and CI

- **Test report** — readable summary of passes and failures.
- **CI trigger** — runs tests on each commit.
- **Parallel execution** — runs tests simultaneously to save time.

Practice: Run your suite in GitHub Actions.

## Mini project

Build a Page Object based automation suite with Selenium or Playwright and an HTML report, running in CI.
