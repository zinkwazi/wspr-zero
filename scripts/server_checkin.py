import requests
import json
import time
from datetime import datetime

# Define the URL of the remote server
server_url = "https://wspr-zero.com/setup/dev-server-setup.php"
log_file = '/home/pi/wspr-zero/logs/setup-post.log'

# Function to read wspr-config.json
def read_wspr_config():
    with open('/home/pi/wspr-zero/wspr-config.json', 'r') as file:
        data = json.load(file)
    return data

# Function to write wspr-config.json
def write_wspr_config(existing_data, new_data):
    existing_data.update(new_data)
    with open('/home/pi/wspr-zero/wspr-config.json', 'w') as file:
        json.dump(existing_data, file, indent=4)

# Function to send data to the server
def send_data_to_server(data):
    try:
        headers = {'Content-Type': 'application/json'}
        log_message(f"Sending data to server: {json.dumps(data, indent=4)}")
        response = requests.post(server_url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_message(f"Exception occurred while sending data: {str(e)}")
        return None

# Function to log messages to a file
def log_message(message):
    with open(log_file, 'a') as file:
        file.write(message + '\n')
    with open(log_file, 'a') as file:
        file.write('-' * 50 + '\n')

# Main function
def main():
    wspr_config = read_wspr_config()
    wspr_config['setup_timestamp'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Send the full configuration to the server once
    server_response = send_data_to_server(wspr_config)

    if server_response:
        write_wspr_config(wspr_config, server_response)

    # Wait 5 seconds and then repeatedly request the config file 12 times without sending full config again
    for _ in range(12):
        server_response = send_data_to_server({'MAC_address': wspr_config['MAC_address']})
        if server_response:
            write_wspr_config(wspr_config, server_response)
        time.sleep(5)

if __name__ == "__main__":
    main()
