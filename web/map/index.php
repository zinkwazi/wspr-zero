<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WSPR-zero Activity Map</title>
    <style>
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
        }
        body {
            display: flex;
            flex-direction: column;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        #header {
            background-color: #ffffff;
            padding: 20px;
            text-align: left;
            color: #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        #header a {
            text-decoration: none;
            color: inherit;
        }
        #header img {
            width: 260px;
            vertical-align: middle;
        }
        #header-links {
            display: flex;
            gap: 10px;
        }
        .header-link {
            padding: 5px 10px;
            background-color: #e0e0e0;
            color: #333;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            text-align: center;
            cursor: pointer;
        }
        .header-link:hover {
            background-color: #d0d0d0;
        }
        #footer {
            background-color: #343a40;
            padding: 10px;
            text-align: center;
            color: #fff;
            flex-shrink: 0;
        }
        #map-container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            height: 100%;
            margin: 0 auto;
            border: 2px solid #333;
            position: relative;
        }
        #map {
            width: 100%;
            height: 100%;
        }
        #overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background-color: rgba(0, 0, 0, 0.6);
            color: white;
            padding: 40px;
            border-radius: 10px;
            text-align: center;
            z-index: 1;
            font-size: 1.5em;
            width: 80%;
        }
        #summary {
            text-align: center;
            font-size: 1em;
            margin: 20px auto;
	    width: 90%;
            line-height: 1.8;
        }
        #title {
            font-size: 1.2em;
        }
    </style>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyB1ighfZ4owP2tr2WlXaEBEqbcDw7JR4U4&callback=initMap" async defer></script>
    <script>
        let wsprData = [];
        let furthestContactData = { distance: 0 };

        async function loadWSPRData() {
            const response = await fetch('wspr_data_tx.json');
            const data = await response.json();
            wsprData = data.data;

            try {
                const furthestResponse = await fetch('furthest_contact.json');
                if (furthestResponse.ok) {
                    furthestContactData = await furthestResponse.json();
                }
            } catch (error) {
                console.error("Error loading furthest contact data:", error);
            }
        }

function getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        // Allow colors up to 'B' for more variety but avoid very light colors
        let index = Math.floor(Math.random() * 15);
        color += letters[index];
    }
    return color;
}

        function isMobileDevice() {
            return (typeof window.orientation !== "undefined") || (navigator.userAgent.indexOf('IEMobile') !== -1);
        }

        function convertToPST(dateString) {
            const utcDate = new Date(dateString + 'Z'); // 'Z' indicates UTC time
            return new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', dateStyle: 'full', timeStyle: 'long' }).format(utcDate);
        }

        async function initMap(minutes = 12) {
            await loadWSPRData();
            const currentTime = Date.now();
            const cutoffTime = new Date(currentTime - (minutes * 60 * 1000));

            const filteredData = wsprData.filter(spot => {
                const spotTime = new Date(spot.time).getTime();
                return spotTime >= cutoffTime.getTime();
            });

            const numberOfSpots = filteredData.length;

            if (numberOfSpots === 0) {
                const overlay = document.getElementById('overlay');
                overlay.style.display = 'block';
                const mapOptions = {
                    mapTypeId: google.maps.MapTypeId.TERRAIN,
                    center: { lat: 36.7783, lng: -119.4179 },
                    zoom: 6
                };
                const map = new google.maps.Map(document.getElementById("map"), mapOptions);
                return;
            }

            const firstSpot = filteredData[0];
            let txLat, txLon;

            if (firstSpot.tx_loc === "DM04bk") {
                txLat = 34.4208485;
                txLon = -119.7023207;
            } else {
                txLat = parseFloat(firstSpot.tx_lat);
                txLon = parseFloat(firstSpot.tx_lon);
            }

            const mapOptions = {
                mapTypeId: google.maps.MapTypeId.TERRAIN,
                center: { lat: txLat, lng: txLon },
                zoom: 6
            };
            const map = new google.maps.Map(document.getElementById("map"), mapOptions);

            const bounds = new google.maps.LatLngBounds();

            filteredData.forEach(spot => {
                const rxLat = parseFloat(spot.rx_lat);
                const rxLon = parseFloat(spot.rx_lon);

                bounds.extend(new google.maps.LatLng(txLat, txLon));
                bounds.extend(new google.maps.LatLng(rxLat, rxLon));
            });

            map.fitBounds(bounds);

            if (isMobileDevice()) {
                map.setZoom(map.getZoom() + 2);
            }

            filteredData.forEach(spot => {
                const rxLat = parseFloat(spot.rx_lat);
                const rxLon = parseFloat(spot.rx_lon);

                const path = [
                    { lat: txLat, lng: txLon },
                    { lat: rxLat, lng: rxLon }
                ];
                const polyline = new google.maps.Polyline({
                    path: path,
                    geodesic: true,
                    strokeColor: getRandomColor(),
                    strokeOpacity: 1.0,
                    strokeWeight: 1,
                    map: map
                });

                const marker = new google.maps.Marker({
                    position: { lat: rxLat, lng: rxLon },
                    map: map,
                    icon: {
                        url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                        scaledSize: new google.maps.Size(15, 15)
                    },
                    title: `Receiver: ${spot.rx_sign}`
                });

                const infowindow = new google.maps.InfoWindow({
                    content: `Receiver: <a href="https://www.qrz.com/db/${spot.rx_sign}" target="_blank">${spot.rx_sign}</a>`,
                    disableAutoPan: true
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

            // Always display furthest contact details from furthest_contact.json
            const summaryDiv = document.getElementById('summary');
            const distanceMiles = Math.round(furthestContactData.distance * 0.621371); // Convert km to miles
            const mostRecentSpot = filteredData[filteredData.length - 1];
            const mostRecentDistanceMiles = Math.round(mostRecentSpot.distance * 0.621371); // Convert km to miles
            let timeDisplay = minutes < 60 ? `${minutes} Minutes` : `${Math.round(minutes / 60)} Hours`;
            summaryDiv.innerHTML = `<h2 id="title">WSPR-zero Activity over the Past ${timeDisplay} - ${numberOfSpots} spots</h2>
            <strong>Furthest Contact:</strong>
                ${distanceMiles} miles from <a href="https://www.qrz.com/db/${furthestContactData.tx_sign}" target="_blank">${furthestContactData.tx_sign}</a> to <a href="https://www.qrz.com/db/${furthestContactData.rx_sign}" target="_blank">${furthestContactData.rx_sign}</a> on ${convertToPST(furthestContactData.time)}<br>
            <strong>Most Recent Contact:</strong>
                ${mostRecentDistanceMiles} miles from <a href="https://www.qrz.com/db/${mostRecentSpot.tx_sign}" target="_blank">${mostRecentSpot.tx_sign}</a> to <a href="https://www.qrz.com/db/${mostRecentSpot.rx_sign}" target="_blank">${mostRecentSpot.rx_sign}</a> on ${convertToPST(mostRecentSpot.time)}`;
        }

        window.onload = () => initMap(12);
    </script>
</head>
<body>
    <div id="header">
        <a href="/"><img id="logo" src="/WSPR-zero-logo-medium.png" alt="WSPR-zero Logo"></a>
        <div id="header-links">
            <a class="header-link" onclick="initMap(12)">12 Min</a>
            <a class="header-link" onclick="initMap(180)">3 Hours</a>
            <a class="header-link" onclick="initMap(1440)">24 Hours</a>
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
