import asyncio
import datetime
import re
import logging
from playwright.async_api import BrowserContext, Page, async_playwright
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    base_url: str
    item_url: str
    item_price: float
    email: str
    user_data_dir: str = "./profile"
    headless: bool = False
    dry_run: bool = True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


async def is_logged_in(page: Page) -> bool:
    name = re.compile(r"^Hi,")
    menu_btn = page.get_by_role("button", name=name)
    try:
        await menu_btn.wait_for(state="visible", timeout=5000)
        return True
    except:
        return False


async def ensure_logged_in(page: Page, email: str) -> None:
    # Early return if we're already logged in
    if await is_logged_in(page):
        print("We are already logged in!")
        return

    # Click the login button
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


async def parse_transactions_report(page: Page) -> dict[str, float]:
    name = re.compile(r"^Hi,")
    menu_btn = page.get_by_role("button", name=name)
    await menu_btn.wait_for(state="visible", timeout=30000)
    await menu_btn.click()

    transactions_report_item = page.get_by_text("Transactions Report", exact=True)
    await transactions_report_item.wait_for(state="visible", timeout=5000)
    await transactions_report_item.click()

    await page.wait_for_load_state("domcontentloaded")

    await asyncio.sleep(30)

    def parse_amount(text: str) -> float:
        pattern_1 = r"₪\s*([0-9]+)"  # ₪400, ₪ 400
        pattern_2 = r"([0-9]+)\s*₪"  # 400₪
        matches = re.search(pattern_1, text) or re.search(pattern_2, text)
        if not matches:
            raise ValueError(f"Could not parse amount from text: {text}")
        return float(matches.group(1))

    async def get_value_by_label(page: Page, label: str) -> float:
        label_loc = page.get_by_text(label, exact=True)

        # TODO: We assume the value is in the parent container
        container = label_loc.locator("..")

        txt = await container.inner_text()
        return parse_amount(txt)

    monthly_limit = await get_value_by_label(page, "Monthly limit")
    daily_limit = await get_value_by_label(page, "Daily limit")
    spent_this_month = await get_value_by_label(page, "Spent this month")
    spent_today = await get_value_by_label(page, "Spent today")
    monthly_balance = await get_value_by_label(page, "Monthly balance")
    daily_balance = await get_value_by_label(page, "Daily balance")

    return BudgetInfo(
        monthly_limit=monthly_limit,
        daily_limit=daily_limit,
        spent_this_month=spent_this_month,
        spent_today=spent_today,
        monthly_balance=monthly_balance,
        daily_balance=daily_balance,
    )


class BudgetInfo(BaseModel):
    monthly_limit: float
    daily_limit: float
    spent_this_month: float
    spent_today: float
    monthly_balance: float
    daily_balance: float


def should_skip(info: BudgetInfo, item_price: float) -> bool:
    """Skip if budget is exceeded for the day or for the month"""

    if info.daily_balance < item_price:
        return False

    if info.monthly_balance < item_price:
        return False

    return True


async def add_to_cart(page: Page, item_url: str) -> None:
    await page.goto(item_url, wait_until="domcontentloaded")

    # TODO: Verify that item page was loaded correctly

    add_btn = page.get_by_role("button", name=re.compile(r"^Add item"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()

    payment_btn = page.get_by_role("button", name="Proceed to payment")
    await payment_btn.wait_for(state="visible", timeout=15_000)
    await payment_btn.click()


# TODO:Verify
async def checkout(page: Page) -> None:
    add_btn = page.get_by_role("button", name=re.compile(r"^Place order"))
    await add_btn.wait_for(state="visible", timeout=15_000)
    await add_btn.click()
    print("Item was bought!")

    # TODO: For debugging purposes
    await asyncio.sleep(30)

    # TODO: Wait for the order confirmation page to load
    # TODO: Verify 'Coupon ordered successfully' message
    await page.get_by_text("Coupon ordered successfully").wait_for(
        state="visible", timeout=10000
    )
    print("Order is confirmed!")

    # Take a screenshot
    t = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    await page.screenshot(path=f"./screenshots/order-{t}.png")

    # TODO: Save the result
    # There is a 'Print voucher' button - save as PDF
    page.emulate_media(media="print")
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
    print(result)

    if should_skip(result, item_price):
        print("Budget exceeded, skipping purchase.")
        return

    await add_to_cart(page, item_url)

    if dry_run:
        print("Dry run enabled, skipping checkout.")
        return

    print("Checking out...")
    await checkout(page)


async def main() -> None:
    settings = Settings()  # type: ignore

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
        print("Exiting...")
