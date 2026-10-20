import streamlit as st
import pandas as pd
import requests
import plotly.express as px

from datetime import datetime, timezone


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Disaster Intelligence Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# CONSTANTS
# =====================================================

LOCATIONS = {
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Thane": (19.2183, 72.9781),
    "Nashik": (19.9975, 73.7898),
    "Kolhapur": (16.7050, 74.2433)
}

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/"
    "feed/v1.0/summary/all_day.geojson"
)


# =====================================================
# DATA FUNCTIONS
# =====================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_weather():

    records = []
    errors = []

    for city, coordinates in LOCATIONS.items():

        latitude, longitude = coordinates

        params = {
            "latitude": latitude,
            "longitude": longitude,
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
                WEATHER_URL,
                params=params,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            current = data["current"]
            hourly = data["hourly"]

            # Build hourly forecast table.
            hourly_df = pd.DataFrame({
                "time": pd.to_datetime(hourly["time"]),
                "rainfall": hourly["precipitation"],
                "probability": hourly[
                    "precipitation_probability"
                ]
            })

            current_time = pd.to_datetime(
                current["time"]
            )

            future_df = hourly_df[
                hourly_df["time"] >= current_time
            ].head(6)

            rainfall_6h = float(
                future_df["rainfall"].fillna(0).sum()
            )

            rain_probability = (
                float(
                    future_df["probability"].max()
                )
                if not future_df.empty
                and future_df["probability"].notna().any()
                else None
            )

            # Illustrative indicator, not a validated
            # flood-prediction model.
            if rainfall_6h >= 50:
                risk = "High"
            elif (
                rainfall_6h >= 20
                or (
                    rain_probability is not None
                    and rain_probability >= 70
                )
            ):
                risk = "Moderate"
            else:
                risk = "Lower"

            records.append({
                "Location": city,
                "Temperature (°C)": current.get(
                    "temperature_2m"
                ),
                "Humidity (%)": current.get(
                    "relative_humidity_2m"
                ),
                "Current Precipitation (mm)": current.get(
                    "precipitation"
                ),
                "Wind Speed (km/h)": current.get(
                    "wind_speed_10m"
                ),
                "Next 6h Rainfall (mm)": round(
                    rainfall_6h, 2
                ),
                "Max Rain Probability (%)": rain_probability,
                "Rainfall Indicator": risk,
                "Latitude": latitude,
                "Longitude": longitude,
                "Weather Model Time": current.get(
                    "time", "Unavailable"
                )
            })

        except Exception as error:

            errors.append(
                f"{city}: {str(error)[:150]}"
            )

    return records, errors


@st.cache_data(ttl=60, show_spinner=False)
def fetch_earthquakes():

    response = requests.get(
        USGS_URL,
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
                "place", "Unknown"
            ),
            "Magnitude": properties.get("mag"),
            "Time": properties.get("time"),
            "Latitude": latitude,
            "Longitude": longitude,
            "Depth (km)": depth,
            "Status": properties.get(
                "status", "Unknown"
            ),
            "Event URL": properties.get("url", "")
        })

    return records


# =====================================================
# HEADER
# =====================================================

st.title("🌍 Multi-Source Disaster Intelligence System")

st.markdown(
    """
    ### Real-Time Environmental Monitoring & Disaster Analytics

    Integrating weather information and earthquake feeds
    to support environmental monitoring and disaster analysis.
    """
)

st.info(
    "Educational prototype. Data availability and update "
    "frequency depend on the source. This is not an official "
    "disaster-warning system."
)


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("⚙️ Dashboard Controls")

st.sidebar.write(
    "Monitor weather across five Maharashtra locations "
    "and review global earthquake events."
)

if st.sidebar.button("🔄 Refresh All Data"):

    fetch_weather.clear()
    fetch_earthquakes.clear()

    st.rerun()

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    **Data Sources**

    - Open-Meteo Weather API
    - USGS Earthquake Feed

    **Technologies**

    - Python
    - Pandas
    - Streamlit
    - Plotly
    """
)


# =====================================================
# RETRIEVE DATA
# =====================================================

weather_records = []
weather_errors = []

earthquake_records = []
earthquake_error = None

with st.spinner("Retrieving external data sources..."):

    weather_records, weather_errors = fetch_weather()

    try:
        earthquake_records = fetch_earthquakes()

    except Exception as error:
        earthquake_error = str(error)[:200]


retrieved_at = datetime.now(
    timezone.utc
).strftime("%Y-%m-%d %H:%M:%S UTC")

st.caption(
    f"Application retrieval time: {retrieved_at}"
)

st.caption(
    "Weather data may be model-based rather than direct "
    "physical measurements. Retrieval time does not indicate "
    "when the underlying source last updated its data."
)


# =====================================================
# WEATHER DATAFRAME
# =====================================================

# Always define the DataFrame before any section uses it.
weather_df = pd.DataFrame(weather_records)


# =====================================================
# WEATHER DASHBOARD
# =====================================================

st.header("🌦️ Regional Weather Monitoring")

if not weather_df.empty:

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Locations Reporting",
        len(weather_df)
    )

    average_temp = weather_df[
        "Temperature (°C)"
    ].mean()

    col2.metric(
        "Average Temperature",
        (
            f"{average_temp:.1f} °C"
            if pd.notna(average_temp)
            else "Unavailable"
        )
    )

    max_rain = weather_df[
        "Next 6h Rainfall (mm)"
    ].max()

    col3.metric(
        "Maximum Forecast Rainfall",
        (
            f"{max_rain:.1f} mm"
            if pd.notna(max_rain)
            else "Unavailable"
        )
    )

    st.subheader("Weather Conditions by Location")

    weather_columns = [
        "Location",
        "Temperature (°C)",
        "Humidity (%)",
        "Current Precipitation (mm)",
        "Wind Speed (km/h)",
        "Next 6h Rainfall (mm)",
        "Max Rain Probability (%)",
        "Rainfall Indicator"
    ]

    st.dataframe(
        weather_df[weather_columns],
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🌧️ Forecast Rainfall Comparison")

    rainfall_fig = px.bar(
        weather_df,
        x="Location",
        y="Next 6h Rainfall (mm)",
        color="Rainfall Indicator",
        title="Forecast Precipitation Over the Next Six Hours"
    )

    st.plotly_chart(
        rainfall_fig,
        use_container_width=True
    )

    st.subheader("🌡️ Temperature Comparison")

    temperature_df = weather_df.dropna(
        subset=["Temperature (°C)"]
    )

    if not temperature_df.empty:

        temperature_fig = px.bar(
            temperature_df,
            x="Location",
            y="Temperature (°C)",
            title="Current Weather-Model Temperature"
        )

        st.plotly_chart(
            temperature_fig,
            use_container_width=True
        )

    st.subheader("📍 Regional Monitoring Map")

    # st.map expects latitude/longitude columns.
    # Rename explicitly for compatibility.
    map_df = weather_df[
        ["Latitude", "Longitude"]
    ].copy()

    map_df.columns = ["latitude", "longitude"]

    map_df = map_df.dropna(
        subset=["latitude", "longitude"]
    )

    if not map_df.empty:

        st.map(map_df)

    else:

        st.warning(
            "Location coordinates are currently unavailable."
        )

    st.subheader("⚠️ Preliminary Rainfall Indicators")

    st.write(
        "These categories use illustrative rainfall and "
        "precipitation-probability thresholds. They are not "
        "validated flood predictions or official warnings."
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
        "⬇️ Download Weather Data",
        data=weather_df.to_csv(index=False),
        file_name="weather_monitoring.csv",
        mime="text/csv"
    )

    with st.expander("Weather Model Timestamps"):

        st.dataframe(
            weather_df[
                ["Location", "Weather Model Time"]
            ],
            use_container_width=True,
            hide_index=True
        )

else:

    st.warning(
        "Weather information is temporarily unavailable. "
        "Please try refreshing the data."
    )


if weather_errors:

    with st.expander("Weather Source Diagnostics"):

        for message in weather_errors:
            st.write(message)


# =====================================================
# EARTHQUAKE DATAFRAME
# =====================================================

earthquake_df = pd.DataFrame(
    earthquake_records
)


# =====================================================
# EARTHQUAKE DASHBOARD
# =====================================================

st.divider()

st.header("🌎 Global Earthquake Intelligence")

if not earthquake_df.empty:

    valid_magnitudes = earthquake_df[
        "Magnitude"
    ].dropna()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Events in USGS Feed",
        len(earthquake_df)
    )

    col2.metric(
        "Magnitude ≥ 4",
        int(
            (valid_magnitudes >= 4).sum()
        )
    )

    col3.metric(
        "Largest Magnitude",
        (
            f"{valid_magnitudes.max():.1f}"
            if not valid_magnitudes.empty
            else "Unavailable"
        )
    )

    st.subheader("📈 Earthquake Magnitude Distribution")

    if not valid_magnitudes.empty:

        magnitude_df = earthquake_df.dropna(
            subset=["Magnitude"]
        )

        magnitude_fig = px.histogram(
            magnitude_df,
            x="Magnitude",
            nbins=20,
            title="Distribution of Earthquake Magnitudes"
        )

        st.plotly_chart(
            magnitude_fig,
            use_container_width=True
        )

    st.subheader("🗺️ Global Earthquake Map")

    quake_map_df = earthquake_df[
        ["Latitude", "Longitude"]
    ].copy()

    quake_map_df.columns = [
        "latitude",
        "longitude"
    ]

    quake_map_df = quake_map_df.dropna(
        subset=["latitude", "longitude"]
    )

    if not quake_map_df.empty:

        st.map(quake_map_df)

    else:

        st.info(
            "Earthquake coordinates are unavailable."
        )

    st.subheader("Recent Earthquake Records")

    display_quakes = earthquake_df.copy()

    display_quakes["Time"] = pd.to_datetime(
        display_quakes["Time"],
        unit="ms",
        utc=True,
        errors="coerce"
    ).dt.strftime("%Y-%m-%d %H:%M UTC")

    display_columns = [
        "Place",
        "Magnitude",
        "Time",
        "Depth (km)",
        "Status"
    ]

    st.dataframe(
        display_quakes[display_columns].sort_values(
            "Time",
            ascending=False,
            na_position="last"
        ),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ Download Earthquake Data",
        data=earthquake_df.to_csv(index=False),
        file_name="usgs_earthquakes.csv",
        mime="text/csv"
    )

else:

    st.warning(
        "Earthquake data is currently unavailable."
    )

    if earthquake_error:

        with st.expander("Earthquake Source Diagnostics"):
            st.write(earthquake_error)


# =====================================================
# METHODOLOGY
# =====================================================

st.divider()

st.header("📚 Data Sources & Methodology")

st.markdown(
    """
    **Source 1 — Open-Meteo**

    Provides weather-model current conditions and hourly
    precipitation information for monitored locations.

    **Source 2 — USGS**

    Provides global earthquake event records for the
    preceding 24 hours.

    **Data processing**

    Python requests retrieve JSON and GeoJSON data.
    Pandas structures and processes the retrieved records.

    **Analytics**

    The dashboard compares weather conditions, summarizes
    earthquake magnitudes, and calculates preliminary
    rainfall indicators.

    **Visualization**

    Plotly charts and geographic maps display the results.

    **Limitations**

    The current version is an educational multi-source
    analytics prototype. Its rainfall indicators have not
    been validated as flood predictions. The application
    does not replace official weather or disaster warnings.
    """
)

st.caption(
    "Multi-Source Disaster Intelligence System | "
    "Educational Big Data Analytics Prototype"
)