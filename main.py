import asyncio
import datetime
import re

from loguru import logger
from playwright.async_api import BrowserContext, Page, async_playwright
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from log import setup_logger
from utils import get_value_by_label

setup_logger()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    base_url: str
    item_url: str
    item_price: float
    email: str
    user_data_dir: str = "./profile"
    headless: bool = False
    dry_run: bool = True


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
        # Button not found, not logged in
        return False


async def ensure_logged_in(page: Page, email: str) -> None:
    """Ensure the user is logged in, performing login if necessary."""

    if await is_logged_in(page):
        logger.info("We are already logged in!")
        return

    await page.get_by_role("button", name="Login").click()

    # Login form is now visible
    await page.get_by_label("Email address").fill(email)
    dialog = page.get_by_role("dialog")
    await dialog.get_by_role("button", name="Login").click()

    # MFA popup requires code now
    otp_input = page.get_by_label("Insert the code")

    # Wait up to 60 seconds for OTP input
    await otp_input.wait_for(state="visible", timeout=60000)

    otp = input("Enter the OTP sent to your email or phone: ")
    await otp_input.fill(otp)

    await page.get_by_role("button", name="Accept").click()


async def parse_transactions_report(page: Page) -> BudgetInfo:
    name = re.compile(r"^Hi,")
    menu_btn = page.get_by_role("button", name=name)
    await menu_btn.wait_for(state="visible", timeout=30000)
    await menu_btn.click()

    transactions_report_item = page.get_by_text("Transactions Report", exact=True)
    await transactions_report_item.wait_for(state="visible", timeout=5000)
    await transactions_report_item.click()

    await page.wait_for_load_state("domcontentloaded")

    monthly_balance = await get_value_by_label(page, "Monthly balance")
    daily_balance = await get_value_by_label(page, "Daily balance")

    return BudgetInfo(
        monthly_balance=monthly_balance,
        daily_balance=daily_balance,
    )


def should_skip(info: BudgetInfo, item_price: float) -> bool:
    """Skip if budget is exceeded for the day or for the month"""
    if info.monthly_balance < item_price:
        logger.info("Monthly budget exceeded.")
        return True

    if info.daily_balance < item_price:
        logger.info("Daily budget exceeded.")
        return True

    return False


async def add_to_cart(page: Page, item_url: str) -> None:
    await page.goto(item_url, wait_until="domcontentloaded")

    add_btn = page.get_by_role("button", name=re.compile(r"^Add item"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()

    payment_btn = page.get_by_role("button", name="Proceed to payment")
    await payment_btn.wait_for(state="visible", timeout=15_000)
    await payment_btn.click()


async def checkout(page: Page) -> None:
    add_btn = page.get_by_role("button", name=re.compile(r"^Place order"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()

    await page.get_by_text("Coupon ordered successfully").wait_for(
        state="visible", timeout=10000
    )

    # Generate a timestamp for this order
    t = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    # Screenshot the confirmation page
    await page.screenshot(path=f"./screenshots/order-{t}.png")

    # TODO: Save the result
    # There is a 'logger.info voucher' button - save as PDF
    await page.emulate_media(media="print")
    await page.pdf(path=f"./orders/order-{t}.pdf", format="A4")


async def run(
    context: BrowserContext,
    base_url: str,
    email: str,
    item_url: str,
    item_price: float,
    dry_run: bool,
) -> None:
    page = await context.new_page()

    await page.goto(base_url, wait_until="domcontentloaded")
    await ensure_logged_in(page, email)

    result = await parse_transactions_report(page)
    logger.info(result)

    if should_skip(result, item_price):
        logger.info("Budget exceeded, skipping purchase.")
        return

    await add_to_cart(page, item_url)

    if dry_run:
        logger.info("Dry run enabled, skipping checkout.")
        return

    logger.info("Checking out...")
    await checkout(page)


async def main() -> None:
    settings = Settings()  # type: ignore

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
            settings.base_url,
            settings.email,
            settings.item_url,
            settings.item_price,
            dry_run=settings.dry_run,
        )

        await context.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
