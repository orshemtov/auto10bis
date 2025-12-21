import asyncio
import datetime
import re
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext, Page, async_playwright
from pydantic import BaseModel

from settings import Settings
from utils import parse_amount, setup_logger


class BudgetInfo(BaseModel):
    monthly_balance: float
    daily_balance: float


async def is_logged_in(page: Page) -> bool:
    name = re.compile(r"^Hi,")
    menu_btn = page.get_by_role("button", name=name)
    try:
        await menu_btn.wait_for(state="visible", timeout=5000)
        return True
    except Exception:
        logger.debug("Login button not found, user not logged in")
        return False


async def ensure_logged_in(page: Page, email: str) -> None:
    """Ensure the user is logged in, performing login if necessary."""

    if await is_logged_in(page):
        logger.info("We are already logged in!")
        return

    logger.info("Not logged in, performing login...")

    await page.get_by_role("button", name="Login").click()

    # Login form is now visible
    await page.get_by_label("Email address").fill(email)
    dialog = page.get_by_role("dialog")
    await dialog.get_by_role("button", name="Login").click()

    # MFA popup requires code now
    otp_input = page.get_by_label("Insert the code")

    # Wait up to 60 seconds for OTP input
    await otp_input.wait_for(state="visible", timeout=60000)

    logger.info("Please check your email or phone for the OTP code.")

    otp = input("Enter the OTP code: ")
    await otp_input.fill(otp)

    await page.get_by_role("button", name="Accept").click()


async def get_value_by_label(page: Page, label: str) -> float:
    """
    Extract the amount value that precedes a label in the budget cards.

    Args:
        label: The readable label text (e.g., "Monthly limit", "Daily balance")

    Returns:
        The amount as a float

    DOM structure:
        <div class="Sum-..."><div>₪1000</div></div>
        <div class="Text-...">Monthly limit</div>
    """
    label_loc = page.get_by_text(label, exact=True)
    await label_loc.wait_for(state="visible", timeout=5000)

    # The amount is in the immediately preceding sibling element
    amount_div = label_loc.locator("xpath=preceding-sibling::*[1]")

    # Extract the text (e.g., "₪1000")
    # Parse and return the numeric value
    txt = await amount_div.inner_text()
    amount = parse_amount(txt)

    return amount


async def parse_transactions_report(page: Page) -> BudgetInfo:
    logger.info("Parsing transactions report...")

    logger.debug("Clicking user menu button...")
    name = re.compile(r"^Hi,")
    menu_btn = page.get_by_role("button", name=name)
    await menu_btn.wait_for(state="visible", timeout=30000)
    await menu_btn.click()

    logger.debug("Navigating to Transactions Report...")
    transactions_report_item = page.get_by_text("Transactions Report", exact=True)
    await transactions_report_item.wait_for(state="visible", timeout=5000)
    await transactions_report_item.click()

    await page.wait_for_load_state("domcontentloaded")

    logger.debug("Extracting budget values...")
    monthly_balance = await get_value_by_label(page, "Monthly balance")
    daily_balance = await get_value_by_label(page, "Daily balance")

    budget_info = BudgetInfo(
        monthly_balance=monthly_balance,
        daily_balance=daily_balance,
    )

    return budget_info


def should_skip(info: BudgetInfo, item_price: float) -> bool:
    """Skip if budget is exceeded for the day or for the month"""
    if info.monthly_balance < item_price:
        logger.warning("Monthly budget exceeded.")
        return True

    if info.daily_balance < item_price:
        logger.warning("Daily budget exceeded.")
        return True

    return False


async def add_to_cart(page: Page, item_url: str) -> None:
    logger.debug(f"Navigating to item: {item_url}")
    await page.goto(item_url, wait_until="domcontentloaded")

    logger.debug("Clicking 'Add item' button...")
    add_btn = page.get_by_role("button", name=re.compile(r"^Add item"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()

    logger.debug("Clicking 'Proceed to payment' button...")
    payment_btn = page.get_by_role("button", name="Proceed to payment")
    await payment_btn.wait_for(state="visible", timeout=15_000)
    await payment_btn.click()


async def checkout(page: Page, screenshots_dir: Path, orders_dir: Path) -> None:
    logger.debug("Clicking 'Place order' button...")
    add_btn = page.get_by_role("button", name=re.compile(r"^Place order"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()

    logger.debug("Waiting for order confirmation...")
    await page.get_by_text("Coupon ordered successfully").wait_for(
        state="visible", timeout=10000
    )

    # Generate a timestamp for this order
    t = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    # Screenshot the confirmation page
    screenshot_path = screenshots_dir / f"order-{t}.png"
    await page.screenshot(path=screenshot_path)
    logger.info(f"Saved screenshot to {screenshot_path}")

    # Save the result
    pdf_path = orders_dir / f"order-{t}.pdf"
    await page.emulate_media(media="print")
    await page.pdf(path=pdf_path, format="A4", print_background=True)
    logger.info(f"Saved order PDF to {pdf_path}")


async def run(
    context: BrowserContext,
    base_url: str,
    email: str,
    item_url: str,
    item_price: float,
    dry_run: bool,
    screenshots_dir: Path,
    orders_dir: Path,
) -> None:
    page = await context.new_page()

    await page.goto(base_url, wait_until="domcontentloaded")
    title = await page.title()
    logger.info(f"Loaded base URL: {title}")

    await ensure_logged_in(page, email)

    result = await parse_transactions_report(page)
    logger.info(
        f"Budget - Monthly: ₪{result.monthly_balance}, Daily: ₪{result.daily_balance}"
    )

    if should_skip(result, item_price):
        logger.info("Budget exceeded, skipping purchase.")
        return

    await add_to_cart(page, item_url)
    logger.info("Item added to cart.")

    if dry_run:
        logger.warning("Dry run enabled, skipping checkout...")
        return

    logger.info("Checking out...")
    await checkout(page, screenshots_dir, orders_dir)

    logger.success("Order completed successfully.")


async def main() -> None:
    settings = Settings()  # type: ignore
    setup_logger(debug=settings.debug)

    # Make sure the necessary directories exist
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    settings.screenshots_dir.mkdir(parents=True, exist_ok=True)
    settings.orders_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting purchase bot...")

    logger.info(f"Item URL: {settings.item_url}")
    logger.info(f"Item Price: {settings.item_price}")

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=settings.user_data_dir,
            headless=settings.headless,
        )

        await run(
            context,
            base_url=settings.base_url,
            email=settings.email,
            item_url=settings.item_url,
            item_price=settings.item_price,
            dry_run=settings.dry_run,
            screenshots_dir=settings.screenshots_dir,
            orders_dir=settings.orders_dir,
        )

        await context.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user, exiting...")
