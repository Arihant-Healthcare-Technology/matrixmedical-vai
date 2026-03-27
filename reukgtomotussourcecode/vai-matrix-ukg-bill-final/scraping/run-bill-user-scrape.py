#!/usr/bin/env python3
"""
Basic scraper using Playwright for Python
More modern and powerful than Puppeteer, with better multi-browser support

Usage:
    python scraper-playwright.py <URL>

Example:
    python scraper-playwright.py https://app.bill.com/users

Requirements:
    pip install playwright
    playwright install chromium  # or playwright install for all browsers
"""

import sys
import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] Missing dependencies. Install with:")
    print("  pip install playwright python-dotenv")
    print("  playwright install chromium")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configuration
CONFIG = {
    'headless': False,  # Change to True for headless mode
    'timeout': 60000,  # 60 seconds (increased for slow pages)
    'wait_until': 'domcontentloaded',  # Less strict than 'networkidle'
    'viewport': {
        'width': 1920,
        'height': 1080
    }
}

# Credentials from environment variables
LOGIN_EMAIL = os.getenv('BILL_LOGIN_EMAIL') or os.getenv('BILL_EMAIL') or ''
LOGIN_PASSWORD = os.getenv('BILL_LOGIN_PASSWORD') or os.getenv('BILL_PASSWORD') or ''

# Company name to select
COMPANY_NAME = os.getenv('BILL_COMPANY_NAME', 'Vai Consulting')

# CSV file path to upload (from environment variable or command line argument)
CSV_FILE_PATH = os.getenv('BILL_CSV_FILE_PATH', '')

# Output directory
OUTPUT_DIR = Path(__file__).parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


def perform_login(page: Page) -> bool:
    """
    Performs login on the page
    """
    print('[INFO] Checking for login form...')
    
    try:
        # Wait for login fields to be available (increased timeout)
        print('[INFO] Waiting for login fields...')
        page.wait_for_selector('input#email, input[name="email"]', timeout=3000)
        print('[INFO] Login form detected')
        
        # Verify we have credentials
        if not LOGIN_EMAIL or not LOGIN_PASSWORD:
            raise ValueError(
                'Credentials not found. Configure BILL_LOGIN_EMAIL and BILL_LOGIN_PASSWORD in the .env file'
            )
        
        print(f'[DEBUG] Email to use: {LOGIN_EMAIL[:3]}*** (hidden for security)')
        
        # Fill email field
        print('[INFO] Filling email field...')
        email_input = page.wait_for_selector('input#email, input[name="email"]', state='visible', timeout=10000)
        
        # Click on the field first to ensure it's focused
        email_input.click()
        page.wait_for_timeout(200)
        
        # Select all text if any (Ctrl+A) and then type
        email_input.press('Control+a')
        page.wait_for_timeout(100)
        
        # Type email with delay to simulate human typing
        email_input.type(LOGIN_EMAIL, delay=50)
        page.wait_for_timeout(300)
        
        print('[INFO] Email entered successfully')
        
        # Fill password field
        print('[INFO] Filling password field...')
        password_input = page.wait_for_selector('input#password, input[name="password"]', state='visible', timeout=10000)
        
        # Click on the field first
        password_input.click()
        page.wait_for_timeout(200)
        
        # Select all text if any (Ctrl+A)
        password_input.press('Control+a')
        page.wait_for_timeout(100)
        
        # Type password with delay
        password_input.type(LOGIN_PASSWORD, delay=50)
        page.wait_for_timeout(300)
        
        print('[INFO] Password entered successfully')
        
        # Wait a moment before clicking
        page.wait_for_timeout(500)
        
        # Find and click login button
        print('[INFO] Looking for login button...')
        
        # Try different selectors for login button
        login_button_selectors = [
            'button[type="submit"]',
            'button[name="login"]',
            'input[type="submit"]',
            '[data-testid*="login"]',
            '[data-testid*="submit"]',
            'button:has-text("Log in")',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
        ]
        
        login_button = None
        for selector in login_button_selectors:
            try:
                login_button = page.query_selector(selector)
                if login_button:
                    print(f'[INFO] Login button found with selector: {selector}')
                    break
            except Exception:
                # Continue with next selector
                continue
        
        # If not found by selector, search by text
        if not login_button:
            buttons = page.query_selector_all('button')
            for button in buttons:
                text = button.inner_text().strip().lower()
                if 'log in' in text or 'login' in text or 'sign in' in text:
                    login_button = button
                    print('[INFO] Login button found by text')
                    break
        
        if not login_button:
            raise ValueError('Could not find login button')
        
        # Click login button
        print('[INFO] Clicking login button...')
        login_button.click()
        
        # Wait for navigation to complete (after login)
        print('[INFO] Waiting for login to complete...')
        try:
            page.wait_for_load_state('networkidle', timeout=3000)
        except Exception:
            # If no navigation, wait a bit more
            print('[INFO] Waiting for content after login...')
        
        # Wait a bit more to ensure page loaded completely
        page.wait_for_timeout(2000)
        
        print('[INFO] Login completed successfully')
        return True
        
    except Exception as error:
        # If no login form, continue normally
        error_msg = str(error)
        if 'timeout' in error_msg.lower() or 'waiting for selector' in error_msg.lower():
            print('[INFO] No login form detected, continuing...')
            return False
        raise error


def select_company(page: Page, company_name: str) -> bool:
    """
    Selects a company from the list after login
    """
    print(f'[INFO] Looking for company: {company_name}...')
    
    try:
        # Wait for companies table to load
        print('[INFO] Waiting for companies list to load...')
        page.wait_for_timeout(2000)
        
        # Find element containing company name
        # Try different strategies to find the company
        
        # Strategy 1: Search by exact text using XPath
        company_xpath = f'//div[contains(text(), "{company_name}")]'
        
        try:
            company_element = page.wait_for_selector(f'xpath={company_xpath}', timeout=10000, state='visible')
            print(f'[INFO] Company "{company_name}" found')
            
            # Scroll to element if needed
            company_element.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            
            # Click on the element
            print(f'[INFO] Clicking on company "{company_name}"...')
            company_element.click()
            
            # Wait for navigation to complete
            page.wait_for_timeout(2000)
            
            print(f'[INFO] Company "{company_name}" selected successfully')
            page.wait_for_timeout(2000)
            
            return True
            
        except Exception as e1:
            print(f'[WARN] Not found with XPath, trying another strategy...')
            
            # Strategy 2: Search in all table rows
            try:
                # Find all cells containing company name
                cells = page.query_selector_all('div[data-testid*="Cell-name"], div[class*="Cell-name"]')
                
                for cell in cells:
                    text = cell.inner_text().strip()
                    if company_name.lower() in text.lower():
                        print(f'[INFO] Company "{company_name}" found in cell')
                        
                        # Scroll to element
                        cell.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        
                        # Click
                        cell.click()
                        page.wait_for_timeout(2000)
                        
                        print(f'[INFO] Company "{company_name}" selected successfully')
                        return True
                
                raise ValueError(f'Company "{company_name}" not found in list')
                
            except Exception as e2:
                print(f'[ERROR] Error searching for company: {e2}')
                raise e2
        
    except Exception as error:
        error_msg = str(error)
        if 'timeout' in error_msg.lower() or 'waiting for selector' in error_msg.lower():
            print(f'[WARN] Could not find company "{company_name}", continuing...')
            return False
        print(f'[ERROR] Error selecting company: {error}')
        raise error


def close_popup(page: Page) -> bool:
    """
    Closes any popup that might appear on the page
    """
    print('[INFO] Checking for popups to close...')
    
    try:
        # Wait longer for popup to appear
        page.wait_for_timeout(2000)
        
        # Try multiple times to close popup
        for attempt in range(3):
            print(f'[INFO] Attempt {attempt + 1} to close popup...')
            
            # Strategy 1: Find SVG with data-testid="Icon-svg-Close" and click its parent button
            try:
                close_svg = page.query_selector('svg[data-testid="Icon-svg-Close"]')
                if close_svg:
                    # Find parent button using evaluate
                    parent_button = close_svg.evaluate('el => el.closest("button")')
                    if parent_button:
                        # Query the button again to get the element handle
                        button_selector = f'button:has(svg[data-testid="Icon-svg-Close"])'
                        button = page.query_selector(button_selector)
                        if button and button.is_visible():
                            print('[INFO] Found close button via SVG data-testid')
                            button.click()
                            page.wait_for_timeout(1000)
                            print('[INFO] Popup closed successfully')
                            return True
                        # If that doesn't work, try clicking the SVG's parent directly
                        try:
                            close_svg.evaluate('el => el.closest("button")?.click()')
                            page.wait_for_timeout(1000)
                            print('[INFO] Clicked parent button via evaluate')
                            return True
                        except Exception:
                            pass
            except Exception as e:
                print(f'[DEBUG] SVG method failed: {e}')
            
            # Strategy 2: Find button with Modal-close-button class
            try:
                close_buttons = page.query_selector_all('button[class*="Modal-close"], button[class*="close-button"]')
                for btn in close_buttons:
                    if btn.is_visible():
                        print('[INFO] Found close button via class selector')
                        btn.click()
                        page.wait_for_timeout(1000)
                        print('[INFO] Popup closed successfully')
                        return True
            except Exception as e:
                print(f'[DEBUG] Class selector method failed: {e}')
            
            # Strategy 3: Find SVG with Close class and click parent
            try:
                close_svgs = page.query_selector_all('svg[class*="Close"], svg[class*="close"]')
                for svg in close_svgs:
                    if svg.is_visible():
                        # Try to click parent button using evaluate
                        try:
                            svg.evaluate('el => el.closest("button")?.click()')
                            page.wait_for_timeout(1000)
                            print('[INFO] Found and clicked close button via SVG class')
                            return True
                        except Exception:
                            # If no parent button, try clicking SVG directly
                            try:
                                svg.click()
                                page.wait_for_timeout(1000)
                                print('[INFO] Clicked SVG directly')
                                return True
                            except Exception:
                                pass
            except Exception as e:
                print(f'[DEBUG] SVG class method failed: {e}')
            
            # Strategy 4: Common popup close button selectors
            popup_selectors = [
                'button[aria-label*="close" i]',
                'button[aria-label*="Close" i]',
                'button[aria-label*="dismiss" i]',
                '[data-testid*="close"]',
                '[data-testid*="dismiss"]',
                'button.close',
                '.close-button',
                '[class*="close-button"]',
                'button:has-text("Close")',
                'button:has-text("X")',
            ]
            
            for selector in popup_selectors:
                try:
                    close_button = page.query_selector(selector)
                    if close_button and close_button.is_visible():
                        print(f'[INFO] Popup close button found with selector: {selector}')
                        close_button.click()
                        page.wait_for_timeout(1000)
                        print('[INFO] Popup closed successfully')
                        return True
                except Exception:
                    continue
            
            # Strategy 5: Try ESC key
            try:
                page.keyboard.press('Escape')
                page.wait_for_timeout(1000)
                print('[INFO] Tried ESC key to close popup')
            except Exception:
                pass
            
            # Wait before next attempt
            if attempt < 2:
                page.wait_for_timeout(1000)
        
        print('[INFO] No popup found or already closed after all attempts')
        return False
        
    except Exception as error:
        print(f'[WARN] Error checking for popup: {error}')
        return False


def navigate_to_people(page: Page) -> bool:
    """
    Navigates to /people page from current URL
    """
    try:
        # Get current URL
        current_url = page.url
        print(f'[INFO] Current URL: {current_url}')
        
        # Parse URL to get base and path
        parsed_url = urlparse(current_url)
        base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
        current_path = parsed_url.path
        
        # Extract company ID from path if we're on a company page
        # Example: /companies/Q29tcGFueToxMTMwMA== or /companies/Q29tcGFueToxMTMwMA==/something
        if '/companies/' in current_path:
            # Split path to get company ID part
            parts = current_path.split('/companies/')
            if len(parts) > 1:
                # Get everything after /companies/
                company_part = parts[1].split('/')[0]  # Get just the company ID
                # Build clean URL: /companies/ID/people
                people_path = f'/companies/{company_part}/people'
                people_url = f'{base_url}{people_path}'
            else:
                # Fallback: try to construct from current path
                if current_path.endswith('/'):
                    people_url = f'{base_url}{current_path}people'
                else:
                    people_url = f'{base_url}{current_path}/people'
        else:
            # If not on company page, try to find company ID in URL or use direct path
            # This is a fallback - ideally we should be on a company page
            people_url = f'{base_url}/people'
        
        print(f'[INFO] Navigating to people page: {people_url}')
        
        # Navigate to people page
        page.goto(people_url, wait_until=CONFIG['wait_until'], timeout=CONFIG['timeout'])
        
        # Close popup again after navigation
        close_popup(page)
        
        # Wait for page to load
        page.wait_for_timeout(3000)
        
        print('[INFO] Successfully navigated to people page')
        return True
        
    except Exception as error:
        print(f'[ERROR] Error navigating to people page: {error}')
        return False


def click_import_people_button(page: Page) -> bool:
    """
    Clicks on the "Import People" button on the people page
    """
    print('[INFO] Looking for "Import People" button...')
    
    try:
        # Wait for page to be fully loaded
        page.wait_for_timeout(2000)
        
        # Strategy 1: Find button by data-testid
        try:
            import_button = page.wait_for_selector(
                'button[data-testid*="import-people"], button[data-testid*="Import"]',
                timeout=10000,
                state='visible'
            )
            print('[INFO] Import People button found by data-testid')
            import_button.click()
            page.wait_for_timeout(2000)
            print('[INFO] Clicked Import People button successfully')
            return True
        except Exception as e1:
            print(f'[DEBUG] Method 1 failed: {e1}')
        
        # Strategy 2: Find button by text content
        try:
            buttons = page.query_selector_all('button')
            for button in buttons:
                text = button.inner_text().strip()
                if 'import people' in text.lower() or 'import' in text.lower():
                    if button.is_visible():
                        print(f'[INFO] Import People button found by text: "{text}"')
                        button.click()
                        page.wait_for_timeout(2000)
                        print('[INFO] Clicked Import People button successfully')
                        return True
        except Exception as e2:
            print(f'[DEBUG] Method 2 failed: {e2}')
        
        # Strategy 3: Find span with "Import People" text and click parent button
        try:
            spans = page.query_selector_all('span')
            for span in spans:
                text = span.inner_text().strip()
                if 'import people' in text.lower():
                    # Find parent button
                    try:
                        parent_button = span.evaluate('el => el.closest("button")')
                        if parent_button:
                            button = page.query_selector(f'button:has(span:has-text("{text}"))')
                            if button and button.is_visible():
                                print('[INFO] Import People button found via span text')
                                button.click()
                                page.wait_for_timeout(2000)
                                print('[INFO] Clicked Import People button successfully')
                                return True
                    except Exception:
                        pass
        except Exception as e3:
            print(f'[DEBUG] Method 3 failed: {e3}')
        
        # Strategy 4: Find by aria-label or other attributes
        try:
            import_buttons = page.query_selector_all('button[aria-label*="import" i], button[aria-label*="Import" i]')
            for btn in import_buttons:
                if btn.is_visible():
                    print('[INFO] Import People button found by aria-label')
                    btn.click()
                    page.wait_for_timeout(2000)
                    print('[INFO] Clicked Import People button successfully')
                    return True
        except Exception as e4:
            print(f'[DEBUG] Method 4 failed: {e4}')
        
        raise ValueError('Could not find "Import People" button')
        
    except Exception as error:
        print(f'[ERROR] Error clicking Import People button: {error}')
        raise error


def upload_csv_file(page: Page, csv_file_path: str) -> bool:
    """
    Clicks on "Select File" button and uploads a CSV file
    """
    print(f'[INFO] Preparing to upload CSV file: {csv_file_path}')
    
    try:
        # Verify file exists
        csv_path = Path(csv_file_path)
        if not csv_path.exists():
            raise FileNotFoundError(f'CSV file not found: {csv_file_path}')
        
        if not csv_path.is_file():
            raise ValueError(f'Path is not a file: {csv_file_path}')
        
        print(f'[INFO] CSV file found: {csv_path.absolute()}')
        
        # Wait for the file input to be available
        print('[INFO] Waiting for file input to be available...')
        page.wait_for_timeout(2000)
        
        # Strategy 1: Find the file input directly by ID
        try:
            file_input = page.wait_for_selector('input#file-input[type="file"]', timeout=10000, state='visible')
            print('[INFO] File input found by ID')
            
            # Set the file path
            file_input.set_input_files(str(csv_path.absolute()))
            print('[INFO] CSV file uploaded successfully')
            page.wait_for_timeout(2000)
            return True
            
        except Exception as e1:
            print(f'[DEBUG] Method 1 failed: {e1}')
            
            # Strategy 2: Find by data-testid on the label
            try:
                label = page.wait_for_selector('label[data-testid="DragAndDropTarget-FileInput-label"]', timeout=10000, state='visible')
                print('[INFO] Label found, clicking to trigger file input...')
                label.click()
                page.wait_for_timeout(1000)
                
                # Now find the input
                file_input = page.query_selector('input[type="file"]')
                if file_input:
                    file_input.set_input_files(str(csv_path.absolute()))
                    print('[INFO] CSV file uploaded successfully via label click')
                    page.wait_for_timeout(2000)
                    return True
                    
            except Exception as e2:
                print(f'[DEBUG] Method 2 failed: {e2}')
                
                # Strategy 3: Find any file input
                try:
                    file_inputs = page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        file_input = file_inputs[0]
                        file_input.set_input_files(str(csv_path.absolute()))
                        print('[INFO] CSV file uploaded successfully via generic file input')
                        page.wait_for_timeout(2000)
                        return True
                except Exception as e3:
                    print(f'[DEBUG] Method 3 failed: {e3}')
                    raise e3
        
        return False
        
    except Exception as error:
        print(f'[ERROR] Error uploading CSV file: {error}')
        raise error


def click_import_people_submit_button(page: Page) -> bool:
    """
    Clicks on the "Import people" submit button after CSV file is loaded
    """
    print('[INFO] Looking for "Import people" submit button...')
    
    try:
        # Wait for the preview page to load after file upload
        page.wait_for_timeout(2000)
        
        # Strategy 1: Find button by data-testid (most reliable)
        try:
            import_button = page.wait_for_selector(
                'button[data-testid="ImportPeople-import-people-BasicButton"]',
                timeout=10000,
                state='visible'
            )
            print('[INFO] Import people button found by data-testid')
            import_button.click()
            page.wait_for_timeout(2000)
            print('[INFO] Clicked Import people button successfully')
            return True
        except Exception as e1:
            print(f'[DEBUG] Method 1 failed: {e1}')
        
        # Strategy 2: Find button by text content
        try:
            buttons = page.query_selector_all('button')
            for button in buttons:
                text = button.inner_text().strip()
                if text.lower() == 'import people' or text.lower() == 'import':
                    if button.is_visible():
                        print(f'[INFO] Import people button found by text: "{text}"')
                        button.click()
                        page.wait_for_timeout(2000)
                        print('[INFO] Clicked Import people button successfully')
                        return True
        except Exception as e2:
            print(f'[DEBUG] Method 2 failed: {e2}')
        
        # Strategy 3: Find span with "Import people" text and click parent button
        try:
            spans = page.query_selector_all('span')
            for span in spans:
                text = span.inner_text().strip()
                if text.lower() == 'import people':
                    # Find parent button
                    try:
                        button = page.query_selector(f'button:has(span:has-text("Import people"))')
                        if button and button.is_visible():
                            print('[INFO] Import people button found via span text')
                            button.click()
                            page.wait_for_timeout(2000)
                            print('[INFO] Clicked Import people button successfully')
                            return True
                    except Exception:
                        pass
        except Exception as e3:
            print(f'[DEBUG] Method 3 failed: {e3}')
        
        # Strategy 4: Find by data-testid pattern
        try:
            import_buttons = page.query_selector_all('button[data-testid*="import-people"], button[data-testid*="ImportPeople"]')
            for btn in import_buttons:
                if btn.is_visible():
                    print('[INFO] Import people button found by data-testid pattern')
                    btn.click()
                    page.wait_for_timeout(2000)
                    print('[INFO] Clicked Import people button successfully')
                    return True
        except Exception as e4:
            print(f'[DEBUG] Method 4 failed: {e4}')
        
        raise ValueError('Could not find "Import people" submit button')
        
    except Exception as error:
        print(f'[ERROR] Error clicking Import people submit button: {error}')
        raise error


def extract_data(page: Page) -> List[Dict[str, Any]]:
    """
    Extracts data from the page
    MODIFY THIS FUNCTION according to your needs
    """
    data = []
    
    try:
        # Example: extract elements from a table or list
        # Replace these selectors with your target page selectors
        
        # Example 1: Extract text from elements
        # elements = page.query_selector_all('selector-css-here')
        # for element in elements:
        #     data.append({
        #         'text': element.inner_text().strip(),
        #         # Add more fields as needed
        #     })
        
        # Example 2: Extract data from a table
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
        
        # Example 3: Extract specific attributes
        # links = page.query_selector_all('a')
        # for link in links:
        #     data.append({
        #         'href': link.get_attribute('href') or '',
        #         'text': link.inner_text().strip(),
        #     })
        
        print(f'[INFO] Data extracted: {len(data)} elements')
        return data
        
    except Exception as e:
        print(f'[ERROR] Error extracting data: {e}')
        return []


def save_results(data: List[Dict[str, Any]], filename: str = 'scraping-results.json') -> None:
    """
    Saves results to a JSON file
    """
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'[INFO] Results saved to: {filepath}')


def save_to_csv(data: List[Dict[str, Any]], filename: str = 'scraping-results.csv') -> None:
    """
    Saves results to a CSV file
    """
    if not data:
        print('[WARN] No data to save to CSV')
        return
    
    filepath = OUTPUT_DIR / filename
    
    # Get columns from first element
    fieldnames = list(data[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f'[INFO] CSV saved to: {filepath}')


def scrape(url: str) -> List[Dict[str, Any]]:
    """
    Main scraping function
    """
    print(f'[INFO] Starting scraping of: {url}')
    
    with sync_playwright() as p:
        try:
            # Launch browser
            print('[INFO] Launching browser...')
            browser = p.chromium.launch(
                headless=CONFIG['headless'],
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # Create new page
            page = browser.new_page()
            page.set_viewport_size(CONFIG['viewport'])
            
            # Navigate to URL
            print(f'[INFO] Navigating to {url}...')
            try:
                page.goto(url, wait_until=CONFIG['wait_until'], timeout=CONFIG['timeout'])
            except Exception as e:
                print(f'[WARN] Timeout on initial navigation, but continuing... Error: {e}')
                # Try to continue even if there's a timeout
                pass
            
            # Wait a bit for dynamic content to load
            print('[INFO] Waiting for content to load...')
            page.wait_for_timeout(3000)
            
            # Check if we're on a login page
            print('[INFO] Checking if login is needed...')
            
            # Try to login if necessary
            perform_login(page)
            
            # Select company if configured
            if COMPANY_NAME:
                select_company(page, COMPANY_NAME)
            
            # Close popup after selecting company
            print('[INFO] Closing popup after company selection...')
            close_popup(page)
            
            # Navigate to /people page
            print('[INFO] Navigating to people page...')
            navigate_to_people(page)
            
            # Wait for page to fully load
            print('[INFO] Waiting for people page to load...')
            page.wait_for_timeout(3000)
            
            # Click on "Import People" button
            print('[INFO] Clicking Import People button...')
            click_import_people_button(page)
            
            # Wait for import page to load
            page.wait_for_timeout(2000)
            print('[INFO] Import page loaded successfully')
            
            # Upload CSV file if path is provided
            if CSV_FILE_PATH:
                print('[INFO] Uploading CSV file...')
                upload_csv_file(page, CSV_FILE_PATH)
                
                # Wait for file preview to load
                page.wait_for_timeout(3000)
                print('[INFO] File preview loaded')
                
                # Click on "Import people" submit button
                print('[INFO] Clicking Import people submit button...')
                click_import_people_submit_button(page)
                
                # Wait for import to complete
                page.wait_for_timeout(5000)
                print('[INFO] Import process completed')
            else:
                print('[WARN] No CSV file path provided. Set BILL_CSV_FILE_PATH environment variable or pass as argument')
            
            # Extract data from page
            data = extract_data(page)
            
            # Save results
            if data:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                save_results(data, f'scraping-results-{timestamp}.json')
                save_to_csv(data, f'scraping-results-{timestamp}.csv')
            
            print(f'[INFO] Scraping completed. Data extracted: {len(data)} elements')
            
            # Close browser
            browser.close()
            
            return data
            
        except Exception as error:
            print(f'[ERROR] Error during scraping: {error}')
            raise error


def main():
    """
    Main function
    """
    global CSV_FILE_PATH
    
    if len(sys.argv) < 2:
        print('[ERROR] You must provide a URL')
        print('Usage: python scraper-playwright.py <URL> [CSV_FILE_PATH]')
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Allow CSV file path as second argument (overrides env variable)
    if len(sys.argv) >= 3:
        CSV_FILE_PATH = sys.argv[2]
        print(f'[INFO] CSV file path from argument: {CSV_FILE_PATH}')
    elif CSV_FILE_PATH:
        print(f'[INFO] CSV file path from environment: {CSV_FILE_PATH}')
    
    try:
        data = scrape(url)
        print('[INFO] Process completed successfully')
        sys.exit(0)
    except Exception as e:
        print(f'[ERROR] Process failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
