import streamlit as st
import requests
import json
import re
import google.generativeai as genai

st.set_page_config(page_title="True MCP Agent", layout="centered")
st.title("Conversational MCP Agent (Maps + Gemini)")

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
def search_places(query):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": places_api}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return []

    return [{
        "name": p["name"],
        "rating": p.get("rating"),
        "address": p.get("formatted_address")
    } for p in res["results"][:5]]

def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origin, "destination": destination, "key": maps_api}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return {}

    leg = res["routes"][0]["legs"][0]

    return {
        "distance": leg["distance"]["text"],
        "duration": leg["duration"]["text"]
    }

# ---------------- AGENT ----------------
SYSTEM_PROMPT = """
You are a travel planning assistant with tool access.

TOOLS:

1. search_places
Input:
{ "query": "..." }

2. get_distance
Input:
{ "origin": "...", "destination": "..." }

RULES:
- You can call tools multiple times
- Plan step-by-step
- Build itinerary gradually
- Always use real data
- When done, provide final answer

TO CALL TOOL:
Return ONLY JSON:
{
  "action": "tool_name",
  "input": {...}
}

TO FINISH:
Return normal text (no JSON)
"""

def extract_json(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

def run_agent(query):
    model = genai.GenerativeModel(model_name)

    messages = [{"role": "user", "content": query}]

    for step in range(5):  # allow multiple tool steps
        prompt = SYSTEM_PROMPT + "\n\n" + json.dumps(messages)

        response = model.generate_content(prompt)
        text = response.text

        action = extract_json(text)

        if not action:
            return text  # final answer

        tool = action.get("action")
        inp = action.get("input", {})

        st.info(f"🔧 Tool: {tool} → {inp}")

        # execute tool
        if tool == "search_places":
            result = search_places(inp.get("query"))

        elif tool == "get_distance":
            result = get_distance(
                inp.get("origin"),
                inp.get("destination")
            )

        else:
            result = {"error": "unknown tool"}

        st.json(result)

        # feed back result
        messages.append({
            "role": "assistant",
            "content": text
        })
        messages.append({
            "role": "user",
            "content": f"Tool result: {result}"
        })

    return "Max steps reached"

# ---------------- UI ----------------
query = st.text_area(
    "Ask your travel question",
    placeholder="I want to travel to Bangalore in May from Taj Bangalore..."
)

if st.button("Run Agent"):
    if not (maps_api and places_api and gemini_api):
        st.error("Enter all API keys")
    else:
        st.info("🤖 Running multi-step MCP agent...")
        answer = run_agent(query)

        st.markdown("### 🤖 Final Plan")
        st.write(answer)
