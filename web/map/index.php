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
        table {
            width: 80%;
            margin: 20px auto;
            border-collapse: collapse;
            background-color: transparent;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        td:first-child {
            font-weight: bold;
            background-color: #f9f9f9;
        }
        tr:last-child td {
            border-bottom: none;
        }
    </style>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyB1ighfZ4owP2tr2WlXaEBEqbcDw7JR4U4&callback=initMap" async defer></script>
    <script>
        let wsprDataTx = [];
        let wsprDataRx = [];
        let furthestTxContactData = { distance: 0 };
        let furthestRxContactData = { distance: 0 };
        const excludedCallsign = 'K6FTP'; // Change this to the callsign you want to exclude

        async function loadWSPRData() {
            const responseTx = await fetch('wspr_data_tx.json');
            const dataTx = await responseTx.json();
            wsprDataTx = dataTx.data;

            const responseRx = await fetch('wspr_data_rx.json');
            const dataRx = await responseRx.json();
            wsprDataRx = dataRx.data;

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

            const filteredDataTx = wsprDataTx.filter(spot => {
                const spotTime = new Date(spot.time).getTime();
                return spotTime >= cutoffTime.getTime();
            });

            const filteredDataRx = wsprDataRx.filter(spot => {
                const spotTime = new Date(spot.time).getTime();
                return spotTime >= cutoffTime.getTime();
            });

            const numberOfSpotsTx = filteredDataTx.length;
            const numberOfSpotsRx = filteredDataRx.length;

            if (numberOfSpotsTx === 0 && numberOfSpotsRx === 0) {
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

            const firstSpotTx = filteredDataTx[0];
            let txLat, txLon;

            if (firstSpotTx.tx_loc === "DM04bk") {
                txLat = 34.4208485;
                txLon = -119.7023207;
            } else {
                txLat = parseFloat(firstSpotTx.tx_lat);
                txLon = parseFloat(firstSpotTx.tx_lon);
            }

            const mapOptions = {
                mapTypeId: google.maps.MapTypeId.TERRAIN,
                center: { lat: txLat, lng: txLon },
                zoom: 6
            };
            const map = new google.maps.Map(document.getElementById("map"), mapOptions);

            const bounds = new google.maps.LatLngBounds();

            filteredDataTx.forEach(spot => {
                const rxLat = parseFloat(spot.rx_lat);
                const rxLon = parseFloat(spot.rx_lon);

                bounds.extend(new google.maps.LatLng(txLat, txLon));
                bounds.extend(new google.maps.LatLng(rxLat, rxLon));
            });

            filteredDataRx.forEach(spot => {
                const txLat = parseFloat(spot.tx_lat);
                const txLon = parseFloat(spot.tx_lon);

                bounds.extend(new google.maps.LatLng(txLat, txLon));
                bounds.extend(new google.maps.LatLng(spot.rx_lat, spot.rx_lon));
            });

            map.fitBounds(bounds);

            if (isMobileDevice()) {
                map.setZoom(map.getZoom() + 2);
            }

            filteredDataTx.forEach(spot => {
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

                if (spot.rx_loc !== "DM04bk") {
                    const marker = new google.maps.Marker({
                        position: { lat: rxLat, lng: rxLon },
                        map: map,
                        icon: {
                            url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                            scaledSize: new google.maps.Size(20, 20)
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
                }
            });

            filteredDataRx.forEach(spot => {
                let txLat, txLon;

                if (spot.rx_loc === "DM04bk") {
                    spot.rx_lat = 34.4208485;
                    spot.rx_lon = -119.7023207;
                }

                if (spot.tx_loc === "DM04bk") {
                    txLat = 34.4208485;
                    txLon = -119.7023207;
                } else {
                    txLat = parseFloat(spot.tx_lat);
                    txLon = parseFloat(spot.tx_lon);
                }

                const path = [
                    { lat: txLat, lng: txLon },
                    { lat: spot.rx_lat, lng: spot.rx_lon }
                ];
                const polyline = new google.maps.Polyline({
                    path: path,
                    geodesic: true,
                    strokeColor: getRandomColor(),
                    strokeOpacity: 1.0,
                    strokeWeight: 1,
                    map: map
                });

                if (spot.tx_sign !== excludedCallsign) {
                    const marker = new google.maps.Marker({
                        position: { lat: txLat, lng: txLon },
                        map: map,
                        icon: {
                            url: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
                            scaledSize: new google.maps.Size(20, 20)
                        },
                        title: `Transmitter: ${spot.tx_sign}`
                    });

                    const infowindow = new google.maps.InfoWindow({
                        content: `Transmitter: <a href="https://www.qrz.com/db/${spot.tx_sign}" target="_blank">${spot.tx_sign}</a>`,
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
                }
            });

            // Always display furthest contact details from furthest_contact.json
            const summaryDiv = document.getElementById('summary');
            const distanceTxMiles = Math.round(furthestTxContactData.distance * 0.621371); // Convert km to miles
            const distanceRxMiles = Math.round(furthestRxContactData.distance * 0.621371); // Convert km to miles

            const mostRecentSpotTx = filteredDataTx[filteredDataTx.length - 1];
            const mostRecentSpotRx = filteredDataRx[filteredDataRx.length - 1];

            let mostRecentSpot;
            if (new Date(mostRecentSpotTx.time) > new Date(mostRecentSpotRx.time)) {
                mostRecentSpot = mostRecentSpotTx;
            } else {
                mostRecentSpot = mostRecentSpotRx;
            }

            const mostRecentDistanceMiles = Math.round(mostRecentSpot.distance * 0.621371); // Convert km to miles
            let timeDisplay = minutes < 60 ? `${minutes} Minutes` : `${Math.round(minutes / 60)} Hours`;

            const mostRecentType = mostRecentSpot === mostRecentSpotTx ? "TX" : "RX";
            const mostRecentSign = mostRecentType === "TX" ? mostRecentSpot.tx_sign : mostRecentSpot.rx_sign;

            summaryDiv.innerHTML = `<h2 id="title">WSPR-zero Activity over the Past ${timeDisplay} - ${numberOfSpotsTx + numberOfSpotsRx} spots</h2>

<table style="table-layout: auto; width: auto; margin: 20px auto; border-collapse: collapse; background-color: transparent; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);">
    <tr>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd; font-weight: bold; background-color: #f9f9f9;"><strong>Furthest TX Contact:</strong></td>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd;">${distanceTxMiles} miles from <a href="https://www.qrz.com/db/${furthestTxContactData.tx_sign}" target="_blank">${furthestTxContactData.tx_sign}</a> to <a href="https://www.qrz.com/db/${furthestTxContactData.rx_sign}" target="_blank">${furthestTxContactData.rx_sign}</a> on ${convertToPST(furthestTxContactData.time)}</td>
    </tr>
    <tr>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd; font-weight: bold; background-color: #f9f9f9;"><strong>Furthest RX Contact:</strong></td>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd;">${distanceRxMiles} miles from <a href="https://www.qrz.com/db/${furthestRxContactData.tx_sign}" target="_blank">${furthestRxContactData.tx_sign}</a> to <a href="https://www.qrz.com/db/${furthestRxContactData.rx_sign}" target="_blank">${furthestRxContactData.rx_sign}</a> on ${convertToPST(furthestRxContactData.time)}</td>
    </tr>
    <tr>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd; font-weight: bold; background-color: #f9f9f9;"><strong>Most Recent Contact:</strong></td>
        <td style="padding: 8px 10px; text-align: left; border-bottom: 1px solid #ddd;">${mostRecentDistanceMiles} miles from <a href="https://www.qrz.com/db/${mostRecentSpot.tx_sign}" target="_blank">${mostRecentSpot.tx_sign}</a> to <a href="https://www.qrz.com/db/${mostRecentSpot.rx_sign}" target="_blank">${mostRecentSpot.rx_sign}</a> on ${convertToPST(mostRecentSpot.time)} (${mostRecentType})</td>
    </tr>
</table>`;
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
