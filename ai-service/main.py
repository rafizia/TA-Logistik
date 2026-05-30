import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
from prompt_template import AGENT_TEMPLATE
from tools import use_tools
from langchain.agents import create_agent

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI()

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

_ollama_url   = os.getenv("OLLAMA_BASE_URL", "http://e2e_logistics_ollama:11434")
_ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
llm = ChatOllama(model=_ollama_model, base_url=_ollama_url)

tools   = use_tools(db)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

PROMPT = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names", "history"],
    template=AGENT_TEMPLATE
)

all_tools = tools + toolkit.get_tools()
sys_prompt = AGENT_TEMPLATE

agent = create_agent(
    model=llm,
    tools=all_tools,
    system_prompt=sys_prompt,
    debug=True
)

'''
agent_executor = AgentExecutor(
    agent=agent,
    tools=all_tools,
    verbose=True,
    max_iterations=30,
    max_execution_time=120,
    early_stopping_method="force",
    handle_parsing_errors=True,
    return_intermediate_steps=True
)'''

class ChatRequest(BaseModel):
    query: str
    history: list = []

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        # Format history into messages
        messages = []
        for msg in request.history:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text")})
            
        messages.append({"role": "user", "content": request.query})

        # create_agent
        response = await agent.ainvoke({"messages": messages})
        
        final_messages = response.get("messages", [])     
        reply_text = ""
        command_payload = None
        
        # Iterate over messages in reverse to find the latest tool call or final answer
        for msg in reversed(final_messages):
            if msg.type == "tool" and msg.name in ["system_control", "manage_truck", "manage_location", "automate_shipment"]:
                # tool returned a direct dict or stringified JSON
                try:
                    output = msg.content
                    if isinstance(output, str):
                        output = json.loads(output)
                    
                    if isinstance(output, dict):
                        ui_action = output.get("ui_action")
                        if ui_action and ui_action != "ERROR":
                            reply_text = output.get("message", "Baik, saya akan memproses permintaan Anda.")
                            command_payload = {
                                "type": ui_action,
                                "target": output.get("target", "dashboard")
                            }
                            if "data" in output:
                                command_payload["data"] = output.get("data")
                            break
                        elif ui_action == "ERROR":
                            reply_text = output.get("message", "Terjadi kesalahan saat memproses data.")
                            command_payload = None
                            break
                except Exception:
                    pass
            elif msg.type == "tool" and "SUCCESS:PREFILL:" in str(msg.content):
                # Fallback for PREFILL tools
                try:
                    obs_str = str(msg.content).strip()
                    parts = obs_str.split(":", 3)
                    target = parts[2] if len(parts) > 2 else "dashboard"
                    json_str = parts[3].strip() if len(parts) > 3 else ""
                    payload_data = json.loads(json_str) if json_str else {}
                    
                    command_payload = {
                        "type": "PREFILL",
                        "target": target,
                        "data": payload_data
                    }
                    reply_text = "Baik, saya akan menyiapkan data yang Anda minta."
                    break
                except Exception:
                    pass
            elif msg.type == "ai" and msg.content and not command_payload:
                # Store the last AI message as the reply text, unless we already found a tool command
                if not reply_text:
                    reply_text = msg.content

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