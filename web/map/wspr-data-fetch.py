import requests
import json
import os
from datetime import datetime, timedelta

# Configurable Parameters
CALLSIGN = 'K6FTP'
HOURS = 24
OUTPUT_DIR = '/home/wspr-zero/public_html/map'
wspr_data_file = os.path.join(OUTPUT_DIR, 'wspr_data.json')
furthest_contact_file = os.path.join(OUTPUT_DIR, 'furthest_contact.json')

# Calculate the start and end dates
end_date = datetime.utcnow()
start_date = end_date - timedelta(hours=HOURS)
start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

# API Query URL
query_url = f'https://wspr.live/wspr_downloader.php?start={start_date_str}&end={end_date_str}&tx_sign={CALLSIGN}&rx_sign=%&format=JSON'

print(f'Query URL: {query_url}')

# Fetch the data
response = requests.get(query_url)
if response.status_code == 200:
    if response.text.strip():
        try:
            data = response.json()
            if data:
                with open(wspr_data_file, 'w') as f:
                    json.dump(data, f, indent=4)
                print(f'Successfully downloaded WSPR data to {wspr_data_file}')

                # Determine the furthest contact from the data
                furthest_spot = max(data['data'], key=lambda x: float(x['distance']), default=None)

                # Read existing furthest contact data if available
                furthest_contact_data = {}
                if os.path.exists(furthest_contact_file):
                    try:
                        with open(furthest_contact_file, 'r') as f:
                            furthest_contact_data = json.load(f)
                    except json.JSONDecodeError:
                        print('Error decoding existing furthest contact JSON file.')

                # Compare and update furthest contact data if the new spot is further
                if furthest_spot:
                    new_distance = float(furthest_spot['distance'])
                    existing_distance = float(furthest_contact_data.get('distance', 0))

                    if new_distance > existing_distance:
                        furthest_contact_data = {
                            'tx_sign': furthest_spot['tx_sign'],
                            'rx_sign': furthest_spot['rx_sign'],
                            'distance': new_distance,
                            'time': furthest_spot['time'],
                            'tx_lat': furthest_spot['tx_lat'],
                            'tx_lon': furthest_spot['tx_lon'],
                            'rx_lat': furthest_spot['rx_lat'],
                            'rx_lon': furthest_spot['rx_lon']
                        }

                        with open(furthest_contact_file, 'w') as f:
                            json.dump(furthest_contact_data, f, indent=4)
                        print(f'Updated furthest contact data in {furthest_contact_file}')
                    else:
                        print('No new furthest contact found.')
                else:
                    print('No valid spots found in the data.')
            else:
                print('No data available for the given time range.')
        except json.JSONDecodeError:
            print('Error decoding JSON response.')
            print(f'Response content: {response.text}')
    else:
        print('No data returned from the server.')
else:
    print(f'Error fetching data: HTTP {response.status_code}')
    print(f'Response content: {response.text}')
