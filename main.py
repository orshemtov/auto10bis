import asyncio
import datetime
import re

from playwright.async_api import BrowserContext, Page, async_playwright
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    base_url: str
    item_url: str
    item_price: float
    email: str
    first_name: str
    user_data_dir: str = "./profile"
    headless: bool = True
    dry_run: bool = True


# TODO: Make this more reliable
async def is_logged_in(page: Page) -> bool:
    login = page.get_by_role("button", name="Login")
    await login.wait_for(state="visible", timeout=10000)
    return not await login.is_visible()


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


async def open_transactions_report(page: Page, first_name: str) -> None:
    # TODO: Make selector better later on
    name = "Hi, " + first_name
    menu_btn = page.get_by_role("button", name=name)
    await menu_btn.wait_for(state="visible", timeout=30000)
    await menu_btn.click()

    transactions_report_item = page.get_by_text("Transactions Report", exact=True)
    await transactions_report_item.wait_for(state="visible", timeout=5000)
    await transactions_report_item.click()

    await page.wait_for_load_state("domcontentloaded")


async def parse_transactions_report(page: Page) -> dict[str, float]:
    def parse_amount(text: str) -> float:
        # Handles: ₪400, ₪ 400, 400₪
        m = re.search(r"₪\s*([0-9]+)", text) or re.search(r"([0-9]+)\s*₪", text)
        if not m:
            raise ValueError(f"Could not parse amount from text: {text}")
        return float(m.group(1))

    async def value_by_label(page: Page, label: str) -> float:
        label_loc = page.get_by_text(label, exact=True)
        container = label_loc.locator("..")
        txt = await container.inner_text()
        return parse_amount(txt)

    monthly_limit = await value_by_label(page, "Monthly limit")
    daily_limit = await value_by_label(page, "Daily limit")
    spent_this_month = await value_by_label(page, "Spent this month")
    spent_today = await value_by_label(page, "Spent today")
    monthly_balance = await value_by_label(page, "Monthly balance")
    daily_balance = await value_by_label(page, "Daily balance")

    return {
        "monthly_limit": monthly_limit,
        "daily_limit": daily_limit,
        "spent_this_month": spent_this_month,
        "spent_today": spent_today,
        "monthly_balance": monthly_balance,
        "daily_balance": daily_balance,
    }


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

    # Take a screenshot
    t = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    await page.screenshot(path=f"./screenshots/order-{t}.png")

    # Verify 'Coupon ordered successfully' message
    await page.get_by_text("Coupon ordered successfully").wait_for(
        state="visible", timeout=10000
    )

    # TODO: Save the result
    # There is a 'Print voucher' button - save as PDF


async def run(
    context: BrowserContext,
    base_url: str,
    email: str,
    first_name: str,
    item_url: str,
    item_price: float,
    dry_run: bool = True,
) -> None:
    page = await context.new_page()

    await page.goto(base_url, wait_until="domcontentloaded")
    await ensure_logged_in(page, email)
    await open_transactions_report(page, first_name)

    result = await parse_transactions_report(page)
    print(result)

    if result["daily_limit"] < item_price:
        print("Not enough balance to proceed.")
        return

    await add_to_cart(page, item_url)

    if dry_run:
        print("Dry run enabled, skipping checkout.")
        return

    await checkout(page)


async def main() -> None:
    settings = Settings()  # type: ignore

    async with async_playwright() as playwright:
        # browser = await p.chromium.launch(headless=False)
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=settings.user_data_dir,
            headless=settings.headless,
        )

        await run(
            context,
            settings.base_url,
            settings.email,
            settings.first_name,
            settings.item_url,
            settings.item_price,
        )

        # For debugging purposes
        await asyncio.sleep(30)

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
