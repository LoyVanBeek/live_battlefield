/* Numbered location pin shared by the GM locations map and the player quest map.
   Requires leaflet.js to be loaded first. */
(function () {
    function locationPinIcon(number) {
        return L.divIcon({
            className: "location-pin-wrap",
            html:
                '<span class="location-pin"><span class="location-pin-number">' +
                number +
                "</span></span>",
            iconSize: [30, 36],
            iconAnchor: [15, 36],
        });
    }

    window.locationPinIcon = locationPinIcon;
})();
