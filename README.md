# Roblox Friends Tracker & Exporter

A lightweight Python CLI tool to export your Roblox friends list to CSV/JSON and track changes over time. It logs who unfriended you, detects new connections, and handles API rate limits automatically.

## Features

- **Snapshot Export:** Dumps full friend list to `CSV` (for Excel) and `JSON`.
- **Change Detection:** Compares against local history to detect:
  - ❌ **Unfriends:** Users who removed you.
  - ✅ **New Friends:** New connections made since the last run.
- **Data Safety:** Includes a fallback mechanism. If the Roblox API returns empty names (common issue), the script retrieves them from your local history instead of corrupting the file.
- **Resilient:** Automatically handles `429 Too Many Requests` with retry logic.

## Prerequisites

- Python 3.x
- A valid `.ROBLOSECURITY` cookie.

## Installation

1. Clone the repository:
   git clone https://github.com/deogw/Roblox-Friends-Tracker.git
   cd Roblox-Friends-Tracker

2. Install dependencies:
   pip install -r requirements.txt

## Quick Start

1. Run the script:
   python run.py

2. Authenticate (First Run):
   - The script will detect if "cookie.txt" is missing.
   - Paste your .ROBLOSECURITY cookie when prompted.
   - Type "y" to save it locally for future auto-login.

3. View Data:
   - Excel/Sheets: Open "[username]_friends.csv".
   - Track Changes: Check "[username]_activity_log.txt" to see unfriended users or new connections.

## How to get your Cookie

1. Go to Roblox.com and log in.
2. Open Developer Tools (F12 or Ctrl+Shift+I).
3. Navigate to the "Application" tab (Storage).
4. Under "Cookies", select "https://www.roblox.com".
5. Copy the value of ".ROBLOSECURITY".

**WARNING: Never share your .ROBLOSECURITY cookie with anyone. This script runs locally on your machine and does not transmit your credentials elsewhere.**

## License

MIT