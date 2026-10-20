import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh

# =========================================================
# MULTI-SOURCE DISASTER INTELLIGENCE SYSTEM
# Educational Big Data Analytics Project
# =========================================================

st.set_page_config(
    page_title="Disaster Intelligence System",
    page_icon="🌍",
    layout="wide"
)

# Automatically refresh the dashboard every 60 seconds
st_autorefresh(interval=60 * 1000, key="auto_refresh")

st.title("🌍 Multi-Source Disaster Intelligence System")

st.markdown("""
Monitor weather conditions, rainfall forecasts, and global earthquake
activity using public data sources.
""")

st.warning(
    "Educational prototype only. This dashboard is not an official "
    "disaster warning system. Always follow official advisories."
)

# =========================================================
# CONFIGURATION
# =========================================================

LOCATIONS = {
    "Mumbai": {"latitude": 19.0760, "longitude": 72.8777},
    "Pune": {"latitude": 18.5204, "longitude": 73.8567},
    "Thane": {"latitude": 19.2183, "longitude": 72.9781},
    "Nashik": {"latitude": 19.9975, "longitude": 73.7898},
    "Kolhapur": {"latitude": 16.7050, "longitude": 74.2433},
}

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

USGS_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)

LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


# =========================================================
# RAINFALL SCREENING
# =========================================================

def rainfall_level(rainfall, probability):

    if pd.notna(rainfall) and rainfall >= 50:
        return "High"

    if (
        (pd.notna(rainfall) and rainfall >= 20)
        or
        (pd.notna(probability) and probability >= 70)
    ):
        return "Moderate"

    return "Lower"


# =========================================================
# FETCH WEATHER AND HOURLY FORECAST
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def fetch_weather():

    current_records = []
    hourly_records = []
    errors = []

    for city, coordinates in LOCATIONS.items():

        parameters = {
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
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
            "forecast_days": 2,
            "timezone": "Asia/Kolkata",
        }

        try:

            response = requests.get(
                WEATHER_URL,
                params=parameters,
                timeout=15
            )

            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            hourly = data.get("hourly", {})

            hourly_df = pd.DataFrame({
                "Time": hourly.get("time", []),
                "Rainfall (mm)": hourly.get("precipitation", []),
                "Rain probability (%)": hourly.get(
                    "precipitation_probability", []
                ),
            })

            if not hourly_df.empty:

                hourly_df["Time"] = pd.to_datetime(
                    hourly_df["Time"],
                    errors="coerce"
                )

                now = (
                    pd.Timestamp.now(tz="Asia/Kolkata")
                    .tz_localize(None)
                )

                next_6_hours = hourly_df[
                    (hourly_df["Time"] >= now)
                    &
                    (
                        hourly_df["Time"]
                        < now + pd.Timedelta(hours=6)
                    )
                ]

                next_24_hours = hourly_df[
                    (hourly_df["Time"] >= now)
                    &
                    (
                        hourly_df["Time"]
                        < now + pd.Timedelta(hours=24)
                    )
                ]

                rainfall_6h = pd.to_numeric(
                    next_6_hours["Rainfall (mm)"],
                    errors="coerce"
                ).sum(min_count=1)

                probability_24h = pd.to_numeric(
                    next_24_hours["Rain probability (%)"],
                    errors="coerce"
                ).max()

                for _, row in next_24_hours.iterrows():

                    hourly_records.append({
                        "City": city,
                        "Time": row["Time"],
                        "Rainfall (mm)": row["Rainfall (mm)"],
                        "Rain probability (%)": row[
                            "Rain probability (%)"
                        ],
                    })

            else:
                rainfall_6h = float("nan")
                probability_24h = float("nan")

            current_records.append({
                "City": city,
                "Temperature (°C)": current.get(
                    "temperature_2m"
                ),
                "Humidity (%)": current.get(
                    "relative_humidity_2m"
                ),
                "Current precipitation (mm)": current.get(
                    "precipitation"
                ),
                "Current rain (mm)": current.get("rain"),
                "Wind speed (km/h)": current.get(
                    "wind_speed_10m"
                ),
                "Rainfall next 6h (mm)": rainfall_6h,
                "Max rain probability next 24h (%)": probability_24h,
                "Risk indicator": rainfall_level(
                    rainfall_6h,
                    probability_24h
                ),
                "Latitude": coordinates["latitude"],
                "Longitude": coordinates["longitude"],
                "Model/data time": current.get(
                    "time", "Unavailable"
                ),
            })

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError
        ) as error:

            errors.append(f"{city}: {error}")

    return current_records, hourly_records, errors


# =========================================================
# FETCH EARTHQUAKE DATA
# =========================================================

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

        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []

        if len(coordinates) < 3:
            continue

        timestamp = properties.get("time")

        if timestamp is not None:
            event_time = datetime.fromtimestamp(
                timestamp / 1000,
                tz=LOCAL_TIMEZONE
            ).strftime("%d %b %Y, %I:%M:%S %p IST")
        else:
            event_time = "Unknown"

        records.append({
            "Place": properties.get(
                "place", "Unknown location"
            ),
            "Magnitude": properties.get("mag"),
            "Time (IST)": event_time,
            "Longitude": coordinates[0],
            "Latitude": coordinates[1],
            "Depth (km)": coordinates[2],
            "Status": properties.get("status", "Unknown"),
            "Event URL": properties.get("url", ""),
        })

    return records


# =========================================================
# SIDEBAR CONTROLS
# =========================================================

st.sidebar.header("Dashboard Controls")

if st.sidebar.button(
    "🔄 Refresh source data now",
    use_container_width=True
):

    fetch_weather.clear()
    fetch_earthquakes.clear()
    st.rerun()

st.sidebar.caption("Dashboard refresh: 60 seconds")
st.sidebar.caption("Weather cache: 5 minutes")
st.sidebar.caption("Earthquake cache: 1 minute")


# =========================================================
# LOAD DATA
# =========================================================

with st.spinner("Loading live-source data..."):

    weather_records, hourly_records, weather_errors = (
        fetch_weather()
    )

    earthquake_error = None

    try:
        earthquake_records = fetch_earthquakes()

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError
    ) as error:

        earthquake_records = []
        earthquake_error = str(error)


weather_df = pd.DataFrame(weather_records)
hourly_df = pd.DataFrame(hourly_records)
earthquake_df = pd.DataFrame(earthquake_records)

st.caption(
    "Dashboard checked at: "
    + datetime.now(LOCAL_TIMEZONE).strftime(
        "%d %b %Y, %I:%M:%S %p IST"
    )
)

if weather_errors:

    with st.expander("Weather source messages"):

        for error in weather_errors:
            st.warning(error)

if earthquake_error:
    st.warning(
        f"Earthquake data is temporarily unavailable: "
        f"{earthquake_error}"
    )


# =========================================================
# WEATHER DASHBOARD
# =========================================================

st.header("🌦️ Weather and Rainfall Monitoring")

st.info(
    "Weather information is provided by Open-Meteo. Current conditions "
    "may be model-derived rather than direct weather-station observations."
)

if weather_df.empty:

    st.error(
        "Weather data is unavailable. Try refreshing the source data."
    )

else:

    rainfall_values = pd.to_numeric(
        weather_df["Rainfall next 6h (mm)"],
        errors="coerce"
    )

    wind_values = pd.to_numeric(
        weather_df["Wind speed (km/h)"],
        errors="coerce"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Locations monitored",
        len(weather_df)
    )

    col2.metric(
        "Highest forecast rainfall",
        (
            f"{rainfall_values.max():.1f} mm"
            if rainfall_values.notna().any()
            else "N/A"
        )
    )

    col3.metric(
        "Highest wind speed",
        (
            f"{wind_values.max():.1f} km/h"
            if wind_values.notna().any()
            else "N/A"
        )
    )

    # Current conditions table

    st.subheader("Current Conditions")

    columns_to_show = [
        "City",
        "Temperature (°C)",
        "Humidity (%)",
        "Current precipitation (mm)",
        "Wind speed (km/h)",
        "Rainfall next 6h (mm)",
        "Max rain probability next 24h (%)",
        "Risk indicator",
        "Model/data time",
    ]

    st.dataframe(
        weather_df[columns_to_show].round(1),
        use_container_width=True,
        hide_index=True
    )

    # Alert panel

    st.subheader("🚨 Preliminary Rainfall Alerts")

    high_alerts = weather_df[
        weather_df["Risk indicator"] == "High"
    ]

    moderate_alerts = weather_df[
        weather_df["Risk indicator"] == "Moderate"
    ]

    if not high_alerts.empty:

        for _, row in high_alerts.iterrows():

            rainfall = row["Rainfall next 6h (mm)"]

            st.error(
                f"HIGH SCREENING INDICATOR — {row['City']}: "
                f"{rainfall:.1f} mm forecast rainfall "
                f"over the next 6 hours."
            )

    if not moderate_alerts.empty:

        for _, row in moderate_alerts.iterrows():

            rainfall = row["Rainfall next 6h (mm)"]
            probability = row[
                "Max rain probability next 24h (%)"
            ]

            rainfall_text = (
                f"{rainfall:.1f} mm"
                if pd.notna(rainfall)
                else "N/A"
            )

            probability_text = (
                f"{probability:.0f}%"
                if pd.notna(probability)
                else "N/A"
            )

            st.warning(
                f"MODERATE SCREENING INDICATOR — {row['City']}: "
                f"next-6-hour rainfall {rainfall_text}; "
                f"maximum hourly rain probability in the next "
                f"24 hours {probability_text}."
            )

    if high_alerts.empty and moderate_alerts.empty:

        st.success(
            "No locations currently cross this prototype's "
            "rainfall screening thresholds. This does not guarantee "
            "that conditions are safe."
        )

    # Bar charts

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:

        rainfall_chart = weather_df.copy()

        rainfall_chart["Rainfall next 6h (mm)"] = pd.to_numeric(
            rainfall_chart["Rainfall next 6h (mm)"],
            errors="coerce"
        )

        figure = px.bar(
            rainfall_chart,
            x="City",
            y="Rainfall next 6h (mm)",
            title="Forecast Rainfall — Next 6 Hours",
            labels={
                "Rainfall next 6h (mm)": "Rainfall (mm)"
            }
        )

        st.plotly_chart(
            figure,
            use_container_width=True
        )

    with chart_col2:

        temperature_chart = weather_df.copy()

        temperature_chart["Temperature (°C)"] = pd.to_numeric(
            temperature_chart["Temperature (°C)"],
            errors="coerce"
        )

        figure = px.bar(
            temperature_chart,
            x="City",
            y="Temperature (°C)",
            title="Current Modelled Temperature"
        )

        st.plotly_chart(
            figure,
            use_container_width=True
        )

    # Hourly forecast graphs

    st.subheader("📈 Hourly Forecast — Next 24 Hours")

    if not hourly_df.empty:

        hourly_df["Time"] = pd.to_datetime(
            hourly_df["Time"],
            errors="coerce"
        )

        hourly_df["Rainfall (mm)"] = pd.to_numeric(
            hourly_df["Rainfall (mm)"],
            errors="coerce"
        )

        hourly_df["Rain probability (%)"] = pd.to_numeric(
            hourly_df["Rain probability (%)"],
            errors="coerce"
        )

        selected_cities = st.multiselect(
            "Select locations",
            options=list(LOCATIONS.keys()),
            default=["Mumbai", "Pune"]
        )

        selected_data = hourly_df[
            hourly_df["City"].isin(selected_cities)
        ]

        if not selected_data.empty:

            rainfall_figure = px.line(
                selected_data,
                x="Time",
                y="Rainfall (mm)",
                color="City",
                markers=True,
                title="Hourly Rainfall Forecast",
                labels={
                    "Time": "Time (IST)",
                    "Rainfall (mm)": "Forecast rainfall (mm)"
                }
            )

            st.plotly_chart(
                rainfall_figure,
                use_container_width=True
            )

            probability_figure = px.line(
                selected_data,
                x="Time",
                y="Rain probability (%)",
                color="City",
                markers=True,
                title="Hourly Precipitation Probability",
                labels={
                    "Time": "Time (IST)",
                    "Rain probability (%)": "Probability (%)"
                }
            )

            st.plotly_chart(
                probability_figure,
                use_container_width=True
            )

        else:

            st.info(
                "Select at least one city to display the forecast."
            )

    else:

        st.info("Hourly forecast data is currently unavailable.")

    # Weather map

    st.subheader("📍 Weather Monitoring Locations")

    weather_map = weather_df[
        ["Latitude", "Longitude"]
    ].copy()

    weather_map.columns = ["latitude", "longitude"]

    st.map(weather_map, use_container_width=True)

    # Download weather data

    st.download_button(
        "⬇️ Download Weather Data CSV",
        data=weather_df.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="weather_monitoring.csv",
        mime="text/csv"
    )


# =========================================================
# EARTHQUAKE DASHBOARD
# =========================================================

st.header("🌐 Global Earthquake Monitoring")

st.caption(
    "Source: USGS global all-day earthquake feed. Earthquake events "
    "can be revised. This data cannot predict earthquakes."
)

if earthquake_df.empty:

    if not earthquake_error:
        st.info("No earthquake records were returned by the feed.")

else:

    earthquake_df["Magnitude"] = pd.to_numeric(
        earthquake_df["Magnitude"],
        errors="coerce"
    )

    earthquake_df["Depth (km)"] = pd.to_numeric(
        earthquake_df["Depth (km)"],
        errors="coerce"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Events in feed",
        len(earthquake_df)
    )

    magnitudes = earthquake_df["Magnitude"].dropna()

    col2.metric(
        "Largest magnitude",
        (
            f"{magnitudes.max():.1f}"
            if not magnitudes.empty
            else "N/A"
        )
    )

    col3.metric(
        "Events magnitude 4.0+",
        int((earthquake_df["Magnitude"] >= 4.0).sum())
    )

    # Magnitude filter

    minimum_magnitude = st.slider(
        "Minimum earthquake magnitude",
        min_value=0.0,
        max_value=9.0,
        value=4.0,
        step=0.5
    )

    filtered_quakes = earthquake_df[
        earthquake_df["Magnitude"].notna()
        &
        (
            earthquake_df["Magnitude"]
            >= minimum_magnitude
        )
    ].copy()

    st.write(
        f"Showing **{len(filtered_quakes)}** events with "
        f"magnitude ≥ {minimum_magnitude:.1f}."
    )

    if not filtered_quakes.empty:

        # Magnitude distribution

        magnitude_figure = px.histogram(
            filtered_quakes,
            x="Magnitude",
            nbins=20,
            title="Earthquake Magnitude Distribution"
        )

        st.plotly_chart(
            magnitude_figure,
            use_container_width=True
        )

        # Earthquake map

        st.subheader("📍 Earthquake Event Map")

        quake_map = filtered_quakes[
            ["Latitude", "Longitude"]
        ].copy()

        quake_map["Latitude"] = pd.to_numeric(
            quake_map["Latitude"],
            errors="coerce"
        )

        quake_map["Longitude"] = pd.to_numeric(
            quake_map["Longitude"],
            errors="coerce"
        )

        quake_map = quake_map.dropna()

        if not quake_map.empty:

            quake_map.columns = [
                "latitude",
                "longitude"
            ]

            st.map(
                quake_map,
                use_container_width=True
            )

        # Earthquake table

        st.subheader("Earthquake Event Records")

        st.dataframe(
            filtered_quakes[
                [
                    "Place",
                    "Magnitude",
                    "Time (IST)",
                    "Depth (km)",
                    "Status",
                    "Event URL",
                ]
            ].sort_values(
                "Magnitude",
                ascending=False,
                na_position="last"
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Event URL": st.column_config.LinkColumn(
                    "USGS Event Details"
                )
            }
        )

        # Download earthquake data

        st.download_button(
            "⬇️ Download Earthquake Data CSV",
            data=filtered_quakes.to_csv(
                index=False
            ).encode("utf-8"),
            file_name="earthquake_events.csv",
            mime="text/csv"
        )

    else:

        st.info(
            "No earthquake events meet the selected magnitude threshold."
        )


# =========================================================
# METHODOLOGY AND LIMITATIONS
# =========================================================

with st.expander(
    "ℹ️ Methodology, Data Sources and Limitations"
):

    st.markdown("""
    ### Data sources

    - **Weather:** Open-Meteo forecast API.
    - **Earthquakes:** USGS global all-day GeoJSON feed.

    ### Refresh behaviour

    - Dashboard reruns every 60 seconds.
    - Weather data is cached for 5 minutes.
    - Earthquake data is cached for 1 minute.
    - Use the sidebar refresh button to clear the caches.

    ### Prototype rainfall indicators

    - **High:** Forecast rainfall in the next 6 hours is at least 50 mm.
    - **Moderate:** Forecast rainfall in the next 6 hours is at least 20 mm,
      or maximum hourly precipitation probability in the next 24 hours is
      at least 70%.
    - **Lower:** Neither threshold is crossed.

    These are illustrative project thresholds, not validated meteorological
    criteria or official warnings. Forecasts can change and data sources can
    fail or be delayed. Current weather conditions may be model-derived.
    Earthquakes cannot be reliably predicted from this feed.

    Do not use this prototype to make emergency decisions.
    """)

st.caption(
    "Built as an educational Big Data Analytics project. "
    "Follow official government and disaster-management advisories "
    "during emergencies."
)