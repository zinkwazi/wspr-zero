<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WSPR-zero Activity Map</title>
    <style>
        html, body {
            height: 100%; /* Ensure the page uses full height */
            margin: 0;
            padding: 0;
        }
        body {
            display: flex; /* Make the body a flex container */
            flex-direction: column; /* Arrange child elements in a column */
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        #header {
            background-color: #ffffff; /* White header background */
            padding: 20px;
            text-align: left; /* Left-align header content */
            color: #333; /* Dark text color */
            display: flex; /* Flex container to align items horizontally */
            justify-content: space-between; /* Space out the logo and links */
            align-items: center; /* Vertically align items in the center */
        }
        #header a {
            text-decoration: none; /* Remove underline from logo link */
            color: inherit; /* Inherit color from parent */
        }
        #header img {
            width: 260px; /* Increased logo size by 25% */
            vertical-align: middle; /* Vertically align logo */
        }
        #header-links {
            display: flex;
            gap: 10px; /* Space between links */
        }
        .header-link {
            padding: 5px 10px;
            background-color: #e0e0e0; /* Light grey background */
            color: #333; /* Darker text color */
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            text-align: center;
            cursor: pointer;
        }
        .header-link:hover {
            background-color: #d0d0d0; /* Slightly darker grey on hover */
        }
        #footer {
            background-color: #343a40; /* Dark footer background */
            padding: 10px;
            text-align: center;
            color: #fff; /* White text color */
            flex-shrink: 0; /* Prevent the footer from shrinking */
        }
        #map-container {
            flex: 1; /* Allow the map container to grow and shrink */
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%; /* Map width scaled to 100% for mobile */
            height: 100%; /* Map height set to fill entire viewport */
            margin: 0 auto; /* Remove margins */
            border: 2px solid #333;
            position: relative; /* For positioning the overlay */
        }
        #map {
            width: 100%;
            height: 100%;
        }
        #overlay {
            position: absolute;
            top: 50%; /* Center vertically */
            left: 50%; /* Center horizontally */
            transform: translate(-50%, -50%); /* Adjust positioning */
            background-color: rgba(0, 0, 0, 0.6); /* Semi-transparent background */
            color: white;
            padding: 40px; /* Increase padding for larger overlay */
            border-radius: 10px;
            text-align: center;
            z-index: 1; /* Bring to the front */
            font-size: 1.5em; /* Increase font size for better visibility */
            width: 80%; /* Set overlay width to 80% */
        }
        #summary {
            text-align: center;
            font-size: 1.2em; /* Same font size for summary */
            margin: 20px auto;
            width: 90%;
        }
        #title {
            font-size: 1.2em; /* Same font size for title */
        }
    </style>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyB1ighfZ4owP2tr2WlXaEBEqbcDw7JR4U4&callback=initMap" async defer></script>
    <script>
        let wsprData = [];

        async function loadWSPRData() {
            const response = await fetch('wspr_data.json'); // Load the JSON file once
            const data = await response.json();
            wsprData = data.data; // Store the data in a global variable
        }

        function getRandomColor() {
            // Generate a random hex color
            const letters = '0123456789ABCDEF';
            let color = '#';
            for (let i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
            }
            return color;
        }

        function isMobileDevice() {
            return (typeof window.orientation !== "undefined") || (navigator.userAgent.indexOf('IEMobile') !== -1);
        }

        async function initMap(hours = 24) {
            await loadWSPRData(); // Ensure data is loaded before filtering
            const filteredData = wsprData.filter(spot => {
                const spotTime = new Date(spot.time);
                const cutoffTime = new Date(Date.now() - (hours * 60 * 60 * 1000));
                return spotTime >= cutoffTime;
            });

            // Check if there is any data
            if (filteredData.length === 0) {
                // If no data, display the overlay message
                const overlay = document.getElementById('overlay');
                overlay.style.display = 'block';

                // Initialize the map with a default center if no data is available
                const mapOptions = {
                    mapTypeId: google.maps.MapTypeId.TERRAIN, // Set map type
                    center: { lat: 36.7783, lng: -119.4179 }, // Default center (California)
                    zoom: 6 // Default zoom level
                };
                const map = new google.maps.Map(document.getElementById("map"), mapOptions);

                return;
            }

            // Determine the transmitter location based on `tx_loc`
            const firstSpot = filteredData[0];
            let txLat, txLon;

            if (firstSpot.tx_loc === "DM04bk") {
                // Use hardcoded coordinates
                txLat = 34.42075;
                txLon = -119.70222;
            } else {
                // Use coordinates from JSON file
                txLat = parseFloat(firstSpot.tx_lat);
                txLon = parseFloat(firstSpot.tx_lon);
            }

            // Initialize the map centered on the transmitter
            const mapOptions = {
                mapTypeId: google.maps.MapTypeId.TERRAIN, // Set map type
                center: { lat: txLat, lng: txLon }, // Center on the transmitter location
                zoom: 6 // Default zoom level
            };
            const map = new google.maps.Map(document.getElementById("map"), mapOptions);

            // Initialize LatLngBounds for calculating the bounds
            const bounds = new google.maps.LatLngBounds();

            let maxDistance = 0;
            let furthestSpot = null;

            filteredData.forEach(spot => {
                const distance = parseFloat(spot.distance);
                const rxLat = parseFloat(spot.rx_lat);
                const rxLon = parseFloat(spot.rx_lon);

                if (distance > maxDistance) {
                    maxDistance = distance;
                    furthestSpot = spot;
                }

                // Extend the bounds to include the transmitter and receiver
                bounds.extend(new google.maps.LatLng(txLat, txLon));
                bounds.extend(new google.maps.LatLng(rxLat, rxLon));
            });

            // Fit the map to the calculated bounds
            map.fitBounds(bounds);

            // If on a mobile device, increase zoom by 2 levels
            if (isMobileDevice()) {
                map.setZoom(map.getZoom() + 2);
            }

            filteredData.forEach(spot => {
                const rxLat = parseFloat(spot.rx_lat);
                const rxLon = parseFloat(spot.rx_lon);

                // Draw a line between transmitter and receiver
                const path = [
                    { lat: txLat, lng: txLon },
                    { lat: rxLat, lng: rxLon }
                ];
                const polyline = new google.maps.Polyline({
                    path: path,
                    geodesic: true,
                    strokeColor: getRandomColor(), // Randomized line color
                    strokeOpacity: 1.0,
                    strokeWeight: 1, // Thinner lines
                    map: map
                });

                // Add a standard Google Maps marker, scaled down
                const marker = new google.maps.Marker({
                    position: { lat: rxLat, lng: rxLon },
                    map: map,
                    icon: {
                        url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                        scaledSize: new google.maps.Size(15, 15) // Scale the standard marker
                    },
                    title: `Receiver: ${spot.rx_sign}`
                });

                // Add tooltip with receiver callsign on hover or click
                const infowindow = new google.maps.InfoWindow({
                    content: `Receiver: <a href="https://www.qrz.com/db/${spot.rx_sign}" target="_blank">${spot.rx_sign}</a>`,
                    disableAutoPan: true // Prevents the X from being selected automatically
                });
                marker.addListener('mouseover', () => {
                    infowindow.open(map, marker);
                });
                marker.addListener('mouseout', () => {
                    infowindow.close();
                });
                marker.addListener('click', () => {
                    infowindow.open(map, marker);
                });
            });

            // Show the summary for the furthest contact
            if (furthestSpot) {
                const summaryDiv = document.getElementById('summary');
                const distanceMiles = Math.round(furthestSpot.distance * 0.621371);
                summaryDiv.innerHTML = `<h1 id="title">WSPR-zero Activity over the Past ${hours} Hours</h1>
                <strong>Furthest Contact:</strong>
                    ${furthestSpot.tx_sign} to <a href="https://www.qrz.com/db/${furthestSpot.rx_sign}" target="_blank">${furthestSpot.rx_sign}</a>,
                    Distance: ${distanceMiles} miles / ${furthestSpot.distance} km`;
            }
        }

        // Load the map with the default 24-hour view
        window.onload = () => initMap(24);
    </script>
</head>
<body>
    <div id="header">
        <a href="/"><img id="logo" src="/WSPR-zero-logo-medium.png" alt="WSPR-zero Logo"></a>
        <div id="header-links">
            <a class="header-link" onclick="initMap(0.2)">12 Min</a>
            <a class="header-link" onclick="initMap(3)">3 Hours</a>
            <a class="header-link" onclick="initMap(24)">24 Hours</a>
            <a class="header-link" onclick="initMap(48)">2 Days</a>
        </div>
    </div>
    <div id="map-container">
        <div id="map"></div>
        <div id="overlay" style="display: none;">The transmitting callsign is offline and hopefully hiking to a remote location or braiding a new wire dipole antenna.</div>
    </div>
    <div id="summary"></div>
    <div id="footer">
        <p>2024 WSPR-zero Project</p>
    </div>
</body>
</html>
