import streamlit as st
import requests
import itertools
import google.generativeai as genai

st.set_page_config(page_title="MCP + LLM Travel Assistant", layout="centered")
st.title("MCP + LLM Travel Assistant")

# ---------------- SIDEBAR ----------------
st.sidebar.header("🔑 API Keys")

maps_api = st.sidebar.text_input("Google Maps API Key", type="password")
gemini_api = st.sidebar.text_input("Gemini API Key", type="password")

model_name = st.sidebar.selectbox(
    "Gemini Model",
    ["gemini-2.5-flash", "gemini-1.5-flash"]
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

# ---------------- MATRIX ----------------
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

# ---------------- LLM ----------------
def analyze_with_llm(locations, route, distance):
    model = genai.GenerativeModel(model_name)

    prompt = f"""
User is traveling in Bangalore with elderly people.

Locations: {locations}
Optimized route: {route}
Total distance: {distance:.2f} km

Suggest:
- Best places to actually visit (reduce travel if needed)
- Comfortable order
- Why suitable for elderly

Keep it simple.
"""

    response = model.generate_content(prompt)
    return response.text

# ---------------- UI ----------------

st.header("Route Optimization + AI Advice")

locations_input = st.text_input(
    "Enter places",
    placeholder="Lalbagh, Cubbon Park, Wonderla"
)

if st.button("Run"):
    if not maps_api:
        st.error("Enter Google Maps API key")
    else:
        locations = [l.strip() for l in locations_input.split(",") if l.strip()]

        if len(locations) < 3:
            st.warning("Enter at least 3 locations")
        else:
            st.info("MCP: Fetching distances from Google Maps...")
            matrix = build_matrix(locations)

            route, distance = tsp_solver(locations, matrix)

            if route:
                st.success(f"Optimal Route (TSP): {' → '.join(route)}")
                st.success(f"Total Distance: {distance:.2f} km")

                if gemini_api:
                    st.info("LLM: Analyzing for elderly-friendly travel...")
                    analysis = analyze_with_llm(locations, route, distance)

                    st.markdown("### 🤖 Gemini Recommendation")
                    st.write(analysis)
                else:
                    st.warning("Add Gemini API key for AI suggestions")
            else:
                st.error("Failed to compute route")
