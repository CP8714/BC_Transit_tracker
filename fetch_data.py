import requests
from google.transit import gtfs_realtime_pb2
import json
from datetime import datetime
import pandas as pd
import zipfile
import io

def fetch():
    url = "https://bct.tmix.se/gtfs-realtime/vehicleupdates.pb?operatorIds=48"
    static_url = "https://bct.tmix.se/Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds=48"
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    static_response = requests.get(static_url)
    static_response.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(static_response.content))

    trips_df = pd.read_csv(z.open("trips.txt"))
    trips_df.to_csv("data/trips.csv", index=False)

    stops_df = pd.read_csv(z.open("stops.txt"))
    stops_df.to_csv("data/stops.csv", index=False)

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    buses = []
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            buses.append({
                "id": entity.vehicle.vehicle.id,
                "lat": entity.vehicle.position.latitude,
                "lon": entity.vehicle.position.longitude,
                "speed": entity.vehicle.position.speed,
                "route": entity.vehicle.trip.route_id,
                "capacity": entity.vehicle.occupancy_status,
                "trip_id": entity.vehicle.trip.trip_id,
                "timestamp": datetime.utcnow().isoformat()
            })

    # Save to file
    with open("data/buses.json", "w") as f:
        json.dump(buses, f, indent=2)


if __name__ == "__main__":
    fetch()
