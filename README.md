# Auto10bis

Automate daily 10bis voucher purchases to maximize your meal budget. Never miss a day of ordering again!

This bot automatically purchases Shufersal vouchers (or any other item) from 10bis, checking your daily and monthly budget limits before ordering. Perfect for employees who want to consistently use their 10bis allowance without manual daily ordering.

## Features

- ✅ Checks daily and monthly budget before purchasing
- ✅ Skips purchase if budget is exceeded
- ✅ Saves order confirmations (PDF + screenshot)
- ✅ Persistent browser session (login once, stay logged in)
- ✅ Dry-run mode for testing
- ✅ Debug mode for troubleshooting

## Prerequisites

- **10bis account** with MFA enabled (email + OTP SMS login)
- **Python 3.13+**
- **uv** (Python package manager) - [Install here](https://docs.astral.sh/uv/)

## Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
uv sync

# Install Playwright browsers (required for automation)
uv run playwright install chromium
```

Alternatively, use the Makefile:

```bash
make playwright-install
```

### 2. Configure Settings

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and update these **required** settings:

```bash
EMAIL="your.email@company.com"  # Your 10bis login email
DRY_RUN="False"                 # Set to False to actually place orders
```

**Optional settings** (defaults usually work fine):

```bash
ITEM_URL="..."      # Change to purchase different items
ITEM_PRICE="200.00" # Update if item price changes
HEADLESS="True"     # Set to False to see the browser window
DEBUG="False"       # Set to True for detailed logs
```

### 3. First Run (Login Setup)

Run with dry-run enabled first to set up your login:

```bash
make run
# or: uv run main.py
```

**What happens:**

1. Browser opens to 10bis
2. You'll be prompted to login (email + OTP code)
3. Login session is saved in `./profile/` directory
4. Budget is checked and displayed
5. Purchase is simulated (dry-run mode)

**Note:** You only need to login once! The session persists across runs.

### 4. Production Run

Once you've tested with dry-run, disable it in `.env`:

```bash
DRY_RUN="False"
```

Now running `make run` will actually place orders!

## Usage

### Manual Run

```bash
make run
```

### What It Does

1. Checks if you're logged in (uses saved session)
2. Navigates to Transactions Report
3. Reads your monthly and daily budget balance
4. Compares budget to item price
5. If sufficient budget:
   - Adds item to cart
   - Proceeds to checkout
   - Places order (unless `DRY_RUN=True`)
   - Saves confirmation screenshot and PDF
6. If insufficient budget:
   - Logs warning and exits

### Automated Daily Runs

To run this automatically every weekday at 10 AM, add to your crontab:

```bash
# Edit crontab
crontab -e

# Add this line (update path to your project):
0 10 * * 1-5 cd /path/to/auto10bis && /usr/local/bin/uv run main.py
```

Or use a scheduler like:

- **macOS**: launchd
- **Linux**: systemd timer
- **Windows**: Task Scheduler

## Output Files

Orders are saved in two locations:

```
./screenshots/     # PNG screenshots of order confirmation
./orders/          # PDF copies of order confirmation
```

Files are named with timestamps: `order-20250121-103045.png`

## Configuration Reference

| Variable        | Default        | Description                                 |
| --------------- | -------------- | ------------------------------------------- |
| `EMAIL`         | **Required**   | Your 10bis login email                      |
| `ITEM_URL`      | Shufersal ₪200 | URL of item to purchase                     |
| `ITEM_PRICE`    | 200.00         | Price of item (for budget checking)         |
| `HEADLESS`      | True           | Run browser in background                   |
| `DRY_RUN`       | True           | Simulate purchase without actually ordering |
| `DEBUG`         | False          | Show detailed debug logs                    |
| `BASE_URL`      | 10bis homepage | 10bis website URL                           |
| `USER_DATA_DIR` | ./profile      | Where to save browser session               |

## Troubleshooting

### "Email not found in settings"

You forgot to set `EMAIL` in your `.env` file.

**Fix:** Copy `.env.example` to `.env` and add your email.

### Browser doesn't open

Playwright browsers aren't installed.

**Fix:** Run `uv run playwright install chromium`

### "Login button not found"

You're already logged in! The bot will proceed normally.

**Debug:** Enable `DEBUG=True` in `.env` to see detailed logs.

### Budget shows ₪0 / Order fails

Either your budget is exhausted or the page structure changed.

**Debug:**

1. Set `HEADLESS=False` to watch the browser
2. Set `DEBUG=True` for detailed logs
3. Check if 10bis changed their website layout

### Session expired / Keep getting asked to login

The saved session in `./profile/` might be corrupted.

**Fix:** Delete the `./profile/` directory and login again.

### Want to change to a different item

1. Go to 10bis website
2. Find the item you want
3. Copy the full URL (including `?dishId=...`)
4. Update `ITEM_URL` in `.env`
5. Update `ITEM_PRICE` to match the item's price

## Development

### Project Structure

```
.
├── main.py           # Main bot logic
├── log.py            # Logger configuration
├── utils.py          # Helper functions
├── settings.py       # (if exists)
├── .env              # Your configuration
├── profile/          # Browser session data
├── screenshots/      # Order screenshots
└── orders/           # Order PDFs
```

### Debug Mode

Enable detailed logging to troubleshoot issues:

```bash
DEBUG="True"
```

This logs every browser interaction, button click, and navigation step.

### Makefile Commands

```bash
make run                # Run the bot
make playwright-install # Install browser engines
```

## Safety Features

- **Budget checking**: Never exceeds your daily or monthly limit
- **Dry-run mode**: Test without placing real orders
- **Persistent session**: Login once, not every time
- **Order confirmations**: Saved for your records

## Tips

1. **Test first**: Always run with `DRY_RUN=True` before going live
2. **Check logs**: Review what happened after each run
3. **Backup confirmations**: Keep the PDFs in `./orders/` for expense reports
4. **Monitor budget**: Bot logs your remaining budget each run
5. **Headless mode**: Keep `HEADLESS=True` for scheduled runs

## License

MIT (or whatever you prefer)

## Support

Found a bug or have a question? Open an issue on GitHub!
