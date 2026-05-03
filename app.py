import streamlit as st
import requests
import itertools
import os

# Gemini
import google.generativeai as genai

st.set_page_config(page_title="MCP + LLM Travel Assistant", layout="centered")
st.title("MCP + LLM Travel Assistant")

# ---------------- USER CONFIG ----------------
st.sidebar.header("🔑 API Configuration")

maps_api = st.sidebar.text_input("Google Maps API Key", type="password")
gemini_api = st.sidebar.text_input("Gemini API Key", type="password")

model_name = st.sidebar.selectbox(
    "Select Gemini Model",
    ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
)

if gemini_api:
    genai.configure(api_key=gemini_api)

# ---------------- MCP TOOL ----------------
def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "key": maps_api
    }

    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return None

    leg = res["routes"][0]["legs"][0]

    distance_text = leg["distance"]["text"]
    distance_val = float(distance_text.split()[0].replace(",", ""))

    return {
        "distance_km": distance_val,
        "distance_text": distance_text,
        "duration": leg["duration"]["text"]
    }

# ---------------- BUILD MATRIX ----------------
def build_matrix(locations):
    matrix = {}
    for i in locations:
        matrix[i] = {}
        for j in locations:
            if i != j:
                data = get_distance(i, j)
                matrix[i][j] = data["distance_km"] if data else float("inf")
    return matrix

# ---------------- TSP ----------------
def tsp_solver(locations, matrix):
    best_route = None
    min_distance = float("inf")

    for perm in itertools.permutations(locations):
        total = 0
        valid = True

        for i in range(len(perm) - 1):
            d = matrix[perm[i]].get(perm[i+1], float("inf"))
            if d == float("inf"):
                valid = False
                break
            total += d

        if valid and total < min_distance:
            min_distance = total
            best_route = perm

    return best_route, min_distance

# ---------------- LLM ANALYSIS ----------------
def analyze_with_llm(locations, route, distance):
    try:
        model = genai.GenerativeModel(model_name)

        prompt = f"""
You are a travel assistant.

User wants to visit these locations in Bangalore:
{locations}

Optimized route is:
{route}

Total distance: {distance:.2f} km

User condition:
- Traveling with elderly people
- Avoid long travel
- Prefer less crowded, easy-access places

Tasks:
1. Suggest best subset of places (if needed)
2. Recommend order of visit
3. Explain why it is suitable for elderly
4. Keep response simple and practical
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"LLM Error: {str(e)}"

# ---------------- UI ----------------

# ---- BASIC DISTANCE ----
st.header("1. Distance & Travel Info")

origin = st.text_input("Origin", placeholder="Bangalore")
destination = st.text_input("Destination", placeholder="Mysore")

if st.button("Get Distance"):
    if not maps_api:
        st.error("Enter Google Maps API key")
    else:
        result = get_distance(origin, destination)
        if result:
            st.success(f"Distance: {result['distance_text']}")
            st.success(f"Duration: {result['duration']}")
        else:
            st.error("Error fetching data")

# ---- ROUTE OPTIMIZATION ----
st.header("2. Optimize Route + LLM Advice")

locations_input = st.text_input(
    "Enter places (comma separated)",
    placeholder="Lalbagh, Cubbon Park, Wonderla"
)

if st.button("Optimize + Analyze"):
    if not maps_api:
        st.error("Enter Google Maps API key")
    else:
        locations = [l.strip() for l in locations_input.split(",") if l.strip()]

        if len(locations) < 3:
            st.warning("Enter at least 3 locations")
        else:
            st.info("Fetching distances via MCP...")
            matrix = build_matrix(locations)

            route, distance = tsp_solver(locations, matrix)

            if route:
                st.success(f"Best Route: {' → '.join(route)}")
                st.success(f"Total Distance: {distance:.2f} km")

                if gemini_api:
                    st.info("Running LLM analysis...")
                    analysis = analyze_with_llm(locations, route, distance)
                    st.markdown("### 🤖 LLM Recommendation")
                    st.write(analysis)
                else:
                    st.warning("Add Gemini API key for AI recommendations")
            else:
                st.error("Route optimization failed")
