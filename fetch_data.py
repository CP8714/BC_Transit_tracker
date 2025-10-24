import requests
from google.transit import gtfs_realtime_pb2
import json
from datetime import datetime
import pandas as pd
import zipfile
import io

def fetch():
    fleet_update_url = "https://bct.tmix.se/gtfs-realtime/vehicleupdates.pb?operatorIds=48"
    trip_update_url = "https://bct.tmix.se/gtfs-realtime/tripupdates.pb?operatorIds=48"
    static_url = "https://bct.tmix.se/Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds=48"
    fleet_update_response = requests.get(fleet_update_url, timeout=10)
    fleet_update_response.raise_for_status()

    trip_update_response = requests.get(trip_update_url, timeout=10)
    trip_update_response.raise_for_status()

    static_response = requests.get(static_url)
    static_response.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(static_response.content))

    trips_df = pd.read_csv(z.open("trips.txt"))
    trips_df.to_csv("data/trips.csv", index=False)

    stops_df = pd.read_csv(z.open("stops.txt"))
    stops_df.to_csv("data/stops.csv", index=False)

    routes_df = pd.read_csv(z.open("routes.txt"))
    routes_df.to_csv("data/routes.csv", index=False)

    fleet_feed = gtfs_realtime_pb2.FeedMessage()
    fleet_feed.ParseFromString(fleet_update_response.content)

    buses = []
    for entity in fleet_feed.entity:
        if entity.HasField("vehicle"):
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

    trip_feed = gtfs_realtime_pb2.FeedMessage()
    trip_feed.ParseFromString(trip_update_response.content)
    trips = []
    for entity in trip_feed.entity:
        trip_entity = entity.trip_update
        if len(trip_entity.stop_time_update) > 0:
            if trip_entity.stop_time_update[0].stop_sequence == 1:
                trips.append({
                    "trip_id": trip_entity.trip.trip_id,
                    "route_id": trip_entity.trip.route_id,
                    "start_time": trip_entity.trip.start_time,
                    "delay": trip_entity.stop_time_update[0].departure.delay
                })
            else:
                trips.append({
                    "trip_id": trip_entity.trip.trip_id,
                    "route_id": trip_entity.trip.route_id,
                    "start_time": trip_entity.trip.start_time,
                    "delay": trip_entity.stop_time_update[0].arrival.delay
                })

    # Save to trip_updates.json
    with open("data/trip_updates.json", "w") as f:
        json.dump(trips, f, indent=2)


if __name__ == "__main__":
    fetch()
