import os
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
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

#llm = ChatOllama(model="llama3.1", num_ctx=2048, base_url="http://host.docker.internal:11434")
#llm = ChatOllama(model="llama3.1", base_url="http://host.docker.internal:11434")
tools = [system_control]

# Database configuration
# - Inside Docker: host 'db', port 5432
# - Local Dev: host 'localhost', port 5433
default_db_url = "postgresql+psycopg2://postgres:postgres@localhost:5433/paragon"
pg_uri = os.getenv("DATABASE_URL", default_db_url)

if pg_uri.startswith("postgresql://"):
    pg_uri = pg_uri.replace("postgresql://", "postgresql+psycopg2://", 1)

db = SQLDatabase.from_uri(pg_uri)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

template = """You are a specialized Logistics Data Analyst for the 'Routing App'.

SCOPE RULES:
1. Your domain includes: Ships, Trucks, Delivery Orders, Products, Locations, and Distribution Centers.
2. Questions about categories, counts, or details of the items above ARE allowed.
3. If the user asks about completely unrelated topics (e.g., cooking, politics, general trivia), politely refuse in Indonesian.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

You have access to the following tools:
{tools}

Use the following format strictly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be EXACTLY one of [{tool_names}]. DO NOT append `()` to the action name.
Action Input: the input to the action (can be empty string)
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

CRITICAL: After providing Action and Action Input, you MUST STOP and wait. DO NOT invent an Observation. The system will provide the Observation.

CATALOG OF AVAILABLE PAGES & ACTIONS:
Pages:
- dashboard: Main dashboard
- shipments_list: List of all shipments
- add_shipment: Form to add a new shipment
- edit_shipment: Form to edit shipment details
- delivery_orders_list: List of all delivery orders
- add_delivery_order: Form to add a new delivery order
- edit_delivery_order: Form to edit delivery order details
- products_line_list: List of all products lines
- add_product_line: Form to add a new product line
- edit_product_line: Form to edit product line details
- products_list: List of all products
- add_product: Form to add a new product
- edit_product: Form to edit product details
- customers_list: List of all customers
- add_customer: Form to add a new customer
- edit_customer: Form to edit customer details
- trucks_list: List of all trucks
- add_truck: Form to add a new truck
- edit_truck: Form to edit truck details
- locations_list: List of all locations
- add_location: Form to add a new location
- edit_location: Form to edit location details
- users_list: List of all users
- add_user: Form to add a new user
- edit_user: Form to edit user details
- roles_list: List of all roles
- add_role: Form to add a new role
- edit_role: Form to edit role details

Actions:
- view_trucks: View list of trucks
- add_new_truck: Add a new truck
- edit_existing_truck: Edit an existing truck
- view_orders: View list of delivery orders
- add_new_order: Add a new delivery order
- edit_existing_order: Edit an existing delivery order
- view_locations: View list of locations
- add_new_location: Add a new location
- edit_existing_location: Edit an existing location
- view_dashboard: View dashboard

EXECUTION RULES:
- If the user wants to "view," "open," or "show," use action_type='NAVIGATE'.
- If the user wants to "add," "create," or "input," use action_type='ACTION'.

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

PROMPT = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
    template=template
)

agent_executor = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
    prompt=PROMPT,
    extra_tools=tools,
    agent_executor_kwargs={"return_intermediate_steps": True, "handle_parsing_errors": True}
)

class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        response = agent_executor.invoke(request.query)

        # debug
        print("AI response:", response)
        
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
                        import json
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
                break
                
        if not reply_text and command_payload:
            reply_text = "Baik, saya akan mengarahkan Anda ke halaman truk."

        return {
            "reply": reply_text,
            "command": command_payload
        }
    except Exception as e:
        return {"error": str(e)}