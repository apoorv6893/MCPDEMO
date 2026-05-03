import streamlit as st
import requests
import itertools
import json
import re
import google.generativeai as genai

st.set_page_config(page_title="MCP Agent: Maps + Gemini", layout="centered")
st.title("MCP Agent: Maps + Gemini")

# ---------------- SIDEBAR ----------------
st.sidebar.header("🔑 API Keys")
maps_api = st.sidebar.text_input("Google Maps API Key", type="password")
places_api = st.sidebar.text_input("Google Places API Key (optional)", type="password")
gemini_api = st.sidebar.text_input("Gemini API Key", type="password")

model_name = st.sidebar.selectbox(
    "Gemini Model",
    ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
)

if gemini_api:
    genai.configure(api_key=gemini_api)

# ---------------- MCP TOOLS ----------------
def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origin, "destination": destination, "key": maps_api}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return {"error": res.get("status")}

    leg = res["routes"][0]["legs"][0]
    distance_text = leg["distance"]["text"]
    distance_val = float(distance_text.split()[0].replace(",", ""))

    return {
        "distance_km": distance_val,
        "distance_text": distance_text,
        "duration": leg["duration"]["text"]
    }

def search_places(query):
    if not places_api:
        return {"error": "Places API key missing"}

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": places_api}
    res = requests.get(url, params=params).json()

    if res.get("status") != "OK":
        return {"error": res.get("status")}

    return [{"name": p["name"], "address": p.get("formatted_address", "")}
            for p in res["results"][:5]]

# ---------------- TSP (optional utility) ----------------
def build_matrix(locations):
    matrix = {}
    for i in locations:
        matrix[i] = {}
        for j in locations:
            if i != j:
                data = get_distance(i, j)
                matrix[i][j] = data.get("distance_km", float("inf"))
    return matrix

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

# ---------------- AGENT (LLM + TOOLS) ----------------
SYSTEM_PROMPT = """
You are an AI travel assistant with access to tools.

You can call tools by responding ONLY with valid JSON in this format:
{
  "action": "tool_name",
  "input": { ... }
}

Available tools:
1. get_distance:
   input: { "origin": "...", "destination": "..." }

2. search_places:
   input: { "query": "..." }

Rules:
- If the user asks about distance, routes, or travel → use get_distance
- If user asks for places → use search_places
- If you already have enough info → respond normally (no JSON)
- After tool result is given, produce final answer in plain English
"""

def extract_json(text):
    """Extract JSON block from LLM output safely."""
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

def run_agent(user_query):
    model = genai.GenerativeModel(model_name)

    # Step 1: Ask model what to do
    first = model.generate_content(SYSTEM_PROMPT + "\nUser: " + user_query)
    action = extract_json(first.text)

    # If no tool needed → return answer
    if not action:
        return first.text

    tool_name = action.get("action")
    tool_input = action.get("input", {})

    # Step 2: Execute tool
    if tool_name == "get_distance":
        result = get_distance(tool_input.get("origin"), tool_input.get("destination"))

    elif tool_name == "search_places":
        result = search_places(tool_input.get("query"))

    else:
        return "Unknown tool requested."

    # Step 3: Send result back to LLM for final answer
    final_prompt = f"""
User query: {user_query}

Tool used: {tool_name}
Tool result: {result}

Now provide a helpful final answer.
"""

    final = model.generate_content(final_prompt)
    return final.text

# ---------------- UI ----------------
st.header("Ask AI (Agent Mode)")

query = st.text_area(
    "Enter your request",
    placeholder="e.g., Tell me places to visit for elderly in Bangalore\nor\nDistance between Bangalore and Mysore"
)

if st.button("Run Agent"):
    if not gemini_api:
        st.error("Please enter Gemini API key")
    else:
        st.info("🤖 Thinking + using tools (MCP)...")
        response = run_agent(query)

        st.markdown("### 🤖 Response")
        st.write(response)
