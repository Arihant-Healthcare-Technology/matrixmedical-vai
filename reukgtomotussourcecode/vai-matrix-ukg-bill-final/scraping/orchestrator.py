"""Main scraping orchestrator."""

from typing import List, Dict, Any, Optional

from playwright.sync_api import Page

from .config.settings import ScraperSettings
from .services.browser_service import BrowserService
from .services.data_extractor import DataExtractor
from .services.result_saver import ResultSaver
from .page_objects.login_page import LoginPage
from .page_objects.company_selector import CompanySelector
from .page_objects.popup_handler import PopupHandler
from .page_objects.people_page import PeoplePage
from .page_objects.import_modal import ImportModal


class BillScraperOrchestrator:
    """Orchestrates the BILL.com scraping workflow."""

    def __init__(
        self,
        settings: Optional[ScraperSettings] = None,
        debug: bool = True
    ):
        """Initialize orchestrator.

        Args:
            settings: Scraper settings
            debug: Whether to print debug messages
        """
        self.settings = settings or ScraperSettings.from_env()
        self.debug = debug
        self.browser_service = BrowserService(self.settings)
        self.data_extractor = DataExtractor(debug)
        self.result_saver = ResultSaver(self.settings.output_dir)

    def scrape(self, url: str) -> List[Dict[str, Any]]:
        """Main scraping function.

        Args:
            url: URL to scrape

        Returns:
            List of extracted data
        """
        print(f'[INFO] Starting scraping of: {url}')

        with self.browser_service.get_page() as page:
            try:
                # Navigate to URL
                self.browser_service.navigate(page, url)
                self.browser_service.wait_for_content(page)

                # Perform login if needed
                self._handle_login(page)

                # Select company
                self._handle_company_selection(page)

                # Navigate to people page and import
                self._handle_people_import(page)

                # Extract data
                data = self.data_extractor.extract_data(page)

                # Save results
                if data:
                    self.result_saver.save_with_timestamp(data)

                print(f'[INFO] Scraping completed. Data extracted: {len(data)} elements')
                return data

            except Exception as error:
                print(f'[ERROR] Error during scraping: {error}')
                raise

    def _handle_login(self, page: Page) -> None:
        """Handle login flow."""
        print('[INFO] Checking if login is needed...')

        login_page = LoginPage(page, self.debug)
        login_page.login(
            self.settings.login_email,
            self.settings.login_password
        )

    def _handle_company_selection(self, page: Page) -> None:
        """Handle company selection."""
        if self.settings.company_name:
            company_selector = CompanySelector(page, self.debug)
            company_selector.select_company(self.settings.company_name)

            # Close popup after company selection
            print('[INFO] Closing popup after company selection...')
            popup_handler = PopupHandler(page, self.debug)
            popup_handler.close_popup()

    def _handle_people_import(self, page: Page) -> None:
        """Handle navigation to people page and CSV import."""
        print('[INFO] Navigating to people page...')

        people_page = PeoplePage(page, self.debug)
        people_page.navigate_to_people()

        print('[INFO] Waiting for people page to load...')
        page.wait_for_timeout(3000)

        print('[INFO] Clicking Import People button...')
        people_page.click_import_people_button()

        page.wait_for_timeout(2000)
        print('[INFO] Import page loaded successfully')

        # Upload CSV if provided
        if self.settings.csv_file_path:
            self._handle_csv_upload(page)
        else:
            print('[WARN] No CSV file path provided. Set BILL_CSV_FILE_PATH '
                  'environment variable or pass as argument')

    def _handle_csv_upload(self, page: Page) -> None:
        """Handle CSV file upload."""
        print('[INFO] Uploading CSV file...')

        import_modal = ImportModal(page, self.debug)
        import_modal.upload_csv_file(self.settings.csv_file_path)

        page.wait_for_timeout(3000)
        print('[INFO] File preview loaded')

        print('[INFO] Clicking Import people submit button...')
        import_modal.click_import_submit()

        page.wait_for_timeout(5000)
        print('[INFO] Import process completed')
