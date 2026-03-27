# Scraping for BILL with Playwright

Basic scraper using Playwright (Python) to load additional data into BILL that the REST API does not allow (such as Manager, Budget, etc.).

## Why Playwright?

- **More modern and powerful** than Puppeteer
- **Better multi-browser support** (Chromium, Firefox, WebKit)
- **More intuitive API** and easier to use
- **Better handling of waits** and events
- **Native support for Python**

## Installation

### 1. Install Python dependencies

```bash
cd scraping
pip install -r requirements-scraping.txt
```

### 2. Install Playwright browsers

```bash
# Chromium only (recommended, faster)
playwright install chromium

# Or install all browsers
playwright install
```

## Credential Configuration

Create a `.env` file in the `scraping` folder (or use the `.env` from the main project) with your credentials:

```bash
BILL_LOGIN_EMAIL=tu-email@ejemplo.com
BILL_LOGIN_PASSWORD=your-password
BILL_COMPANY_NAME=Vai Consulting
```

Or alternatively:

```bash
BILL_EMAIL=tu-email@ejemplo.com
BILL_PASSWORD=your-password
BILL_COMPANY_NAME=Vai Consulting
```

**Environment variables:**
- `BILL_LOGIN_EMAIL` or `BILL_EMAIL`: Email for login
- `BILL_LOGIN_PASSWORD` or `BILL_PASSWORD`: Password for login
- `BILL_COMPANY_NAME`: Name of the company to select (default: "Vai Consulting")
- `BILL_CSV_FILE_PATH`: Path to the CSV file to upload (optional, can be passed as argument)

## Usage

### Basic Usage (without CSV upload)

```bash
python scraper-playwright.py <URL>
```

### Usage with CSV File Upload

You can provide the CSV file path in two ways:

**Option 1: As command line argument (recommended)**
```bash
python scraper-playwright.py <URL> <CSV_FILE_PATH>
```

**Option 2: As environment variable**
```bash
# Set in .env file
BILL_CSV_FILE_PATH=/path/to/your/file.csv

# Then run
python scraper-playwright.py <URL>
```

### Examples

**Example 1: Without CSV upload**
```bash
python scraper-playwright.py https://app-dev-bdc-stg.divvy.co/companies
```

**Example 2: With CSV upload (command line argument)**
```bash
python scraper-playwright.py https://app-dev-bdc-stg.divvy.co/companies /path/to/people.csv
```

**Example 3: With CSV upload (environment variable)**
```bash
# In .env file
BILL_CSV_FILE_PATH=/path/to/people.csv

# Run command
python scraper-playwright.py https://app-dev-bdc-stg.divvy.co/companies
```

**Example 4: With relative path**
```bash
python scraper-playwright.py https://app-dev-bdc-stg.divvy.co/companies ../data/people-2026-01-09_10-57-00.csv
```

## Features

The scraper automatically:

1. ✅ Detects if there is a login form
2. ✅ Fills in the email and password fields from environment variables
3. ✅ Clicks the login button (multiple selectors supported)
4. ✅ Waits for navigation to complete after login
5. ✅ **Selects the company** specified in `BILL_COMPANY_NAME` (default: "Vai Consulting")
6. ✅ **Closes popups** that appear after company selection
7. ✅ **Navigates to `/people` page**
8. ✅ **Clicks on "Import People" button** to open the import page
9. ✅ **Uploads CSV file** if path is provided
10. ✅ **Clicks on "Import people" submit button** to complete the import
11. ✅ Extracts data from the page (if needed)
12. ✅ Saves results in JSON and CSV with timestamp


## File Structure

```
scraping/
├── scraper-playwright.py    # Main scraper with Playwright
├── requirements-scraping.txt # Python dependencies
├── README.md                # This file
├── .gitignore              # Files to ignore
└── output/                 # Output directory (generated automatically)
    ├── scraping-results-*.json
    └── scraping-results-*.csv
```

## Customization

### Modify data extraction

Edit the `extract_data()` function in `scraper-playwright.py`:

```python
def extract_data(page: Page) -> List[Dict[str, Any]]:
    data = []

    # Example: Extract elements from a table
    table = page.query_selector('table')
    if table:
        rows = table.query_selector_all('tr')
        for row in rows:
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
            cells = row.query_selector_all('tr')
    table = page.query_selector('table')
    if table:
        rows = table.query_selector_all('tr')
        for row in rows:
            cells = row.query_selector_all('td, th')
            if cells:
                data.append({
                    'first_name': cells[0].inner_text().strip() if len(cells) > 0 else '',
                    'last_name': cells[1].inner_text().strip() if len(cells) > 1 else '',
                    'email': cells[2].inner_text().strip() if len(cells) > 2 else '',
                    'role': cells[3].inner_text().strip() if len(cells) > 3 else '',
                    'manager': cells[4].inner_text().strip() if len(cells) > 4 else '',
                })
    
    return data
```

### Configuration

You can modify the configuration in the `CONFIG` section of the file:

```python
CONFIG = {
    'headless': False,  # True for headless mode (no window)
    'timeout': 30000,   # Timeout in milliseconds
    'wait_until': 'networkidle',  # Wait until the network is idle
    'viewport': {
        'width': 1920,
        'height': 1080
    }
}
```

## Integration with the UKG → BILL Process

Once you have the scraped data, you can:

1. **Generate the CSV for import into BILL** with the required fields:
   - First name
   - Last name
   - Email address
   - Role
   - Manager (supervisor's email)

2. **Combine data from UKG API + Scraping**:
   - Use `run-bill-batch.py` to get data from UKG
   - Use the scraper to get additional data from BILL
   - Combine both into a final CSV

## Complete Flow Example

### Step 1: Generate CSV from UKG data

```bash
# Generate CSV with UKG data (First name, Last name, Email, Role, Manager)
cd ..
python run-bill-batch.py --company-id J9A6Y --limit 10
# This will generate a CSV file with the required format
```

### Step 2: Import CSV to BILL using scraper

```bash
# Navigate to scraping folder
cd scraping

# Run scraper with URL and CSV file path
python scraper-playwright.py https://app-dev-bdc-stg.divvy.co/companies ../data/people-2026-01-09_10-57-00.csv
```

### Complete Automated Flow

The scraper will:
1. Navigate to the provided URL
2. Login automatically
3. Select the company (Vai Consulting by default)
4. Close any popups
5. Navigate to `/people` page
6. Click "Import People" button
7. Upload the CSV file
8. Click "Import people" submit button
9. Complete the import process

### CSV File Format

The CSV file should have the following columns (as per BILL requirements):
- **First name** (required)
- **Middle initial** (optional)
- **Last name** (required)
- **Email address** (required)
- **Role** (required)
- **Physical Card Status** (optional)
- **Membership Status** (optional)
- **Date Added** (optional)
- **Budget Count** (optional)
- **Manager** (optional - supervisor's email)

## Useful Playwright Commands

```bash
# View automatically generated code
playwright codegen https://app.bill.com/users

# Run in debug mode
PWDEBUG=1 python scraper-playwright.py <URL>

# View execution trace
playwright show-trace trace.zip
```

## Notes

- Results are automatically saved in JSON and CSV format
- Output files include timestamps to prevent overwriting
- Adjust CSS selectors according to the structure of the target page
- Automatic login is implemented and working
- You can change `headless: False` to `True` to run without a window

## Next Steps

1. ✅ Identify the exact URL of the BILL page you need to scrape
2. ✅ Inspect the CSS/HTML selectors of the elements you need
3. ⏳ Modify the `extract_data()` function with your specific selectors
4. ✅ Automatic login is already implemented
5. ⏳ Integrate the scraper with your UKG batch process.

## Troubleshooting

### Error: "playwright not found"
```bash
pip install playwright
playwright install chromium
```

### Error: "Credentials not found"
Make sure you have a `.env` file with `BILL_LOGIN_EMAIL` and `BILL_LOGIN_PASSWORD`.

### Login does not work
- Verify that the form selectors are correct.
- Run with `headless: False` to see what is happening.
- Increase the timeout if the page loads slowly.

### CSV file not found
- Verify the path to the CSV file is correct (use absolute path if relative path doesn't work).
- Check that the file exists and has read permissions.
- On Windows, use forward slashes or double backslashes in the path.

### Import button not found
- Make sure you're on the correct page (`/people`).
- Wait for the page to fully load before clicking.
- Check browser console for any JavaScript errors.

