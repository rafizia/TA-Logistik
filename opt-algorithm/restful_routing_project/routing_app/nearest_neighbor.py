from datetime import datetime, time, timedelta
import os
import requests
import polyline
from .logger_utils import get_logger

# OSRM public server
OSRM_BASE_URL = os.getenv('OSRM_BASE_URL', 'http://router.project-osrm.org')

logger = get_logger(__name__)


def _osrm_route_segment(origin_lat, origin_lon, dest_lat, dest_lon, with_polyline=False):
    overview = 'full' if with_polyline else 'false'
    # OSRM: koordinat dalam format lon,lat
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        f"?overview={overview}&geometries=polyline"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            result = {
                'duration': route['duration'],
                'distance': route['distance'],
            }
            if with_polyline:
                result['geometry'] = route.get('geometry', '')
            return result
        else:
            logger.warning(f"[_osrm_route_segment] OSRM code={data.get('code')}")
    except Exception as e:
        logger.warning(f"[_osrm_route_segment] Request gagal: {e}")
    return None

def nearest_neighbor_runner(bin_cluster_data, distances, times, distance_from_DC, duration_from_DC, ori_lat, ori_long):
    logger.info(f"[nearest_neighbor_runner] START - Processing {len(bin_cluster_data)} locations")
     
    NN_route_indexs, NN_unreachable_indexs, total_time, total_time_with_waiting, total_distance, location_dest_info = nearest_neighbor_vrptw(bin_cluster_data, distances, times, distance_from_DC, duration_from_DC)

    NN_route_loc_dest_ids = bin_cluster_data.iloc[NN_route_indexs]['loc_dest_id'].tolist()
    NN_unreachable_loc_dest_ids = bin_cluster_data.iloc[NN_unreachable_indexs]['loc_dest_id'].tolist()
    logger.info(f"[nearest_neighbor_runner] Route: {len(NN_route_loc_dest_ids)} reachable, {len(NN_unreachable_loc_dest_ids)} unreachable")
    logger.debug(f"[nearest_neighbor_runner] Reachable IDs: {NN_route_loc_dest_ids}")

    if (len(NN_unreachable_loc_dest_ids) == 0):
        logger.info("[nearest_neighbor_runner] All locations can be reached")
    else:
        logger.warning(f"[nearest_neighbor_runner] Unreachable locations: {NN_unreachable_loc_dest_ids}")

    dc_banten_coords = (ori_lat, ori_long)
    logger.info(f"[nearest_neighbor_runner] Fetching route coordinates")
    NN_all_coords, NN_directions_results = fetch_concatenate_routes(NN_route_indexs, bin_cluster_data, dc_banten_coords)
    
    logger.info(f"[nearest_neighbor_runner] COMPLETE - total_time={total_time}, total_distance={total_distance}m")
    return NN_all_coords, NN_directions_results, NN_route_loc_dest_ids, NN_unreachable_loc_dest_ids, total_time, total_time_with_waiting, total_distance, location_dest_info

def nearest_neighbor_vrptw(locations, distance_matrix, time_matrix, initial_distance, initial_duration):
    logger.info(f"[nearest_neighbor_vrptw] START - Processing {len(locations)} locations")
    location_dest_info = []

    num_locations = len(locations)
    unvisited = set(range(num_locations))   
    route = []   
    unreachable = []   
    total_time = timedelta(seconds=initial_duration)   
    total_time_waiting = total_time
    total_distance = initial_distance   
     
    start_time = time(8, 0)
    current_time = datetime.combine(datetime.today(), start_time)
    service_time = timedelta(minutes=locations.iloc[0]['service_time'])  # 15 minutes service time
    logger.info(f"[nearest_neighbor_vrptw] Starting at {current_time.strftime('%H:%M:%S')} from DC")
     

    first_location_index = 0   
    first_location = locations.iloc[first_location_index]

    route.append(first_location_index)
    unvisited.remove(first_location_index)
    current_time += timedelta(seconds=initial_duration)
    open_time = datetime.combine(datetime.today(), locations.iloc[first_location_index]['open_hour'])
    if current_time < open_time:
        waiting_duration = open_time - current_time
        total_time_waiting += waiting_duration
        current_time += waiting_duration
        print(f"Arrived early at {locations.iloc[first_location_index]['address']}. Waiting for {waiting_duration} until it opens at {open_time.strftime('%H:%M:%S')}")

    print(f"First stop: {first_location['address']} at {current_time.strftime('%H:%M:%S')}, travel time: {initial_duration/60} minutes, travel distance: {initial_distance} meters")
    location_dest_info.append({
        "loc_dest_id" : first_location['loc_dest_id'],
        "queue": 1,
        "eta": current_time.strftime('%H:%M:%S'),
        "travel_time" : initial_duration/60,
        "travel_distance" :initial_distance
    })
    # service time first location
    current_time += service_time
    total_time += service_time
    
    while unvisited:
        current_index = route[-1] if route else -1   
        next_index = None
        min_distance = float('inf')
        
        for loc_index in unvisited:
            travel_distance = distance_matrix[current_index][loc_index]
            travel_time_seconds = time_matrix[current_index][loc_index]
            travel_time = timedelta(seconds=travel_time_seconds)
            arrival_time = current_time + travel_time
            open_time = datetime.combine(datetime.today(), locations.iloc[loc_index]['open_hour'])
            close_time = datetime.combine(datetime.today(), locations.iloc[loc_index]['close_hour'])
            
            if arrival_time <= close_time and travel_distance < min_distance:
                if arrival_time < open_time:
                    waiting_duration = open_time - arrival_time
                    total_time_waiting += waiting_duration
                    arrival_time = open_time
                    print(f"Arrived early at {locations.iloc[loc_index]['address']}. Waiting for {waiting_duration} until it opens at {open_time.strftime('%H:%M:%S')}")
                    next_index = loc_index
                    min_time = arrival_time
                    min_travel_time = travel_time
                    min_distance = travel_distance
                if open_time <= arrival_time <= close_time:
                    next_index = loc_index
                    min_time = arrival_time
                    min_travel_time = travel_time
                    min_distance = travel_distance

        if next_index is None:
            unreachable.extend(unvisited)
            break

        total_time += min_travel_time
        total_time_waiting += min_travel_time
        total_distance += min_distance
        print(f"Next stop: {locations.iloc[next_index]['address']} at {min_time.strftime('%H:%M:%S')}, travel time: {min_travel_time}, travel distance: {min_distance} meters")
        location_dest_info.append({
            "loc_dest_id" : locations.iloc[next_index]['loc_dest_id'],
            "queue": len(location_dest_info) + 1,
            "eta": min_time.strftime('%H:%M:%S'),
            "travel_time" : min_travel_time.total_seconds() / 60,
            "travel_distance" :min_distance
        })

        current_time = min_time

        # service time each location
        current_time += timedelta(minutes=locations.iloc[next_index]['service_time']) 
        total_time += timedelta(minutes=locations.iloc[next_index]['service_time']) 
        
        route.append(next_index)
        unvisited.remove(next_index)
    
    logger.info(f"[nearest_neighbor_vrptw] Route: {route}")
    logger.info(f"[nearest_neighbor_vrptw] Total travel time: {total_time}")
    logger.info(f"[nearest_neighbor_vrptw] Total travel time with waiting: {total_time_waiting}")
    logger.info(f"[nearest_neighbor_vrptw] Total travel distance: {total_distance} meters")
    return route, unreachable, total_time, total_time_waiting, total_distance, location_dest_info

def calculate_total_distance(route_indices, distance_matrix, distance_from_DC):
    total_distance = 0
    for i in range(len(route_indices) - 1):
        total_distance += distance_matrix[route_indices[i]][route_indices[i+1]]
     
    return total_distance + distance_from_DC

def fetch_concatenate_route(latitude, longitude, ori_lat, ori_long):
    all_coords = []
    segment = _osrm_route_segment(ori_lat, ori_long, latitude, longitude, with_polyline=True)
    if segment and segment.get('geometry'):
        decoded = polyline.decode(segment['geometry'])
        all_coords.extend(decoded)
    else:
        logger.warning(
            f"[fetch_concatenate_route] Tidak ada polyline dari "
            f"({ori_lat},{ori_long}) ke ({latitude},{longitude})"
        )
    return all_coords


def fetch_concatenate_routes(route_indices, location_data, dc_coords):
    all_direction_results = []
    all_coords = []

    dc_lat, dc_lon = float(dc_coords[0]), float(dc_coords[1])

    # Segmen pertama: DC → lokasi pertama
    first_location = location_data.iloc[route_indices[0]]
    first_lat = first_location['latitude']
    first_lon = first_location['longitude']

    seg = _osrm_route_segment(dc_lat, dc_lon, first_lat, first_lon, with_polyline=True)
    if seg:
        all_direction_results.append(seg)
        if seg.get('geometry'):
            all_coords.extend(polyline.decode(seg['geometry']))

    # Segmen selanjutnya: antar titik pengiriman
    for i in range(len(route_indices) - 1):
        start = location_data.iloc[route_indices[i]]
        end   = location_data.iloc[route_indices[i + 1]]

        seg = _osrm_route_segment(
            start['latitude'], start['longitude'],
            end['latitude'],   end['longitude'],
            with_polyline=True
        )
        if seg:
            all_direction_results.append(seg)
            if seg.get('geometry'):
                all_coords.extend(polyline.decode(seg['geometry']))

    return all_coords, all_direction_results
