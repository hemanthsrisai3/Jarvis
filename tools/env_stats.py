import logging
from datetime import datetime
from typing import Dict, Any
import httpx
from tools.base import BaseTool
from config.settings import settings

logger = logging.getLogger("jarvis.tools.env_stats")

# Weather code mapping to human-readable strings
WEATHER_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️",
    2: "Partly cloudy ⛅",
    3: "Overcast ☁️",
    45: "Fog 🌫️",
    48: "Depositing rime fog 🌫️",
    51: "Light drizzle 🌧️",
    53: "Moderate drizzle 🌧️",
    55: "Dense drizzle 🌧️",
    56: "Light freezing drizzle 🌧️❄️",
    57: "Dense freezing drizzle 🌧️❄️",
    61: "Slight rain 🌧️",
    63: "Moderate rain 🌧️",
    65: "Heavy rain 🌧️",
    66: "Light freezing rain 🌧️❄️",
    67: "Heavy freezing rain 🌧️❄️",
    71: "Slight snow fall ❄️",
    73: "Moderate snow fall ❄️",
    75: "Heavy snow fall ❄️",
    77: "Snow grains ❄️",
    80: "Slight rain showers 🌧️",
    81: "Moderate rain showers 🌧️",
    82: "Violent rain showers 🌧️⛈️",
    85: "Slight snow showers ❄️",
    86: "Heavy snow showers ❄️",
    95: "Thunderstorm ⚡",
    96: "Thunderstorm with slight hail ⚡🌨️",
    99: "Thunderstorm with heavy hail ⚡🌨️"
}

class EnvStatsTool(BaseTool):
    """
    Fetches the current local date, time, and weather stats.
    """
    @property
    def name(self) -> str:
        return "env_stats"

    @property
    def description(self) -> str:
        return (
            "Returns the host's current local date, time, and weather. "
            "Can accept optional latitude and longitude parameters. If omitted, geolocates the user's IP to find the local weather."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Optional latitude coordinates."
                },
                "longitude": {
                    "type": "number",
                    "description": "Optional longitude coordinates."
                }
            },
            "additionalProperties": False
        }

    async def _geolocate_ip(self) -> Dict[str, Any]:
        """
        Geolocate public IP of the host machine using ip-api.
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://ip-api.com/json/")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return {
                            "lat": data.get("lat"),
                            "lon": data.get("lon"),
                            "city": data.get("city"),
                            "region": data.get("regionName"),
                            "country": data.get("country"),
                            "timezone": data.get("timezone")
                        }
        except Exception as e:
            logger.debug(f"IP Geolocation failed: {e}")
        
        # Fallback to Seattle, WA coordinates
        return {
            "lat": 47.6062,
            "lon": -122.3321,
            "city": "Seattle",
            "region": "Washington",
            "country": "United States",
            "timezone": "America/Los_Angeles"
        }

    async def run(self, **kwargs) -> str:
        # 1. Get current date & time
        now = datetime.now()
        local_time_str = now.strftime("%A, %B %d, %Y, %I:%M:%S %p")
        
        # 2. Get location details
        lat = kwargs.get("latitude")
        lon = kwargs.get("longitude")
        
        city_name = ""
        region_name = ""
        country_name = ""
        
        if lat is None or lon is None:
            # Geolocate automatically
            loc = await self._geolocate_ip()
            lat = loc["lat"]
            lon = loc["lon"]
            city_name = loc["city"]
            region_name = loc["region"]
            country_name = loc["country"]
        else:
            city_name = f"Coordinates ({lat}, {lon})"

        # 3. Fetch weather from Open-Meteo
        weather_str = ""
        try:
            weather_url = (
                f"{settings.WEATHER_API_URL}"
                f"?latitude={lat}&longitude={lon}&current_weather=true"
            )
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(weather_url)
                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current_weather", {})
                    temp_c = current.get("temperature", "N/A")
                    # Convert to Fahrenheit
                    temp_f = round((temp_c * 9/5) + 32, 1) if isinstance(temp_c, (int, float)) else "N/A"
                    wind_kmh = current.get("windspeed", "N/A")
                    weather_code = current.get("weathercode", -1)
                    desc = WEATHER_CODES.get(weather_code, "Unknown Weather Condition")
                    
                    loc_str = f" in {city_name}, {region_name}, {country_name}" if city_name else ""
                    weather_str = (
                        f"Weather{loc_str}:\n"
                        f"- Condition: {desc}\n"
                        f"- Temperature: {temp_c}°C ({temp_f}°F)\n"
                        f"- Wind Speed: {wind_kmh} km/h"
                    )
                else:
                    weather_str = f"Weather: Open-Meteo API returned status {response.status_code}."
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            weather_str = f"Weather: Service currently unavailable ({e})."

        # Combine results
        return (
            f"Host Local Date & Time:\n"
            f"- Time: {local_time_str}\n\n"
            f"{weather_str}"
        )
