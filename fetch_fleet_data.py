import requests
from google.transit import gtfs_realtime_pb2
import json
from datetime import datetime

# Script used to download the vehicleupdates.pb file from BC Transit's website and save the data into bus_updates.json in the /data folder

def fetch():
    fleet_update_url = "https://bct.tmix.se/gtfs-realtime/vehicleupdates.pb?operatorIds=48"
    fleet_update_response = requests.get(fleet_update_url, timeout=10)
    fleet_update_response.raise_for_status()

    fleet_feed = gtfs_realtime_pb2.FeedMessage()
    fleet_feed.ParseFromString(fleet_update_response.content)

    buses = []
    for entity in fleet_feed.entity:
        if entity.HasField("vehicle"):
            # Download the vehicle's id as well as its current position, speed, route, capacity, trip, next stop, bearing 
            # along with the timestamp indicating when the data was received
            buses.append({
                "id": entity.vehicle.vehicle.id,
                "lat": entity.vehicle.position.latitude,
                "lon": entity.vehicle.position.longitude,
                "speed": entity.vehicle.position.speed,
                "route": entity.vehicle.trip.route_id,
                "capacity": entity.vehicle.occupancy_status,
                "trip_id": entity.vehicle.trip.trip_id,
                "stop_id": entity.vehicle.stop_id,
                "bearing": entity.vehicle.position.bearing,
                "timestamp": datetime.utcnow().isoformat()
            })

    # Save to bus_updates.json
    with open("data/bus_updates.json", "w") as f:
        json.dump(buses, f, indent=2)

if __name__ == "__main__":
    fetch()

