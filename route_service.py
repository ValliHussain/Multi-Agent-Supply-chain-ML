# route_service.py
import requests

def get_coordinates(location_name: str):
    """Geocodes a city/port name into latitude and longitude using OpenStreetMap Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "AutonomousSupplyChainBot/1.0"}
    params = {"q": location_name, "format": "json", "limit": 1}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding error for {location_name}: {e}")
    
    # Default fallback coordinates (e.g., Bangalore / Chennai)
    return 12.9716, 77.5946

def fetch_live_weather(lat: float, lon: float):
    """Fetches real-time weather data and calculates a weather severity score (1-10)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation,wind_speed_10m"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        current = data.get("current", {})
        
        wind_speed = current.get("wind_speed_10m", 0.0) # km/h
        precipitation = current.get("precipitation", 0.0) # mm
        
        # Calculate weather severity score on a 1-10 scale
        # High wind (>40 km/h) or heavy rain (>5mm) drives up severity
        severity = 1.0 + (wind_speed / 8.0) + (precipitation * 1.5)
        return min(10.0, max(1.0, round(severity, 1)))
    except Exception as e:
        print(f"Weather API error: {e}")
        return 3.0 # Default mild severity fallback

def fetch_route_congestion(origin_coords, dest_coords):
    """Calculates route distance and congestion index using OSRM public routing engine."""
    url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}"
    params = {"overview": "false"}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data.get("routes"):
            route = data["routes"][0]
            distance_km = route["distance"] / 1000.0
            duration_hrs = route["duration"] / 3600.0
            
            # Estimate congestion index based on average speed delays
            # Standard smooth speed ~80 km/h. Lower speeds indicate congestion.
            expected_hours = distance_km / 80.0
            congestion_ratio = duration_hrs / max(0.1, expected_hours)
            
            congestion_index = 1.0 + (congestion_ratio - 1.0) * 5.0
            return min(10.0, max(1.0, round(congestion_index, 1))), round(distance_km, 1)
    except Exception as e:
        print(f"Routing API error: {e}")
        
    return 5.0, 500.0 # Fallback metrics

def get_realtime_telemetry(origin: str, destination: str):
    """Main orchestrator to fetch live weather and traffic conditions between origin and destination."""
    orig_lat, orig_lon = get_coordinates(origin)
    dest_lat, dest_lon = get_coordinates(destination)
    
    weather_severity = fetch_live_weather(dest_lat, dest_lon) # Evaluates destination weather hazards
    congestion_index, distance = fetch_route_congestion((orig_lat, orig_lon), (dest_lat, dest_lon))
    
    return {
        "route_congestion": congestion_index,
        "weather_severity": int(round(weather_severity)),
        "route_distance_km": distance
    }