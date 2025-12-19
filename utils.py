import re

from playwright.async_api import Page


def parse_amount(text: str) -> float:
    pattern_1 = r"₪\s*([0-9]+)"  # ₪400, ₪ 400
    pattern_2 = r"([0-9]+)\s*₪"  # 400₪
    matches = re.search(pattern_1, text) or re.search(pattern_2, text)
    if not matches:
        raise ValueError(f"Could not parse amount from text: {text}")
    return float(matches.group(1))


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
