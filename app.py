import streamlit as st
import requests
import json
import google.generativeai as genai

st.set_page_config(page_title="Production MCP Travel Agent", layout="centered")
st.title("🌍 Production MCP Travel Agent")

# ---------------- KEYS ----------------
st.sidebar.header("🔑 API Keys")

maps_api = st.sidebar.text_input("Google Maps API Key", type="password")
places_api = st.sidebar.text_input("Google Places API Key", type="password")
gemini_api = st.sidebar.text_input("Gemini API Key", type="password")

model_name = st.sidebar.selectbox(
    "Model",
    ["gemini-2.5-flash", "gemini-1.5-flash"]
)

if gemini_api:
    genai.configure(api_key=gemini_api)

# ---------------- TOOLS ----------------
def search_places(city):
    query = f"top tourist attractions in {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": places_api}
    res = requests.get(url, params=params).json()

    return [{
        "name": p.get("name"),
        "rating": p.get("rating"),
        "address": p.get("formatted_address")
    } for p in res.get("results", [])[:8]]


def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origin, "destination": destination, "key": maps_api}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return None

    leg = res["routes"][0]["legs"][0]
    return {
        "distance": leg["distance"]["text"],
        "duration": leg["duration"]["text"]
    }

# ---------------- LLM CALL ----------------
def llm(prompt):
    model = genai.GenerativeModel(model_name)
    return model.generate_content(prompt).text

# ---------------- MAIN PIPELINE ----------------
def run_agent(user_query):

    # -------- STEP 1: EXTRACT CITY --------
    city_prompt = f"""
Extract the main travel city from this query:

{user_query}

Return ONLY the city name.
"""
    city = llm(city_prompt).strip()

    st.info(f"📍 Detected city: {city}")

    # -------- STEP 2: FETCH PLACES --------
    places = search_places(city)

    st.info("🔧 Fetching places from Google Maps...")
    st.json(places)

    # -------- STEP 3: SELECT TOP PLACES --------
    plan_prompt = f"""
User query:
{user_query}

Places:
{places}

Select best 5 places considering:
- ratings
- variety
- travel feasibility

Return ONLY list of place names.
"""
    selected = llm(plan_prompt)

    selected_places = [p.strip("- ").strip() for p in selected.split("\n") if p.strip()]

    # -------- STEP 4: DISTANCE MATRIX --------
    st.info("🚗 Calculating travel distances...")

    routes = []
    base = None

    # detect hotel if mentioned
    if "taj" in user_query.lower():
        base = "Taj Bangalore"

    for place in selected_places:
        origin = base if base else selected_places[0]
        dist = get_distance(origin, place)

        if dist:
            routes.append({
                "from": origin,
                "to": place,
                "distance": dist["distance"],
                "duration": dist["duration"]
            })

    st.json(routes)

    # -------- STEP 5: FINAL SYNTHESIS --------
    final_prompt = f"""
User query:
{user_query}

City:
{city}

Selected places:
{selected_places}

Travel data:
{routes}

Create a FINAL travel plan:

- Top 5 places with short explanation
- 2-day itinerary
- Travel times from base location
- Why these places are good
- Keep it clean and human-friendly
"""

    return llm(final_prompt)


# ---------------- UI ----------------
query = st.text_area(
    "Ask your travel question",
    placeholder="Tell me a 2 day trip to Shimla in March"
)

if st.button("Run Agent"):
    if not (maps_api and places_api and gemini_api):
        st.error("Please enter all API keys")
    else:
        st.info("🤖 Running production MCP agent...")
        result = run_agent(query)

        st.markdown("### 🧭 Final Travel Plan")
        st.write(result)
