import requests
import json
import os
from datetime import datetime, timedelta

# Configurable Parameters
CALLSIGN = 'K6FTP'  # Callsign to search for
HOURS = 48           # Past N hours to retrieve
OUTPUT_DIR = '/home/wspr-zero/public_html/map'  # Directory to store data

# Calculate the start and end dates and include the time
end_date = datetime.utcnow()
start_date = end_date - timedelta(hours=HOURS)
start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')  # Include time in the format
end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')      # Include time in the format

# API Query URL
query_url = f'https://wspr.live/wspr_downloader.php?start={start_date_str}&end={end_date_str}&tx_sign={CALLSIGN}&rx_sign=%&format=JSON'

print(f'Query URL: {query_url}')  # Print the query URL used

# Fetch the data
response = requests.get(query_url)
if response.status_code == 200:
    if response.text.strip():
        try:
            data = response.json()
            # Write data to file if the data is not empty
            if data:
                output_file = os.path.join(OUTPUT_DIR, 'wspr_data.json')
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=4)
                print(f'Successfully downloaded WSPR data to {output_file}')
            else:
                print('No data available for the given time range.')
        except json.JSONDecodeError:
            print('Error decoding JSON response.')
            print(f'Response content: {response.text}')  # Print the response text for debugging
    else:
        print('No data returned from the server.')
else:
    print(f'Error fetching data: HTTP {response.status_code}')
    print(f'Response content: {response.text}')  # Print the response text for debugging
