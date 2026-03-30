"""CSS selectors for BILL.com pages."""


class Selectors:
    """CSS selectors organized by page/component."""

    class Login:
        """Login page selectors."""
        EMAIL_INPUT = 'input#email, input[name="email"]'
        PASSWORD_INPUT = 'input#password, input[name="password"]'
        SUBMIT_BUTTON = [
            'button[type="submit"]',
            'button[name="login"]',
            'input[type="submit"]',
            '[data-testid*="login"]',
            '[data-testid*="submit"]',
            'button:has-text("Log in")',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
        ]

    class Company:
        """Company selection page selectors."""
        COMPANY_XPATH_TEMPLATE = '//div[contains(text(), "{company_name}")]'
        COMPANY_CELL = 'div[data-testid*="Cell-name"], div[class*="Cell-name"]'

    class Popup:
        """Popup/modal close button selectors."""
        CLOSE_SVG = 'svg[data-testid="Icon-svg-Close"]'
        CLOSE_BUTTON_VIA_SVG = 'button:has(svg[data-testid="Icon-svg-Close"])'
        MODAL_CLOSE = 'button[class*="Modal-close"], button[class*="close-button"]'
        SVG_CLOSE_CLASS = 'svg[class*="Close"], svg[class*="close"]'
        COMMON_CLOSE = [
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

    class Import:
        """Import people page selectors."""
        IMPORT_BUTTON_TESTID = 'button[data-testid*="import-people"], button[data-testid*="Import"]'
        IMPORT_BUTTON_ARIA = 'button[aria-label*="import" i], button[aria-label*="Import" i]'
        SUBMIT_BUTTON_TESTID = 'button[data-testid="ImportPeople-import-people-BasicButton"]'
        SUBMIT_BUTTON_PATTERN = 'button[data-testid*="import-people"], button[data-testid*="ImportPeople"]'

    class FileUpload:
        """File upload selectors."""
        FILE_INPUT_ID = 'input#file-input[type="file"]'
        FILE_INPUT_LABEL = 'label[data-testid="DragAndDropTarget-FileInput-label"]'
        FILE_INPUT_GENERIC = 'input[type="file"]'
