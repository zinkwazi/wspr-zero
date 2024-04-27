<?php
$dataFile = 'pi_data.json';

// Function to get the real IP address of the client in case of proxies
function getRealIpAddr() {
    if (!empty($_SERVER['HTTP_CLIENT_IP'])) {
        // IP from share internet
        return $_SERVER['HTTP_CLIENT_IP'];
    } elseif (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        // IP passed from proxy
        return $_SERVER['HTTP_X_FORWARDED_FOR'];
    } else {
        // Standard IP address
        return $_SERVER['REMOTE_ADDR'];
    }
}

$visitorIP = getRealIpAddr();

if (isset($_GET['hn']) && isset($_GET['ip']) && isset($_GET['mac'])) {
    // Load existing data
    $existingData = json_decode(file_get_contents($dataFile), true);
    if (!is_array($existingData)) {
        $existingData = [];
    }

    // Key the data by MAC address for easy lookup and ensure only latest is stored
    $macAddress = $_GET['mac'];
    $existingData[$macAddress] = [
        'hostname' => $_GET['hn'],
        'ip' => $_GET['ip'],
        'mac' => $macAddress,
        'client_ip' => $visitorIP,
        'timestamp' => time()
    ];

    // Save updated data, formatted to make each entry on a new line
    file_put_contents($dataFile, json_encode($existingData, JSON_PRETTY_PRINT));
    echo "Data Received";
} else {
    $data = json_decode(file_get_contents($dataFile), true);
    echo "<!DOCTYPE html>";
    echo "<html lang='en'>";
    echo "<head>";
    echo "<meta charset='UTF-8'>";
    echo "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    echo "<title>WSPR-zero IP Information</title>";
    echo "<link href='https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap' rel='stylesheet'>";
    echo "<style>";
    echo "body { font-family: 'Roboto', sans-serif; padding: 20px; background-color: #f4f4f9; color: #333; text-align: center; }";
    echo "h1, h2 { color: #5a76a7; }";
    echo ".container { max-width: 800px; margin: 20px auto; background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }";
    echo "hr { border: 0; height: 2px; background: linear-gradient(to right, #f0f0f0, #8fa1c7, #f0f0f0); }";
    echo "p { line-height: 1.6; }";
    echo "footer { margin-top: 20px; font-size: 0.8em; color: #888; }";
    echo "a { color: #5a76a7; text-decoration: none; }";
    echo "a:hover { text-decoration: underline; }";
    echo "@media (max-width: 600px) { .container { width: 95%; padding: 10px; } }";
    echo "</style>";
    echo "</head>";
    echo "<body>";
    echo "<div class='container'>";
    echo "<h1>WSPR-zero IP Information</h1>";
    echo "<h2>Public IP: " . $visitorIP . "</h2>";
    echo "<hr>";

    // Sort data by timestamp descending
    usort($data, function($a, $b) {
        return $b['timestamp'] - $a['timestamp'];
    });

    // Display all recent entries from the same IP
    $found = false;
    date_default_timezone_set('America/Los_Angeles');  // Set the timezone to PST
    foreach ($data as $entry) {
        if ($entry['client_ip'] == $visitorIP) {
            echo "<p><strong>Last Check-In:</strong> " . date("g:i:s A, Y-m-d", $entry['timestamp']) . "</p>";
            echo "<p><strong>Hostname:</strong> " . $entry['hostname'] . "</p>";
            echo "<p><strong>Private IP:</strong> " . $entry['ip'] . "</p>";
            echo "<p><strong>MAC Address:</strong> " . $entry['mac'] . "</p><hr>";
            $found = true;
        }
    }

    if (!$found) {
        echo "<p>No data available for your IP address in the past 10 minutes.</p>";
    }

    echo "</div>";
    echo "<footer>";
    echo "WSPR-zero Project, " . date("Y") . " &bull; <a href='https://github.com/zinkwazi/wspr-zero'>GitHub Repository</a>";
    echo "</footer>";
    echo "</body>";
    echo "</html>";
}
?>
