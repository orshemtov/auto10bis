from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from utils import find_project_root

project_root = find_project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=project_root / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    base_url: str = "https://www.10bis.co.il/next/en/"

    # The default is a Shufersal voucher worth 200 ILS
    item_url: str = "https://www.10bis.co.il/next/en/restaurants/menu/delivery/26698/shufersal/?dishId=6552647"
    item_price: float = 200.00

    email: str

    user_data_dir: Path = project_root / "profile"
    screenshots_dir: Path = project_root / "screenshots"
    orders_dir: Path = project_root / "orders"

    headless: bool = True
    dry_run: bool = False
    debug: bool = False
