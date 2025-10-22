import requests
from google.transit import gtfs_realtime_pb2
import json
from datetime import datetime

def fetch():
    url = "https://bct.tmix.se/gtfs-realtime/vehicleupdates.pb?operatorIds=48"
    response = requests.get(url, timeout=10)
    response.raise_for_status()

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
                "timestamp": datetime.utcnow().isoformat()
            })

    # Save to file
    with open("data/buses.json", "w") as f:
        json.dump(buses, f, indent=2)

if __name__ == "__main__":
    fetch()
