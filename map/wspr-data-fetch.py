import requests
import json
import os
from datetime import datetime, timedelta
import time

# Configurable Parameters
CALLSIGN = 'K6FTP'
HOURS = 24
OUTPUT_DIR = '/home/wspr-zero/public_html/map'
wspr_data_tx_file = os.path.join(OUTPUT_DIR, 'wspr_data_tx.json')
wspr_data_rx_file = os.path.join(OUTPUT_DIR, 'wspr_data_rx.json')
furthest_contact_file = os.path.join(OUTPUT_DIR, 'furthest_contact.json')

# Calculate the start and end dates
end_date = datetime.utcnow()
start_date = end_date - timedelta(hours=HOURS)
start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

# API Query URLs
tx_query_url = f'https://wspr.live/wspr_downloader.php?start={start_date_str}&end={end_date_str}&tx_sign={CALLSIGN}&rx_sign=%&format=JSON'
rx_query_url = f'https://wspr.live/wspr_downloader.php?start={start_date_str}&end={end_date_str}&tx_sign=%&rx_sign={CALLSIGN}&format=JSON'

print(f'TX Query URL: {tx_query_url}')
print(f'RX Query URL: {rx_query_url}')

# Custom headers with User-Agent
headers = {
    'User-Agent': 'WSPR-zero (https://wspr-zero.com)'
}

# Function to fetch and save WSPR data
def fetch_and_save_wspr_data(url, file_path):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.RequestException as e:
        print(f'Error fetching data from {url}: {e}')
        return None

    if not response.text.strip():
        print(f'No data returned from the server for {url}')
        return None

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        print('Error decoding JSON response.')
        print(f'Response content: {response.text}')
        print(f'Error: {e}')
        return None

    # Commented out the line that prints the received data
    # print(f'Response content: {json.dumps(data, indent=4)}')

    if isinstance(data, dict) and data.get('rows', 0) > 0:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f'Successfully downloaded WSPR data to {file_path}')
        return data
    else:
        with open(file_path, 'w') as f:
            json.dump({"callsign": CALLSIGN, "results": 0}, f, indent=4)
        print(f'No valid data available for the given time range in {url}. Wrote empty file to {file_path}')
        return None

# Fetch TX data
tx_data = fetch_and_save_wspr_data(tx_query_url, wspr_data_tx_file)

# Adding a delay between the requests
time.sleep(5)

# Fetch RX data
rx_data = fetch_and_save_wspr_data(rx_query_url, wspr_data_rx_file)

# Function to determine the furthest contact
def get_furthest_contact(data, contact_type):
    if data and 'data' in data and len(data['data']) > 0:
        furthest_spot = max(data['data'], key=lambda x: float(x['distance']), default=None)
        if furthest_spot:
            return {
                'type': contact_type,
                'tx_sign': furthest_spot['tx_sign'],
                'rx_sign': furthest_spot['rx_sign'],
                'distance': float(furthest_spot['distance']),
                'time': furthest_spot['time'],
                'tx_lat': furthest_spot['tx_lat'],
                'tx_lon': furthest_spot['tx_lon'],
                'rx_lat': furthest_spot['rx_lat'],
                'rx_lon': furthest_spot['rx_lon'],
                'frequency': furthest_spot['frequency']
            }
    return None

# Determine the furthest TX contact
furthest_tx_contact = get_furthest_contact(tx_data, 'TX')

# Determine the furthest RX contact
furthest_rx_contact = get_furthest_contact(rx_data, 'RX')

# Read existing furthest contact data if available
furthest_contact_data = {}
if os.path.exists(furthest_contact_file):
    try:
        with open(furthest_contact_file, 'r') as f:
            furthest_contact_data = json.load(f)
    except json.JSONDecodeError:
        print('Error decoding existing furthest contact JSON file.')

# Update furthest contact data
def update_furthest_contact(existing_data, new_contact):
    if new_contact:
        new_distance = new_contact['distance']
        existing_distance = float(existing_data.get('distance', 0))

        if new_distance > existing_distance:
            return new_contact
    return existing_data

furthest_contact_data['TX'] = update_furthest_contact(furthest_contact_data.get('TX', {}), furthest_tx_contact)
furthest_contact_data['RX'] = update_furthest_contact(furthest_contact_data.get('RX', {}), furthest_rx_contact)

# Save updated furthest contact data
with open(furthest_contact_file, 'w') as f:
    json.dump(furthest_contact_data, f, indent=4)
print(f'Updated furthest contact data in {furthest_contact_file}')

