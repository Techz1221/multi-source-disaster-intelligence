import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timezone

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Disaster Intelligence System",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Multi-Source Disaster Intelligence System")

st.markdown(
    """
    **Real-Time Environmental Monitoring & Disaster Analytics**

    Integrating weather information and earthquake feeds
    to support environmental monitoring and disaster analysis.
    """
)

st.caption(
    "Educational prototype | Live data where available | "
    "Not an official disaster-warning service"
)

# --------------------------------------------------
# MONITORED LOCATIONS
# --------------------------------------------------

LOCATIONS = {
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Thane": (19.2183, 72.9781),
    "Nashik": (19.9975, 73.7898),
    "Kolhapur": (16.7050, 74.2433)
}

# --------------------------------------------------
# WEATHER DATA SOURCE: OPEN-METEO
# --------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_weather():
    records = []
    errors = []

    for city, coordinates in LOCATIONS.items():
        lat, lon = coordinates

        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation,"
                "rain,"
                "wind_speed_10m"
            ),
            "hourly": (
                "precipitation,"
                "precipitation_probability"
            ),
            "forecast_days": 1,
            "timezone": "Asia/Kolkata"
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=15
            )
            response.raise_for_status()

            data = response.json()
            current = data["current"]
            hourly = data["hourly"]

            times = pd.to_datetime(hourly["time"])

            now = pd.to_datetime(
                current["time"]
            )

            # Use the six hourly forecast points starting
            # at or immediately after the current model time.
            future_mask = times >= now
            future = pd.DataFrame({
                "time": times,
                "rain_mm": hourly["precipitation"],
                "rain_probability": hourly[
                    "precipitation_probability"
                ]
            }).loc[future_mask].head(6)

            rainfall_6h = float(
                future["rain_mm"].fillna(0).sum()
            )

            probability = float(
                future["rain_probability"]
                .fillna(0).max()
            ) if not future.empty else 0.0

            # Illustrative screening indicator only.
            # Not a validated flood prediction.
            if rainfall_6h >= 50:
                level = "High"
            elif rainfall_6h >= 20 or probability >= 70:
                level = "Moderate"
            else:
                level = "Lower"

            records.append({
                "Location": city,
                "Temperature (°C)": current[
                    "temperature_2m"
                ],
                "Humidity (%)": current[
                    "relative_humidity_2m"
                ],
                "Current Precipitation (mm)": current[
                    "precipitation"
                ],
                "Wind Speed (km/h)": current[
                    "wind_speed_10m"
                ],
                "Next 6h Rainfall (mm)": round(
                    rainfall_6h, 2
                ),
                "Max Rain Probability (%)": round(
                    probability, 1
                ),
                "Rainfall Indicator": level,
                "Latitude": lat,
                "Longitude": lon,
                "Weather Model Time": current["time"]
            })

        except Exception as error:
            errors.append(
                f"{city}: {str(error)[:160]}"
            )

    return records, errors


# --------------------------------------------------
# EARTHQUAKE SOURCE: USGS
# --------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_earthquakes():
    url = (
        "https://earthquake.usgs.gov/earthquakes/"
        "feed/v1.0/summary/all_day.geojson"
    )

    response = requests.get(
        url,
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    records = []

    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")

        if not coordinates:
            continue

        longitude, latitude, depth = coordinates

        records.append({
            "Place": properties.get(
                "place", "Unknown location"
            ),
            "Magnitude": properties.get("mag"),
            "Time": properties.get("time"),
            "Latitude": latitude,
            "Longitude": longitude,
            "Depth (km)": depth,
            "Status": properties.get(
                "status", "Unknown"
            ),
            "URL": properties.get("url", "")
        })

    return records


# --------------------------------------------------
# MANUAL REFRESH
# --------------------------------------------------

if st.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# FETCH DATA
# --------------------------------------------------

st.subheader("📍 Regional Monitoring Map")

if weather_records:
    st.map(
        pd.DataFrame(weather_records)[
            ["Latitude", "Longitude"]
        ]
    )
else:
    st.warning("Weather data is currently unavailable.")
weather_records = []
weather_errors = []
earthquake_records = []
earthquake_error = None

with st.spinner("Retrieving the latest available data..."):
    weather_records, weather_errors = get_weather()

    try:
        earthquake_records = get_earthquakes()
    except Exception as error:
        earthquake_error = str(error)[:250]

retrieved_at = datetime.now(
    timezone.utc
).strftime("%Y-%m-%d %H:%M:%S UTC")

st.caption(
    f"Application retrieval time: {retrieved_at}"
)

st.caption(
    "Weather timestamps represent the source's current "
    "modelled conditions. They are not guaranteed to be "
    "instantaneous physical observations."
)

# --------------------------------------------------
# WEATHER DASHBOARD
# --------------------------------------------------

st.header("🌦️ Regional Weather Monitoring")

if weather_records:
    weather_df = pd.DataFrame(weather_records)

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Locations Reporting",
        len(weather_df)
    )

    col2.metric(
        "Average Temperature",
        f"{weather_df['Temperature (°C)'].mean():.1f} °C"
    )

    col3.metric(
        "Maximum Next 6h Rainfall",
        f"{weather_df['Next 6h Rainfall (mm)'].max():.1f} mm"
    )

    st.subheader("Weather Conditions by Location")

    st.dataframe(
        weather_df[
            [
                "Location",
                "Temperature (°C)",
                "Humidity (%)",
                "Current Precipitation (mm)",
                "Wind Speed (km/h)",
                "Next 6h Rainfall (mm)",
                "Max Rain Probability (%)",
                "Rainfall Indicator"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🌧️ Rainfall Comparison")

    fig = px.bar(
        weather_df,
        x="Location",
        y="Next 6h Rainfall (mm)",
        color="Rainfall Indicator",
        title="Forecast Precipitation: Next Six Hours",
        labels={
            "Next 6h Rainfall (mm)": "Rainfall (mm)"
        }
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.subheader("🌡️ Temperature Comparison")

    fig2 = px.bar(
        weather_df,
        x="Location",
        y="Temperature (°C)",
        title="Current Weather-Model Temperature",
        labels={
            "Temperature (°C)": "Temperature (°C)"
        }
    )

    st.plotly_chart(
        fig2,
        use_container_width=True
    )

    st.subheader("📍 Regional Monitoring Map")

    st.map(
        weather_df[["Latitude", "Longitude"]],
        use_container_width=True
    )

    st.subheader("🔎 Rainfall Indicator Analysis")

    st.write(
        "The following categories are based on the "
        "prototype's illustrative six-hour rainfall "
        "and precipitation-probability rules."
    )

    st.dataframe(
        weather_df[
            [
                "Location",
                "Next 6h Rainfall (mm)",
                "Max Rain Probability (%)",
                "Rainfall Indicator"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Download Weather Data as CSV",
        weather_df.to_csv(index=False),
        file_name="weather_monitoring.csv",
        mime="text/csv"
    )

    with st.expander("Weather source timestamps"):
        st.dataframe(
            weather_df[
                ["Location", "Weather Model Time"]
            ],
            use_container_width=True,
            hide_index=True
        )

else:
    st.error(
        "Weather data could not be retrieved. "
        "Check your internet connection or retry later."
    )

if weather_errors:
    with st.expander("Weather retrieval diagnostics"):
        for message in weather_errors:
            st.write(message)

# --------------------------------------------------
# EARTHQUAKE DASHBOARD
# --------------------------------------------------

st.header("🌎 Global Earthquake Intelligence")

if earthquake_records:
    quake_df = pd.DataFrame(earthquake_records)

    valid_magnitudes = quake_df[
        "Magnitude"
    ].dropna()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Earthquakes in Feed",
        len(quake_df)
    )

    col2.metric(
        "Magnitude ≥ 4",
        int((valid_magnitudes >= 4).sum())
    )

    col3.metric(
        "Largest Recorded Magnitude",
        f"{valid_magnitudes.max():.1f}"
        if not valid_magnitudes.empty
        else "N/A"
    )

    st.subheader("📈 Earthquake Magnitude Distribution")

    fig3 = px.histogram(
        quake_df.dropna(subset=["Magnitude"]),
        x="Magnitude",
        nbins=20,
        title="Distribution of Reported Earthquake Magnitudes"
    )

    st.plotly_chart(
        fig3,
        use_container_width=True
    )

    st.subheader("🗺️ Recent Earthquake Locations")

    st.caption(
        "This map displays locations in the global USGS "
        "feed, not only India."
    )

    st.map(
        quake_df[["Latitude", "Longitude"]],
        use_container_width=True
    )

    st.subheader("Recent Earthquake Records")

    display_df = quake_df.copy()

    display_df["Time"] = pd.to_datetime(
        display_df["Time"],
        unit="ms",
        utc=True
    ).dt.strftime("%Y-%m-%d %H:%M UTC")

    st.dataframe(
        display_df[
            [
                "Place",
                "Magnitude",
                "Time",
                "Depth (km)",
                "Status"
            ]
        ].sort_values(
            "Time",
            ascending=False
        ),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Download Earthquake Data as CSV",
        quake_df.to_csv(index=False),
        file_name="usgs_earthquakes.csv",
        mime="text/csv"
    )

else:
    if earthquake_error:
        st.warning(
            "The earthquake feed could not be retrieved. "
            "Please retry later."
        )

        with st.expander("Earthquake retrieval diagnostics"):
            st.write(earthquake_error)
    else:
        st.info(
            "No earthquake records are currently available."
        )

# --------------------------------------------------
# DATA SOURCES AND LIMITATIONS
# --------------------------------------------------

st.divider()

st.header("📚 Data Sources & Methodology")

st.markdown(
    """
    **1. Weather data:** Open-Meteo Forecast API.

    **2. Earthquake data:** USGS Earthquake GeoJSON Feed.

    **3. Processing:** Python and Pandas.

    **4. Visualization:** Streamlit, Plotly and geographic maps.

    **5. Update behaviour:** Weather responses are cached for
    five minutes and earthquake responses for one minute.
    The dashboard retrieves data when it runs or is refreshed.

    **6. Limitations:** The rainfall categories are illustrative
    screening indicators, not validated flood predictions.
    Weather-model values may differ from actual local
    observations. This prototype is not an official warning
    service and should not be used for emergency decisions.
    """
)

st.caption(
    "Developed as an educational Big Data Analytics project."
)