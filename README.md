# Gogoro_Line_Bot
Line chatbot to find nearest Gogoro GoStation, calculating ETA and distance with HERE Location Services.

## Basic concept

![](https://i.imgur.com/iN1CYvq.png)

Utilizing HERE Location Services API (together with LINE messaging API) to search the nearest Gogoro battery station.

* Geofencing – create the service boundary of battery stations.
* Custom Location – manage the station data on HERE cloud.
* Geofencing - Check the availability of GoStation.
* Isoline routing – define the reachable area of GoStations.
* Matrix routing – find the nearest GoStation.
* Route calculation – get the ETA.


## Enterprise scenario

    1. Use location of battery exchange station and Isoline Routing to generate the boundary of maximum service coverage of each station. It’s more realistic than circular search.
    1. Use the result of 1 to upload to Geofencing Extension/Custom Location Extension.

## End user scenario:

    1. Input the starting point, Reverse Geocoding it to get the street name/address (for user friendly), and use Geofencing Extension to search for nearby stations.
    2. Perform Matrix Routing with nearby stations (up to 100 stations) to find the nearest battery station.
    3. Perform Route Calculation to the nearest station, output ETA, distance and route instructions.
