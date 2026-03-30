"""Data extraction service."""

from typing import List, Dict, Any

from playwright.sync_api import Page


class DataExtractor:
    """Service for extracting data from pages."""

    def __init__(self, debug: bool = True):
        """Initialize data extractor.

        Args:
            debug: Whether to print debug messages
        """
        self.debug = debug

    def extract_data(self, page: Page) -> List[Dict[str, Any]]:
        """Extract data from the page.

        Override this method for specific extraction logic.

        Args:
            page: Playwright page

        Returns:
            List of extracted data dictionaries
        """
        data = []

        try:
            # Example extraction patterns (customize as needed):

            # Extract from elements
            # elements = page.query_selector_all('selector-css-here')
            # for element in elements:
            #     data.append({
            #         'text': element.inner_text().strip(),
            #     })

            # Extract from table
            # table = page.query_selector('table')
            # if table:
            #     rows = table.query_selector_all('tr')
            #     for row in rows:
            #         cells = row.query_selector_all('td, th')
            #         if cells:
            #             data.append({
            #                 'col1': cells[0].inner_text().strip() if len(cells) > 0 else '',
            #                 'col2': cells[1].inner_text().strip() if len(cells) > 1 else '',
            #             })

            # Extract links
            # links = page.query_selector_all('a')
            # for link in links:
            #     data.append({
            #         'href': link.get_attribute('href') or '',
            #         'text': link.inner_text().strip(),
            #     })

            print(f'[INFO] Data extracted: {len(data)} elements')
            return data

        except Exception as error:
            print(f'[ERROR] Error extracting data: {error}')
            return []

    def extract_table_data(
        self,
        page: Page,
        table_selector: str,
        columns: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract data from a table.

        Args:
            page: Playwright page
            table_selector: CSS selector for table
            columns: Column names for the data

        Returns:
            List of dictionaries with extracted data
        """
        data = []

        try:
            table = page.query_selector(table_selector)
            if not table:
                print(f'[WARN] Table not found: {table_selector}')
                return data

            rows = table.query_selector_all('tr')
            for row in rows:
                cells = row.query_selector_all('td')
                if cells:
                    row_data = {}
                    for idx, col_name in enumerate(columns):
                        if idx < len(cells):
                            row_data[col_name] = cells[idx].inner_text().strip()
                        else:
                            row_data[col_name] = ''
                    data.append(row_data)

            print(f'[INFO] Extracted {len(data)} rows from table')
            return data

        except Exception as error:
            print(f'[ERROR] Error extracting table data: {error}')
            return []

    def extract_list_data(
        self,
        page: Page,
        list_selector: str
    ) -> List[str]:
        """Extract text from list items.

        Args:
            page: Playwright page
            list_selector: CSS selector for list items

        Returns:
            List of text strings
        """
        data = []

        try:
            items = page.query_selector_all(list_selector)
            for item in items:
                text = item.inner_text().strip()
                if text:
                    data.append(text)

            print(f'[INFO] Extracted {len(data)} list items')
            return data

        except Exception as error:
            print(f'[ERROR] Error extracting list data: {error}')
            return []
