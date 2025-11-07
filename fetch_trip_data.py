import requests
from google.transit import gtfs_realtime_pb2
import json

# Script used to download the tripupdates.pb file from BC Transit's website containing realtime data of all trips currently being run
# or will be run in the next 2 hours and save the data into trip_updates.json in the /data folder

def fetch():
    trip_update_url = "https://bct.tmix.se/gtfs-realtime/tripupdates.pb?operatorIds=48"
    trip_update_response = requests.get(trip_update_url, timeout=10)
    trip_update_response.raise_for_status()
  
    trip_feed = gtfs_realtime_pb2.FeedMessage()
    trip_feed.ParseFromString(trip_update_response.content)
  
    trips = []
    for entity in trip_feed.entity:
        trip_entity = entity.trip_update
        if len(trip_entity.stop_time_update) > 0:
            for stop in trip_entity.stop_time_update:
                if trip_entity.stop_time_update[0].stop_sequence == 1:
                    trips.append({
                        "trip_id": trip_entity.trip.trip_id,
                        "route_id": trip_entity.trip.route_id,
                        "start_time": trip_entity.trip.start_time,
                        "stop_id": stop.stop_id,
                        "delay": stop.departure.delay,
                        "stop_sequence": stop.stop_sequence,
                        "time": stop.arrival.time
                    })
                else:
                    trips.append({
                        "trip_id": trip_entity.trip.trip_id,
                        "route_id": trip_entity.trip.route_id,
                        "start_time": trip_entity.trip.start_time,
                        "stop_id": stop.stop_id,
                        "delay": stop.arrival.delay,
                        "stop_sequence": stop.stop_sequence,
                        "time": stop.arrival.time
                    })

    # Save to trip_updates.json
    with open("data/trip_updates.json", "w") as f:
        json.dump(trips, f, indent=2)


if __name__ == "__main__":
    fetch()
