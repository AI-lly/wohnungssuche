import requests
from bs4 import BeautifulSoup
import json
import os
import time
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PHONE = os.getenv("CALLMEBOT_PHONE")
APIKEY = os.getenv("CALLMEBOT_APIKEY")
INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))

# Search filters (read from .env)
FILTER_CITIES = [c.strip().lower() for c in os.getenv("FILTER_CITIES", "frankfurt").split(",")]
_rooms_env = os.getenv("FILTER_ROOMS", "").strip()
FILTER_ROOMS = [] if (_rooms_env == "" or _rooms_env.lower() == "all") else [r.strip() for r in _rooms_env.split(",")]  # empty/"all" = all rooms

# Constants
URL = "https://www.nhw.de/wohnungsangebote"
STATE_FILE = "seen_apartments.json"

def send_whatsapp_message(message):
    """Sends a WhatsApp message using the CallMeBot API."""
    if not PHONE or not APIKEY or 'XXX' in PHONE:
        print(f"Skipping WhatsApp message (not configured): {message}")
        return False

    url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={requests.utils.quote(message)}&apikey={APIKEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("Successfully sent WhatsApp message.")
            return True
        else:
            print(f"Failed to send message: {response.text}")
            return False
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return False

def load_seen_apartments():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_seen_apartments(seen):
    with open(STATE_FILE, 'w') as f:
        json.dump(seen, f, indent=4)

def check_for_new_apartments():
    print(f"Checking for new apartments at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
    
    seen_apartments = load_seen_apartments()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # The NHW page uses Isotope to filter items client-side.
    # The URL parameters don't filter the HTML, they tell the JS to filter.
    # We need to manually parse the elements and check if they belong to Frankfurt and have 2 rooms.
    # We look for <div class="immo--item">
    
    items = soup.find_all('div', class_='immo--item')
    new_apartments_found = False
    
    for item in items:
        # Check data attributes correctly
        city = ""
        rooms = ""
        filter_data = item.find('div', class_='immo--filterdata')
        if filter_data:
            geo_span = filter_data.find('span', attrs={'data-filtertype': 'geo'})
            rooms_span = filter_data.find('span', attrs={'data-filtertype': 'anzahl_zimmer'})
            if geo_span:
                city = geo_span.get('data-filtervalue', '').lower()
            if rooms_span:
                rooms = rooms_span.get('data-filtervalue', '')
        
        # Check against configured filters
        city_match = any(f in city for f in FILTER_CITIES)
        rooms_match = (not FILTER_ROOMS) or (rooms in FILTER_ROOMS)  # empty = all rooms
        if city_match and rooms_match:
            # Extract apartment link
            link_elem = item.find('a', class_='immo--item--link')
            if not link_elem:
                link_elem = item.find('a', href=True)
            
            if link_elem and 'href' in link_elem.attrs:
                href = link_elem['href']
                full_url = "https://www.nhw.de" + href if href.startswith('/') else href
                
                # Extract title/address
                title_elem = item.find('span', class_='immo--item--title') or item.find('em', class_='immo--item--location')
                title = title_elem.text.strip() if title_elem else f"Wohnung in {city.capitalize()}"
                
                # Create a unique ID
                uid = item.get('data-itemuid', href)
                
                if uid not in seen_apartments:
                    print(f"NEW APARTMENT FOUND: {title} ({full_url})")
                    
                    message = f"🚨 *Neue Wohnung bei NHW!*\n\n{title}\nZimmer: {rooms}\nStadt: {city.capitalize()}\n\nLink: {full_url}"
                    if send_whatsapp_message(message):
                        # Only add to seen if message was sent successfully
                        seen_apartments.append(uid)
                        save_seen_apartments(seen_apartments)
                        new_apartments_found = True
                        time.sleep(3)  # Wait 3s between messages to avoid CallMeBot rate limiting
                    else:
                        print("Message sending failed. Will retry next time.")

    if not new_apartments_found:
        print("No new apartments found.")

if __name__ == "__main__":
    once = "--once" in sys.argv
    if once:
        print("Running in single-check mode (--once)...")
        check_for_new_apartments()
    else:
        print("Starting NHW Apartment Tracker (continuous mode)...")
        while True:
            check_for_new_apartments()
            print(f"Sleeping for {INTERVAL} seconds...")
            time.sleep(INTERVAL)
