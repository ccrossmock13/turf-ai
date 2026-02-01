"""
Weather integration for turf management recommendations.
Uses OpenWeatherMap API to get local weather and factor it into recommendations.
"""
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# OpenWeatherMap API
OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5"


def get_weather_data(
    lat: float = None,
    lon: float = None,
    city: str = None,
    state: str = None
) -> Optional[Dict[str, Any]]:
    """
    Get current weather and forecast for a location.

    Args:
        lat, lon: Coordinates (preferred)
        city, state: City/state name (fallback)

    Returns:
        Weather data dict or None if unavailable
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logger.debug("No OpenWeatherMap API key configured")
        return None

    try:
        # Build location query
        if lat and lon:
            location_param = f"lat={lat}&lon={lon}"
        elif city:
            location = f"{city},{state},US" if state else city
            location_param = f"q={location}"
        else:
            return None

        # Get current weather
        current_url = f"{OPENWEATHER_API_URL}/weather?{location_param}&appid={api_key}&units=imperial"
        current_response = requests.get(current_url, timeout=5)
        current_response.raise_for_status()
        current_data = current_response.json()

        # Get 5-day forecast
        forecast_url = f"{OPENWEATHER_API_URL}/forecast?{location_param}&appid={api_key}&units=imperial"
        forecast_response = requests.get(forecast_url, timeout=5)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        return {
            'current': _parse_current_weather(current_data),
            'forecast': _parse_forecast(forecast_data),
            'location': current_data.get('name', 'Unknown')
        }

    except requests.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Weather parsing failed: {e}")
        return None


def _parse_current_weather(data: Dict) -> Dict[str, Any]:
    """Parse current weather response."""
    main = data.get('main', {})
    weather = data.get('weather', [{}])[0]
    wind = data.get('wind', {})

    return {
        'temp': main.get('temp'),
        'feels_like': main.get('feels_like'),
        'humidity': main.get('humidity'),
        'description': weather.get('description', ''),
        'wind_speed': wind.get('speed'),
        'wind_gust': wind.get('gust'),
    }


def _parse_forecast(data: Dict) -> list:
    """Parse forecast response into daily summaries."""
    forecasts = []
    daily_data = {}

    for item in data.get('list', []):
        dt = datetime.fromtimestamp(item['dt'])
        date_key = dt.strftime('%Y-%m-%d')

        if date_key not in daily_data:
            daily_data[date_key] = {
                'date': date_key,
                'temps': [],
                'humidity': [],
                'rain_chance': 0,
                'conditions': []
            }

        daily_data[date_key]['temps'].append(item['main']['temp'])
        daily_data[date_key]['humidity'].append(item['main']['humidity'])

        # Track rain probability
        if 'pop' in item:
            daily_data[date_key]['rain_chance'] = max(
                daily_data[date_key]['rain_chance'],
                item['pop'] * 100
            )

        # Track conditions
        if item.get('weather'):
            daily_data[date_key]['conditions'].append(
                item['weather'][0].get('main', '')
            )

    # Summarize each day
    for date_key in sorted(daily_data.keys())[:5]:  # Next 5 days
        day = daily_data[date_key]
        forecasts.append({
            'date': date_key,
            'high': max(day['temps']) if day['temps'] else None,
            'low': min(day['temps']) if day['temps'] else None,
            'avg_humidity': sum(day['humidity']) / len(day['humidity']) if day['humidity'] else None,
            'rain_chance': day['rain_chance'],
            'conditions': max(set(day['conditions']), key=day['conditions'].count) if day['conditions'] else ''
        })

    return forecasts


def get_weather_context(weather_data: Dict) -> str:
    """
    Convert weather data into context for the AI prompt.
    Highlights conditions relevant to turf management.
    """
    if not weather_data:
        return ""

    current = weather_data.get('current', {})
    forecast = weather_data.get('forecast', [])
    location = weather_data.get('location', 'your area')

    context_parts = [f"\n[CURRENT WEATHER - {location}]"]

    # Current conditions
    if current.get('temp'):
        context_parts.append(f"Temperature: {current['temp']:.0f}°F (feels like {current.get('feels_like', current['temp']):.0f}°F)")
    if current.get('humidity'):
        context_parts.append(f"Humidity: {current['humidity']}%")
    if current.get('wind_speed'):
        wind_str = f"Wind: {current['wind_speed']:.0f} mph"
        if current.get('wind_gust'):
            wind_str += f" (gusts to {current['wind_gust']:.0f} mph)"
        context_parts.append(wind_str)
    if current.get('description'):
        context_parts.append(f"Conditions: {current['description'].title()}")

    # Forecast summary
    if forecast:
        context_parts.append("\n[FORECAST]")
        for day in forecast[:3]:  # Next 3 days
            date_str = datetime.strptime(day['date'], '%Y-%m-%d').strftime('%A')
            line = f"{date_str}: {day['high']:.0f}°F/{day['low']:.0f}°F"
            if day['rain_chance'] > 30:
                line += f" - {day['rain_chance']:.0f}% chance of rain"
            context_parts.append(line)

    return "\n".join(context_parts)


def get_weather_warnings(weather_data: Dict) -> list:
    """
    Analyze weather and return turf-relevant warnings.
    """
    if not weather_data:
        return []

    warnings = []
    current = weather_data.get('current', {})
    forecast = weather_data.get('forecast', [])

    temp = current.get('temp', 70)
    humidity = current.get('humidity', 50)
    wind = current.get('wind_speed', 0)

    # High temperature warnings
    if temp > 90:
        warnings.append({
            'type': 'heat_stress',
            'message': f"High temperature ({temp:.0f}°F) - avoid foliar applications, consider syringing",
            'severity': 'high'
        })
    elif temp > 85:
        warnings.append({
            'type': 'heat_caution',
            'message': f"Warm conditions ({temp:.0f}°F) - reduce herbicide rates, avoid DMI fungicides on greens",
            'severity': 'medium'
        })

    # Disease pressure warnings
    if humidity > 90 and temp > 68:
        warnings.append({
            'type': 'disease_pressure',
            'message': f"Brown patch conditions: High humidity ({humidity}%) + warm temps ({temp:.0f}°F)",
            'severity': 'high'
        })
    elif humidity > 80 and 60 < temp < 85:
        warnings.append({
            'type': 'disease_pressure',
            'message': f"Dollar spot conditions: Moderate humidity ({humidity}%) + temps {temp:.0f}°F",
            'severity': 'medium'
        })

    # Wind warnings for spraying
    if wind > 15:
        warnings.append({
            'type': 'spray_warning',
            'message': f"Wind too high for spraying ({wind:.0f} mph) - postpone applications",
            'severity': 'high'
        })
    elif wind > 10:
        warnings.append({
            'type': 'spray_caution',
            'message': f"Windy conditions ({wind:.0f} mph) - use low-drift nozzles, avoid fine sprays",
            'severity': 'medium'
        })

    # Rain in forecast
    for day in forecast[:2]:  # Next 2 days
        if day.get('rain_chance', 0) > 60:
            date_str = datetime.strptime(day['date'], '%Y-%m-%d').strftime('%A')
            warnings.append({
                'type': 'rain_forecast',
                'message': f"Rain likely {date_str} ({day['rain_chance']:.0f}% chance) - time applications accordingly",
                'severity': 'medium'
            })
            break  # Only warn once

    return warnings


def format_weather_for_response(weather_data: Dict) -> Optional[str]:
    """
    Format weather information for display in the response.
    Returns a concise summary for the user.
    """
    if not weather_data:
        return None

    current = weather_data.get('current', {})
    warnings = get_weather_warnings(weather_data)
    location = weather_data.get('location', 'your area')

    parts = [f"**Current conditions in {location}:** {current.get('temp', 'N/A'):.0f}°F, "
             f"{current.get('humidity', 'N/A')}% humidity"]

    if current.get('wind_speed', 0) > 5:
        parts[0] += f", wind {current['wind_speed']:.0f} mph"

    # Add high-severity warnings
    high_warnings = [w for w in warnings if w['severity'] == 'high']
    if high_warnings:
        parts.append("\n⚠️ **Weather Alerts:**")
        for w in high_warnings:
            parts.append(f"- {w['message']}")

    return "\n".join(parts)
