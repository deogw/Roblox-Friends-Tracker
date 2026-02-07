#!/usr/bin/env python3
import requests
import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional

from colorama import Fore, Style, init

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookie.txt")
BATCH_SIZE = 50
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 5

# Auto-reset colors after printing
init(autoreset=True)

def log(message, color=Fore.CYAN, level="INFO"):
    print(f"{color}{Style.BRIGHT}[{level}] {Style.RESET_ALL}{message}")

# --- Core Logic ---

def load_cookie() -> Optional[str]:
    """Load cookie from file. Ask user input if missing."""
    
    # Check file first
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content: return content
        except Exception as e:
            log(f"Read error on '{COOKIE_FILE}': {e}", Fore.RED, "ERROR")

    # Fallback: Manual input
    log(f"'{COOKIE_FILE}' not found or empty.", Fore.YELLOW, "WARN")
    print(f"{Style.BRIGHT}Paste .ROBLOSECURITY cookie below:{Style.RESET_ALL}")
    
    try:
        cookie = input(f"{Fore.CYAN}> {Style.RESET_ALL}").strip()
    except KeyboardInterrupt:
        print()
        return None

    if not cookie: return None

    # Offer to save for next time
    if input(f"Save to '{COOKIE_FILE}'? (y/n) > ").strip().lower() == 'y':
        try:
            with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                f.write(cookie)
            log(f"Saved to '{COOKIE_FILE}'.", Fore.GREEN)
        except Exception as e:
            log(f"Save failed: {e}", Fore.RED, "ERROR")

    return cookie

def get_headers(cookie: str) -> Dict:
    return {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Roblox/WinInet",
        "Content-Type": "application/json"
    }

def load_local_history(username: str) -> List[Dict]:
    """Load existing JSON data to use as fallback."""
    filename = os.path.join(BASE_DIR, f"{username}_friends.json")
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def get_auth_user(cookie: str):
    """Validate cookie and get user info."""
    url = "https://users.roblox.com/v1/users/authenticated"
    try:
        resp = requests.get(url, headers=get_headers(cookie))
        if resp.status_code == 200:
            data = resp.json()
            log(f"User: {Style.BRIGHT}{data['name']}{Style.RESET_ALL} (ID: {data['id']})", Fore.GREEN)
            return data['id'], data['name']
        log(f"Auth failed. Code: {resp.status_code}", Fore.RED, "ERROR")
        return None, None
    except requests.RequestException as e:
        log(f"Connection error: {e}", Fore.RED, "ERROR")
        return None, None

def fetch_friend_ids(user_id: int, cookie: str) -> Optional[List[Dict]]:
    """Get raw friend list (IDs only) using pagination."""
    log("Fetching friend list...", Fore.BLUE)
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends/find"
    
    all_friends = []
    cursor = None
    
    while True:
        params = {"limit": 50}
        if cursor:
            params["cursor"] = cursor
            
        try:
            resp = requests.get(url, headers=get_headers(cookie), params=params)
            
            if resp.status_code == 200:
                data = resp.json()
                # Handle possible response structures
                items = data.get('PageItems', []) or data.get('data', [])
                all_friends.extend(items)
                
                cursor = data.get('NextCursor') 
                if not cursor:
                    break
            elif resp.status_code == 429:
                log("Rate limit (429). Retrying...", Fore.YELLOW, "WARN")
                time.sleep(RATE_LIMIT_DELAY)
                continue
            else:
                log(f"Error fetching list: {resp.status_code}", Fore.RED, "ERROR")
                break
                
        except requests.RequestException:
            log("Network error while fetching friends.", Fore.RED, "ERROR")
            break
            
    log(f"Found {len(all_friends)} connections.", Fore.BLUE)
    return all_friends

def fetch_user_details(friends: List[Dict], cookie: str, username: str) -> List[Dict]:
    """
    Get details (Name, DisplayName) in batches.
    Handles 429 errors and falls back to local JSON if API fails.
    """
    if not friends: return []
    
    log("Fetching user details...", Fore.BLUE)
    
    local_data = {u['id']: u for u in load_local_history(username)}
    user_ids = [f['id'] for f in friends]
    fetched_map = {}
    
    url = "https://users.roblox.com/v1/users"

    # Batch process to avoid hitting limits
    for i in range(0, len(user_ids), BATCH_SIZE):
        batch = user_ids[i:i + BATCH_SIZE]
        payload = {"userIds": batch, "excludeBannedUsers": False}
        
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url, json=payload, headers=get_headers(cookie))
                if resp.status_code == 200:
                    for u in resp.json().get('data', []):
                        fetched_map[u['id']] = u
                    break
                elif resp.status_code == 429:
                    wait = (attempt + 1) * RATE_LIMIT_DELAY
                    log(f"Rate limit on batch {i}. Retrying in {wait}s...", Fore.YELLOW, "WARN")
                    time.sleep(wait)
                else:
                    break
            except requests.RequestException:
                time.sleep(1)

    # Merge: API Data > Local History > Raw
    final_list = []
    recovered = 0
    
    for f in friends:
        fid = f['id']
        api_data = fetched_map.get(fid)
        local_entry = local_data.get(fid)

        if api_data:
            f.update({
                'name': api_data.get('name'),
                'displayName': api_data.get('displayName'),
                'hasVerifiedBadge': api_data.get('hasVerifiedBadge')
            })
        elif local_entry and local_entry.get('name'):
            # Fallback to avoid empty names
            f.update({
                'name': local_entry.get('name'),
                'displayName': local_entry.get('displayName'),
                'hasVerifiedBadge': local_entry.get('hasVerifiedBadge')
            })
            recovered += 1
        
        final_list.append(f)

    if recovered:
        log(f"Recovered {recovered} names from local history.", Fore.YELLOW, "WARN")
    
    return final_list

def analyze_changes(current_list: List[Dict], username: str):
    """Check for unfriends/new friends vs local history."""
    json_file = os.path.join(BASE_DIR, f"{username}_friends.json")
    log_file = os.path.join(BASE_DIR, f"{username}_activity_log.txt")
    
    # Sanity check: Don't analyze if data looks corrupt (too many empty names)
    empty_names = sum(1 for f in current_list if not f.get('name'))
    if len(current_list) > 0 and (empty_names / len(current_list)) > 0.5:
        log("Too many missing names. Skipping analysis.", Fore.RED, "SKIP")
        return

    if not os.path.exists(json_file): return

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            old_list = json.load(f)
    except:
        return

    old_map = {u['id']: u for u in old_list}
    cur_map = {u['id']: u for u in current_list}
    
    old_ids = set(old_map.keys())
    cur_ids = set(cur_map.keys())

    unfriended = old_ids - cur_ids
    new_friends = cur_ids - old_ids
    
    if not unfriended and not new_friends:
        log("No changes detected.", Fore.CYAN)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs = []

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}--- ACTIVITY REPORT ---{Style.RESET_ALL}")

    if unfriended:
        print(f"{Fore.RED}❌ LOST ({len(unfriended)}):{Style.RESET_ALL}")
        for uid in unfriended:
            u = old_map[uid]
            print(f"   - {u.get('name', 'Unknown')} (@{u.get('displayName', '-')})")
            logs.append(f"[{timestamp}] ❌ UNFRIENDED: {u.get('name')} (ID: {uid})\n")

    if new_friends:
        print(f"{Fore.GREEN}✅ NEW ({len(new_friends)}):{Style.RESET_ALL}")
        for uid in new_friends:
            u = cur_map[uid]
            print(f"   + {u.get('name', 'Unknown')} (@{u.get('displayName', '-')})")
            logs.append(f"[{timestamp}] ✅ NEW FRIEND: {u.get('name')} (ID: {uid})\n")
    
    print(f"{Fore.MAGENTA}{Style.BRIGHT}-----------------------{Style.RESET_ALL}\n")

    try:
        with open(log_file, "a", encoding='utf-8') as f:
            f.writelines(logs)
        log("Activity log updated.", Fore.GREEN)
    except Exception as e:
        log(f"Log write failed: {e}", Fore.RED, "ERROR")

def save_database(friends: List[Dict], username: str):
    if not friends: return

    # Guard: Don't save if data is mostly garbage
    invalid_count = sum(1 for f in friends if not f.get('name'))
    if len(friends) > 0 and (invalid_count / len(friends)) > 0.2:
        log("Data corruption detected (names missing). Aborting save.", Fore.RED, "PROTECTION")
        return

    try:
        with open(os.path.join(BASE_DIR, f"{username}_friends.json"), 'w', encoding='utf-8') as f:
            json.dump(friends, f, indent=4)
    except IOError:
        log("Failed to save JSON.", Fore.RED, "ERROR")

    try:
        with open(os.path.join(BASE_DIR, f"{username}_friends.csv"), 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=friends[0].keys())
            writer.writeheader()
            writer.writerows(friends)
        log("Database updated.", Fore.GREEN)
    except IOError:
        log("Failed to save CSV.", Fore.RED, "ERROR")

# --- Main ---

if __name__ == "__main__":
    print(f"{Fore.MAGENTA}{Style.BRIGHT}Roblox Friends Tracker | https://github.com/deogw {Style.RESET_ALL}")
    
    cookie = load_cookie()
    if not cookie: 
        log("Process terminated.", Fore.RED, "EXIT")
        sys.exit(1)

    uid, username = get_auth_user(cookie)
    if not uid: sys.exit(1)

    raw_friends = fetch_friend_ids(uid, cookie)
    if raw_friends is None:
        log("API Error. Halting.", Fore.RED, "STOP")
        sys.exit(1)

    data = fetch_user_details(raw_friends, cookie, username)
    analyze_changes(data, username)
    save_database(data, username)