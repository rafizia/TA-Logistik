import os
import re
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
from langchain.tools import tool
from sqlalchemy import text
from prompt_template import AGENT_TEMPLATE

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()

@app.on_event("startup")
async def startup():
    print("AI Service is starting up...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
# - Inside Docker: host 'db', port 5432
# - Local Dev: host 'localhost', port 5433
default_db_url = "postgresql+psycopg2://postgres:postgres@localhost:5433/paragon"
pg_uri = os.getenv("DATABASE_URL", default_db_url)

if pg_uri.startswith("postgresql://"):
    pg_uri = pg_uri.replace("postgresql://", "postgresql+psycopg2://", 1)

db = SQLDatabase.from_uri(pg_uri)

@tool
def system_control(query: str) -> str:
    """
    VERY IMPORTANT: Use this tool for navigation or system actions.
    The Action Input MUST be a valid JSON string with 'action_type' and 'target_page'.
    Example Action Input: {"action_type": "NAVIGATE", "target_page": "trucks_list"}
    """
    try:
        data = json.loads(query)
        action_type = data.get("action_type", "NAVIGATE")
        target_page = data.get("target_page", "dashboard")
        return f"SUCCESS:{action_type}:{target_page}"
    except Exception:
        return f"SUCCESS:NAVIGATE:{query}"

@tool
def get_available_options(query: str = "") -> str:
    """
    Fetches available dropdown options for trucks and locations:
    - Vehicle Types (name and id)
    - Distribution Centers (name and id)
    - Customers (name and id)
    - Valid Statuses (TruckFirstStatus and TruckSecondStatus)
    Use this before creating or updating a truck or location to ensure you have the correct IDs and enum values.
    """
    try:
        # Get Vehicle Types
        types = db.run("SELECT id, name FROM truck_type")
        # Get DCs
        dcs = db.run("SELECT id, name FROM dc")
        # Get Customers
        customers = db.run("SELECT id, name FROM customer")
        
        # Static Statuses (extracted from DB earlier)
        first_statuses = ["AVAILABLE", "UNAVAILABLE"]
        second_statuses = ["ON_DELIVERY", "OUT_OF_STOCK", "ARCHIVE", "MAINTENANCE", "LEGAL"]
        
        result = {
            "vehicle_types": types,
            "distribution_centers": dcs,
            "customers": customers,
            "first_statuses": first_statuses,
            "second_statuses": second_statuses
        }
        return json.dumps(result)
    except Exception as e:
        return f"Error fetching options: {str(e)}"

PLATE_NUMBER_REGEX = re.compile(
    r'^[A-Z]{1,2}\s[0-9]{1,4}\s[A-Z]{1,3}$',
    re.IGNORECASE
)

def validate_plate_number(plate: str) -> tuple[bool, str]:
    plate_stripped = plate.strip()
    if not PLATE_NUMBER_REGEX.match(plate_stripped):
        return False, (
            f"Format nomor plat '{plate_stripped}' tidak valid. "
        )
    return True, ""

@tool
def manage_truck(query: str) -> str:
    """
    Use this tool for CREATE, UPDATE, or DELETE operations on truck entities.
    Input must be a JSON string with:
    - action: 'CREATE', 'UPDATE', or 'DELETE'
    - data: dictionary of truck fields.
    For CREATE: requires plate_number, type_id, dc_id, first_status, created_by. Optional: max_individual_capacity_volume.
      IMPORTANT: plate_number MUST follow Indonesian license plate format:
      [1-2 letter area code] [1-4 digit registration number] [1-3 letter series code]
      Each part separated by a SINGLE SPACE. Example: "B 1234 RFS", "AB 12 CD".
    For UPDATE/DELETE: requires plate_number or id.
    Example: {"action": "CREATE", "data": {"plate_number": "B 1234 XY", "type_id": 1, "dc_id": 1, "first_status": "AVAILABLE", "created_by": "AI_Agent", "max_individual_capacity_volume": 150000}}
    """
    try:
        payload = json.loads(query)
        action = payload.get("action").upper()
        data = payload.get("data", {})
        
        if action == "CREATE":
            # Basic validation
            required = ["plate_number", "type_id", "dc_id", "first_status"]
            for field in required:
                if field not in data:
                    return f"ERROR: Missing required field '{field}' for CREATE."
            
            # Validasi format plat nomor
            plate = data.get("plate_number", "")
            is_valid, error_msg = validate_plate_number(plate)
            if not is_valid:
                return f"ERROR: {error_msg}"
            data["plate_number"] = plate.strip().upper()
            
            return f"SUCCESS:PREFILL:add_truck:{json.dumps(data)}"
            
        elif action == "UPDATE":
            identifier = data.get("plate_number") or data.get("id")
            if not identifier:
                return "ERROR: Missing plate_number or id for UPDATE."
            
            # Cari id truk berdasarkan plat nomor
            truck_id = data.get("id")
            if not truck_id:
                sql = text("SELECT id FROM truck WHERE plate_number = :plate")
                with db._engine.connect() as conn:
                    result = conn.execute(sql, {"plate": identifier}).fetchone()
                    if not result:
                        return f"ERROR: Truck with plate {identifier} not found."
                    truck_id = result[0]
            
            # Prepare data for pre-fill
            prefill_data = {
                "Id": truck_id,
                "prefill": {
                    "dc_id": data.get("dc_id"),
                    "status": data.get("status") or data.get("first_status") or data.get("second_status") or data.get("third_status")
                }
            }
            return f"SUCCESS:PREFILL:edit_truck:{json.dumps(prefill_data)}"
            
        elif action == "DELETE":
            identifier = data.get("plate_number") or data.get("id")
            if not identifier:
                return "ERROR: Missing plate_number or id for DELETE."
            
            where_clause = "plate_number = :ident" if data.get("plate_number") else "id = :ident"
            sql = text(f"DELETE FROM truck WHERE {where_clause}")
            with db._engine.connect() as conn:
                conn.execute(sql, {"ident": identifier})
                conn.commit()
            return f"SUCCESS: Truck {identifier} deleted successfully."
            
        return "ERROR: Invalid action."
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool
def manage_location(query: str) -> str:
    """
    Use this tool for CREATE, UPDATE, or DELETE operations on location entities.
    Input must be a JSON string with:
    - action: 'CREATE', 'UPDATE', or 'DELETE'
    - data: dictionary of location fields.
    For CREATE: requires address, provinsi, kabupaten_kota, kecamatan, desa_kelurahan, kode_pos, open_hour, close_hour, customer_id, dc_id.
    Note: Always use `get_available_options` first to find the correct `customer_id` and `dc_id` from names like "PT ABC" or "DC Jakarta".
    For UPDATE/DELETE: requires id.
    Example: {"action": "CREATE", "data": {"address": "Jl. Merdeka 1", "provinsi": "DKI Jakarta", "kabupaten_kota": "Jakarta Pusat", "kecamatan": "Gambir", "desa_kelurahan": "Gambir", "kode_pos": "10110", "open_hour": "08:00", "close_hour": "17:00", "customer_id": 1, "dc_id": 1}}
    """
    try:
        payload = json.loads(query)
        action = payload.get("action").upper()
        data = payload.get("data", {})
        
        if action == "CREATE":
            # Basic validation
            required = ["address", "provinsi", "kabupaten_kota", "kecamatan", "desa_kelurahan", "kode_pos", "open_hour", "close_hour", "customer_id", "dc_id"]
            for field in required:
                if field not in data:
                    return f"ERROR: Missing required field '{field}' for CREATE."
            
            return f"SUCCESS:PREFILL:add_location:{json.dumps(data)}"
            
        elif action == "UPDATE":
            location_id = data.get("id")
            if not location_id:
                return "ERROR: Missing id for UPDATE."
            
            prefill_data = {
                "Id": location_id,
                "prefill": data
            }
            return f"SUCCESS:PREFILL:edit_location:{json.dumps(prefill_data)}"
            
        elif action == "DELETE":
            identifier = data.get("id")
            if not identifier:
                return "ERROR: Missing id for DELETE."
            
            sql = text(f"DELETE FROM location WHERE id = :ident")
            with db._engine.connect() as conn:
                conn.execute(sql, {"ident": identifier})
                conn.commit()
            return f"SUCCESS: Location {identifier} deleted successfully."
            
        return "ERROR: Invalid action."
    except Exception as e:
        return f"ERROR: {str(e)}"

_ollama_url = os.getenv("OLLAMA_BASE_URL", "http://e2e_logistics_ollama:11434")
_ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
llm = ChatOllama(
    model=_ollama_model,
    base_url=_ollama_url,
)
tools = [system_control, get_available_options, manage_truck, manage_location]

toolkit = SQLDatabaseToolkit(db=db, llm=llm)

PROMPT = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names", "history"],
    template=AGENT_TEMPLATE
)

agent_executor = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
    prompt=PROMPT,
    extra_tools=tools,
    max_iterations=30,
    max_execution_time=120,
    early_stopping_method="force",
    agent_executor_kwargs={
        "return_intermediate_steps": True, 
        "handle_parsing_errors": True,
    }
)

class ChatRequest(BaseModel):
    query: str
    history: list = []

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        # Format history for the prompt
        history_text = ""
        for msg in request.history:
            sender = "User" if msg.get("sender") == "user" else "AI"
            history_text += f"{sender}: {msg.get('text')}\n"
            
        response = await agent_executor.ainvoke({
            "input": request.query,
            "history": history_text
        })
        
        reply_text = response.get('output', '')
        command_payload = None
        
        steps = response.get('intermediate_steps', [])
        for action, observation in steps:
            if getattr(action, "tool", None) == "system_control":
                tool_input = action.tool_input
                if isinstance(tool_input, dict):
                    action_type = tool_input.get("action_type", "NAVIGATE")
                    target = tool_input.get("target_page", "dashboard")
                else:
                    try:
                        parsed = json.loads(tool_input)
                        action_type = parsed.get("action_type", "NAVIGATE")
                        target = parsed.get("target_page", "dashboard")
                    except Exception:
                        action_type = "NAVIGATE"
                        target = str(tool_input).strip()
                        
                command_payload = {
                     "type": action_type,
                     "target": target
                }
            elif "SUCCESS:PREFILL:" in str(observation):
                obs_str = str(observation)
                try:
                    parts = obs_str.split(":", 3)
                    target = parts[2] if len(parts) > 2 else "dashboard"
                    
                    json_start = obs_str.find("{")
                    json_end = obs_str.rfind("}")
                    if json_start != -1 and json_end != -1:
                        json_str = obs_str[json_start:json_end+1]
                        payload_data = json.loads(json_str)
                    else:
                        payload_data = {}
                        
                    command_payload = {
                        "type": "PREFILL",
                        "target": target,
                        "data": payload_data
                    }
                except Exception as e:
                    print(f"Error parsing PREFILL observation: {e}")
                    command_payload = None
            
            if command_payload:
                break
                
        if not reply_text and command_payload:
            reply_text = "Baik, saya akan mengarahkan Anda ke halaman yang relevan."

        return {
            "reply": reply_text,
            "command": command_payload
        }
    except Exception as e:
        print(f"[ERROR] chat_with_ai: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}