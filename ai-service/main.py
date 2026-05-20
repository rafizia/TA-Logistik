import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
from prompt_template import AGENT_TEMPLATE
from tools import use_tools

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

_ollama_url   = os.getenv("OLLAMA_BASE_URL", "http://e2e_logistics_ollama:11434")
_ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
llm = ChatOllama(model=_ollama_model, base_url=_ollama_url)

tools   = use_tools(db)
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