<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WSPR-zero Activity Map</title>
    <link rel="stylesheet" href="styles.css">
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyB1ighfZ4owP2tr2WlXaEBEqbcDw7JR4U4&callback=initMap" async defer></script>
    <script>
        let wsprData = [];
        let furthestTxContactData = { distance: 0 };
        let furthestRxContactData = { distance: 0 };

        async function loadWSPRData() {
            const response = await fetch('wspr_data_tx.json');
            const data = await response.json();
            wsprData = data.data;

            try {
                const furthestResponse = await fetch('furthest_contact.json');
                if (furthestResponse.ok) {
                    const furthestData = await furthestResponse.json();
                    furthestTxContactData = furthestData.TX;
                    furthestRxContactData = furthestData.RX;
                }
            } catch (error) {
                console.error("Error loading furthest contact data:", error);
            }
        }

        function getRandomColor() {
            const letters = '0123456789ABCDEF';
            let color = '#';
            for (let i = 0; i < 6; i++) {
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

        function frequencyToWavelength(frequencyHz) {
            const speedOfLight = 299792458; // meters per second
            const wavelengthMeters = speedOfLight / frequencyHz;
            return Math.round(wavelengthMeters);
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
            } else {
                const overlay = document.getElementById('overlay');
                overlay.style.display = 'none';
            }

            const mapOptions = {
                mapTypeId: google.maps.MapTypeId.TERRAIN,
                center: { lat: 36.7783, lng: -119.4179 },
                zoom: 6
            };
            const map = new google.maps.Map(document.getElementById("map"), mapOptions);

            if (numberOfSpots > 0) {
                const firstSpot = filteredData[0];
                let txLat, txLon;

                if (firstSpot.tx_loc === "DM04bk") {
                    txLat = 34.4208485;
                    txLon = -119.7023207;
                } else {
                    txLat = parseFloat(firstSpot.tx_lat);
                    txLon = parseFloat(firstSpot.tx_lon);
                }

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
                            url: 'red-dot.png',
                            scaledSize: new google.maps.Size(25, 25)
                        },
                        title: `Receiver: ${spot.rx_sign}`
                    });

                    const wavelength = frequencyToWavelength(spot.frequency);

                    const infowindow = new google.maps.InfoWindow({
                        content: `<div class="infowindow-content">
                                      Receiver: <a href="https://www.qrz.com/db/${spot.rx_sign}" target="_blank">${spot.rx_sign}</a><br>
                                      Transmitter: <a href="https://www.qrz.com/db/${spot.tx_sign}" target="_blank">${spot.tx_sign}</a><br>
                                      Band: ${wavelength} meters
                                  </div>`,
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
            }

            // Always display furthest contact details from furthest_contact.json
            const summaryDiv = document.getElementById('summary');
            const distanceTxMiles = Math.round(furthestTxContactData.distance * 0.621371); // Convert km to miles
            const distanceRxMiles = Math.round(furthestRxContactData.distance * 0.621371); // Convert km to miles

            // Check for most recent spot
            const mostRecentSpot = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null;
            const mostRecentDistanceMiles = mostRecentSpot ? Math.round(mostRecentSpot.distance * 0.621371) : 0; // Convert km to miles
            const mostRecentWavelength = mostRecentSpot ? frequencyToWavelength(mostRecentSpot.frequency) : null;

            const furthestTxWavelength = frequencyToWavelength(furthestTxContactData.frequency);
            const furthestRxWavelength = frequencyToWavelength(furthestRxContactData.frequency);
            let timeDisplay = minutes < 60 ? `${minutes} Minutes` : `${Math.round(minutes / 60)} Hours`;

            summaryDiv.innerHTML = `<h2 id="title">K6FTP WSPR Activity over the Past ${timeDisplay} - ${numberOfSpots} spots</h2>
            <table>
                <tr>
                    <td><strong>Furthest TX Contact:</strong></td>
                    <td>${distanceTxMiles} miles from <a href="https://www.qrz.com/db/${furthestTxContactData.tx_sign}" target="_blank">${furthestTxContactData.tx_sign}</a> to <a href="https://www.qrz.com/db/${furthestTxContactData.rx_sign}" target="_blank">${furthestTxContactData.rx_sign}</a> on ${convertToPST(furthestTxContactData.time)} on ${furthestTxWavelength}m</td>
                </tr>
                <tr>
                    <td><strong>Furthest RX Contact:</strong></td>
                    <td>${distanceRxMiles} miles from <a href="https://www.qrz.com/db/${furthestRxContactData.tx_sign}" target="_blank">${furthestRxContactData.tx_sign}</a> to <a href="https://www.qrz.com/db/${furthestRxContactData.rx_sign}" target="_blank">${furthestRxContactData.rx_sign}</a> on ${convertToPST(furthestRxContactData.time)} on ${furthestRxWavelength}m</td>
                </tr>
                ${mostRecentSpot ? `
                <tr>
                    <td><strong>Most Recent Contact:</strong></td>
                    <td>${mostRecentDistanceMiles} miles from <a href="https://www.qrz.com/db/${mostRecentSpot.tx_sign}" target="_blank">${mostRecentSpot.tx_sign}</a> to <a href="https://www.qrz.com/db/${mostRecentSpot.rx_sign}" target="_blank">${mostRecentSpot.rx_sign}</a> on ${convertToPST(mostRecentSpot.time)} on ${mostRecentWavelength}m</td>
                </tr>` : ''}
            </table>`;
        }

        window.onload = () => initMap(12);
    </script>
</head>
<body>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-QT3J6BZ7EK"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-QT3J6BZ7EK');
</script>
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
