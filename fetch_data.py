import requests
from google.transit import gtfs_realtime_pb2
import json
from datetime import datetime
import pandas as pd
import zipfile
import io

# Script used to download the vehicleupdates.pb and tripupdates.pb files from BC Transit's website 
# respectfully containing realtime data of all BC Transit buses (excluding Handydart) 
# currently running and trips currently being run or will be run in the next 2 hours in Victoria, BC. 
# This data is then saved as json files in the /data folder. Static data containing information
# such as trip and route information is also downloaded and stored in csv files in the /data folder.
# Due to the large memory used when downloading the static data, this script is only used by the GitHub Workflow.
# The website instead runs with fetch_fleet_data.py and fetch_trip_data.py and retrieves the static data
# in /data from the last run of the GitHub Workflow

def fetch():
    # The urls from which the realtime and static data is dowanloaded
    fleet_update_url = "https://bct.tmix.se/gtfs-realtime/vehicleupdates.pb?operatorIds=48"
    trip_update_url = "https://bct.tmix.se/gtfs-realtime/tripupdates.pb?operatorIds=48"
    static_url = "https://bct.tmix.se/Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds=48"
    
    # --- Section of code where the static data is read and stored in csv files ---
    # Downloading the zip file containing the static data
    static_response = requests.get(static_url)
    static_response.raise_for_status()
    
    # Opening the zip file containing all the static data files
    z = zipfile.ZipFile(io.BytesIO(static_response.content))

    # Reading the trips.txt file containing info on all trips and saving it to trips.csv
    trips_df = pd.read_csv(z.open("trips.txt"))
    trips_df.to_csv("data/trips.csv", index=False)

    # Reading the trips.txt file containing info on all stops and saving it to stops.csv
    stops_df = pd.read_csv(z.open("stops.txt"))
    stops_df.to_csv("data/stops.csv", index=False)

    # Reading the trips.txt file containing info on all routes and saving it to routes.csv
    routes_df = pd.read_csv(z.open("routes.txt"))
    routes_df.to_csv("data/routes.csv", index=False)


    # Reading the calendar_dates.txt file containing all calendar dates and saving it to calendar_dates.csv
    calendar_df = pd.read_csv(z.open("calendar_dates.txt"))
    calendar_df.to_csv("data/calendar_dates.csv", index=False)


    

    # Reading stop_times.txt in chunks and saving to multiple CSVs
    stop_times_chunksize = 100000  # rows per file
    stop_times_file_base = "data/stop_times_part"

    # Use iterator with chunksize
    stop_times_iter = pd.read_csv(z.open("stop_times.txt"), chunksize=stop_times_chunksize)

    for i, chunk in enumerate(stop_times_iter):
        chunk.to_csv(f"{stop_times_file_base}_{i}.csv", index=False)

    # # Reading the stop_times.txt file containing info on scheduled arrival times for all trips for every stop served and saving it to stop_times.csv
    # stop_times_df = pd.read_csv(z.open("stop_times.txt"))
    # stop_times_df.to_csv("data/stop_times.csv", index=False)



    
    

    # --- Section of code where the realtime data related to each specific bus currently running is read and saved ---
    # Reading the realtime bus data
    fleet_update_response = requests.get(fleet_update_url, timeout=10)
    fleet_update_response.raise_for_status()
    fleet_feed = gtfs_realtime_pb2.FeedMessage()
    fleet_feed.ParseFromString(fleet_update_response.content)

    # Saving the data of every bus currently running into a dictionary and adding it to the buses
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
            
    # Overwriting the content of bus_updates.json with buses
    with open("data/bus_updates.json", "w") as f:
        json.dump(buses, f, indent=2)
        

    # --- Section of code where the realtime data related to each specific trip currently being run or scheduled to run in the next 2 hours is read and saved ---
    # Reading the realtime bus data
    trip_update_response = requests.get(trip_update_url, timeout=10)
    trip_update_response.raise_for_status()
    trip_feed = gtfs_realtime_pb2.FeedMessage()
    trip_feed.ParseFromString(trip_update_response.content)

    # Saving the data of every trip currently being run or scheduled to run in the next 2 hours currently running into a dictionary and adding it to the trips
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

    # Overwriting the content of bus_updates.json with trips
    with open("data/trip_updates.json", "w") as f:
        json.dump(trips, f, indent=2)


if __name__ == "__main__":
    fetch()
