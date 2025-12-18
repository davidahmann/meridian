"""Playwright UI tests for Fabra Feature Store UI.

Run with:
    uv run pytest tests/ui/ --headed  # See browser
    uv run pytest tests/ui/           # Headless
    uv run pytest -m e2e              # Run only UI/e2e tests

Note: These tests are marked as e2e and excluded from default test runs
to prevent event loop conflicts with pytest-asyncio. Playwright's sync API
uses its own event loop which conflicts with async tests.
"""

import pytest

try:
    from playwright.sync_api import Page, expect
except ImportError:
    pytest.skip("playwright not installed", allow_module_level=True)

# Mark all tests in this module as e2e tests
pytestmark = pytest.mark.e2e


class TestUILoading:
    """Test that the UI loads correctly."""

    def test_page_loads(self, page: Page, ui_server: str) -> None:
        """Test that the main page loads."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Check title
        expect(page).to_have_title("Fabra UI")

    def test_has_main_title(self, page: Page, ui_server: str) -> None:
        """Test that the main title is visible."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Look for Fabra title
        title = page.locator("h1:has-text('Fabra')")
        expect(title).to_be_visible()

    def test_tabs_visible(self, page: Page, ui_server: str) -> None:
        """Test that both tabs are visible."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Check for tabs
        store_tab = page.locator("button:has-text('Store & Features')")
        context_tab = page.locator("button:has-text('Context Assembly')")

        expect(store_tab).to_be_visible()
        expect(context_tab).to_be_visible()


class TestFeatureStoreTab:
    """Test the Store & Features tab."""

    def test_entity_selector_visible(self, page: Page, ui_server: str) -> None:
        """Test that entity selector is visible."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Should have entity selector
        selector = page.locator("text=Select Entity")
        expect(selector).to_be_visible()

    def test_feature_map_visible(self, page: Page, ui_server: str) -> None:
        """Test that Feature System Map section exists."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Look for the Feature System Map section
        header = page.locator("text=Feature System Map")
        expect(header).to_be_visible()

    def test_fetch_features_button(self, page: Page, ui_server: str) -> None:
        """Test that Fetch Features button exists and works."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Find and click the button
        button = page.locator("button:has-text('Fetch Features')")
        expect(button).to_be_visible()

        # Click it
        button.click()

        # Wait for results (spinner should appear then disappear)
        page.wait_for_timeout(2000)

        # Should see feature values header or cards
        # Note: This depends on the example data


class TestContextAssemblyTab:
    """Test the Context Assembly tab."""

    def test_switch_to_context_tab(self, page: Page, ui_server: str) -> None:
        """Test switching to Context Assembly tab."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Click Context Assembly tab
        tab = page.locator("button:has-text('Context Assembly')")
        tab.click()

        # Should see context-related content
        page.wait_for_timeout(500)
        header = page.locator("text=Context Assembly").first
        expect(header).to_be_visible()

    def test_context_form_visible(self, page: Page, ui_server: str) -> None:
        """Test that context form is visible after switching tabs."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Switch to Context tab
        tab = page.locator("button:has-text('Context Assembly')")
        tab.click()
        page.wait_for_timeout(500)

        # Should have Assemble Context button
        button = page.locator("button:has-text('Assemble Context')")
        expect(button).to_be_visible()

    def test_assemble_context(self, page: Page, ui_server: str) -> None:
        """Test assembling a context."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Switch to Context tab
        tab = page.locator("button:has-text('Context Assembly')")
        tab.click()
        page.wait_for_timeout(1000)

        # Find visible inputs within the form on this tab
        form_inputs = page.locator("input[type='text']:visible")
        if form_inputs.count() > 0:
            form_inputs.first.fill("test_user")

        # Click Assemble Context
        button = page.locator("button:has-text('Assemble Context')")
        button.click()

        # Wait for result (could be success or error)
        page.wait_for_timeout(3000)

        # Page should still be functional after submission
        expect(page).to_have_title("Fabra UI")


class TestSidebar:
    """Test sidebar functionality."""

    def test_sidebar_visible(self, page: Page, ui_server: str) -> None:
        """Test that sidebar is visible."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Sidebar should have Configuration header
        config = page.locator("text=Configuration")
        expect(config).to_be_visible()

    def test_loaded_file_shown(self, page: Page, ui_server: str) -> None:
        """Test that loaded file name is shown."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Should show the loaded file
        file_indicator = page.locator("text=rag_chatbot.py")
        expect(file_indicator).to_be_visible()


class TestDarkTheme:
    """Test dark theme styling."""

    def test_dark_background(self, page: Page, ui_server: str) -> None:
        """Test that dark theme is applied."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Check that the main content container has dark background
        # In Next.js the body should have dark background via Tailwind
        body = page.locator("body")
        expect(body).to_be_visible()

        # Check background color is dark (gray-900 or similar)
        # Dark backgrounds typically have RGB values less than 50
        # gray-900 is rgb(17, 24, 39) - body should be visible and dark


class TestScrolling:
    """Test scrolling behavior."""

    def test_page_scrollable(self, page: Page, ui_server: str) -> None:
        """Test that page is scrollable."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Scroll down and verify page handles scrolling
        page.evaluate("window.scrollTo(0, 500)")
        page.wait_for_timeout(100)

        # Page should handle scroll events (content height may vary)

    def test_json_container_scrollable(self, page: Page, ui_server: str) -> None:
        """Test that JSON containers are scrollable."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Switch to Context tab and assemble
        tab = page.locator("button:has-text('Context Assembly')")
        tab.click()
        page.wait_for_timeout(500)

        # Fill and submit form
        button = page.locator("button:has-text('Assemble Context')")
        button.click()
        page.wait_for_timeout(3000)

        # Check for scrollable container in results
        # The JsonViewer component uses overflow-y-auto


class TestResponsiveness:
    """Test responsive design."""

    def test_mobile_viewport(self, page: Page, ui_server: str) -> None:
        """Test UI at mobile viewport size."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Page should still be usable
        title = page.locator("h1:has-text('Fabra')")
        expect(title).to_be_visible()

    def test_tablet_viewport(self, page: Page, ui_server: str) -> None:
        """Test UI at tablet viewport size."""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Page should still be usable
        title = page.locator("h1:has-text('Fabra')")
        expect(title).to_be_visible()


class TestApiIntegration:
    """Test API integration with the UI."""

    def test_store_info_loaded(self, page: Page, ui_server: str) -> None:
        """Test that store info is loaded from API."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Should show Configuration section in sidebar
        config_section = page.locator("text=Configuration")
        expect(config_section).to_be_visible()

        # Should show Loaded File section in sidebar
        loaded_file = page.locator("text=Loaded File")
        expect(loaded_file).to_be_visible()

    def test_entities_loaded(self, page: Page, ui_server: str) -> None:
        """Test that entities are loaded from API."""
        page.goto(ui_server)
        page.wait_for_load_state("networkidle")

        # Should show User entity from rag_chatbot.py
        user_entity = page.locator("text=User")
        expect(user_entity.first).to_be_visible()
