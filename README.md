# README

Automation for purchasing 10bis vouchers for Shufersal, intended to run daily until budget exhausted for the month.

## Pre-requisites

- 10bis account, with MFA enabled (login with email + OTP SMS)
- Python 3.13+
- Playwright
- uv

## Installation

```shell
uv sync
```

## Configuration

See `.env.example`.

## Usage

```shell
# runs uv sync main.py
make
```
