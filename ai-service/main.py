import os
import json
from sqlalchemy import text
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate
from prompt_template import AGENT_TEMPLATE
from prompt_template_fewshot import AGENT_TEMPLATE_FEWSHOT
from tools import use_tools
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model
from langchain_core.messages import RemoveMessage, trim_messages as lc_trim_messages
from typing import Any, Optional
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.checkpoint.memory import InMemorySaver

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

'''
_ollama_url   = os.getenv("OLLAMA_BASE_URL", "http://e2e_logistics_ollama:11434")
_ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
llm = ChatOllama(model=_ollama_model, base_url=_ollama_url, num_ctx=4096, keep_alive="5m")

'''
# Google Gemini API configuration:
google_api_key = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=google_api_key,
    temperature=0
)


tools   = use_tools(db)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

PROMPT = PromptTemplate(
    input_variables=["input", "agent_scratchpad", "tools", "tool_names", "history"],
    template=AGENT_TEMPLATE
)

all_tools = tools + toolkit.get_tools()
sys_prompt = AGENT_TEMPLATE_FEWSHOT
memory = InMemorySaver()

@before_model
def trim_messages(state: AgentState, runtime: Any) -> dict | None:
    """Keep only the messages that fit inside the context window based on max tokens."""
    messages = state.get("messages", [])
    
    trimmed_messages = lc_trim_messages(
        messages,
        max_tokens=80000,
        strategy="last",
        token_counter="approximate",
        start_on="human",
        include_system=True,
        allow_partial=False
    )

    if len(trimmed_messages) == len(messages):
        return None

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *trimmed_messages
        ]
    }

agent = create_agent(
    model=llm,
    tools=all_tools,
    system_prompt=sys_prompt,
    middleware=[trim_messages],
    checkpointer=memory,
    debug=False
)

class UserContext(BaseModel):
    role: Optional[str] = None
    dc_id: Optional[int] = None
    dc_name: Optional[str] = None
    token: Optional[str] = None

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"
    user_context: Optional[UserContext] = None

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        from context import request_token, request_dc_id
        if request.user_context and request.user_context.token:
            request_token.set(request.user_context.token)
        else:
            request_token.set("")
        request_dc_id.set(request.user_context.dc_id if request.user_context else None)
        input_messages = [{"role": "user", "content": request.query}]

        # Inject user context (DC info) as a system message prefix
        if request.user_context:
            ctx = request.user_context
            if ctx.dc_id:
                dc_info_parts = [f"dc_id={ctx.dc_id}"]
                if ctx.dc_name:
                    dc_info_parts.append(f"dc_name='{ctx.dc_name}'")
                else:
                    try:
                        sql_dc = text("SELECT name FROM dc WHERE id = :dc_id")
                        with db._engine.connect() as conn:
                            row = conn.execute(sql_dc, {"dc_id": ctx.dc_id}).fetchone()
                        if row:
                            dc_info_parts.append(f"dc_name='{row[0]}'")
                    except Exception:
                        pass
                dc_context_msg = (
                    f"[SYSTEM CONTEXT] The current user is logged in as role '{ctx.role or 'Admin DC'}'. "
                    f"Their Distribution Center (DC) is fixed and CANNOT be changed: {', '.join(dc_info_parts)}. "
                    f"When creating a delivery order, you MUST use this dc_id automatically. "
                    f"Do NOT ask the user about which DC to use. The dc_id is already determined."
                )
            else:
                dc_context_msg = (
                    f"[SYSTEM CONTEXT] The current user is logged in as role '{ctx.role or 'Super'}'. "
                    f"They do NOT have a fixed Distribution Center (DC). "
                    f"When creating a delivery order, you MUST ask the user which DC they want to use."
                )

            input_messages = [
                {"role": "system", "content": dc_context_msg},
                {"role": "user", "content": request.query}
            ]

        config = {"configurable": {"thread_id": request.session_id}}

        response = await agent.ainvoke(
            {"messages": input_messages}, 
            config=config
        )

        # 🟢 LOG TRACE BERPIKIR & TOOL CALL KE TERMINAL
        print("\n" + "="*50)
        print("🧠 --- TRACE EKSEKUSI AI ---")
        for msg in response.get("messages", []):
            if msg.type == "ai":
                if getattr(msg, "tool_calls", None):
                    print(f"🤖 [AI CALL TOOL]: {msg.tool_calls}")
                elif msg.content:
                    print(f"🤖 [AI THINKING/REPLY]: {msg.content}")
            elif msg.type == "tool":
                print(f"🛠️ [TOOL RESULT ({msg.name})]: {msg.content}")
        print("="*50 + "\n")
        
        final_messages = response.get("messages", [])
        reply_text = ""
        command_payload = None

        def _content_to_str(content) -> str:
            """Normalise AI message content (str | list[dict]) → plain string."""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict):
                        parts.append(part.get("text") or str(part))
                    else:
                        parts.append(str(part))
                return "".join(parts)
            return str(content)
        
        # Iterate over messages in reverse to find the latest tool call or final answer
        for msg in reversed(final_messages):
            if msg.type == "tool" and msg.name in ["system_control", "manage_truck", "manage_location", "automate_shipment", "manage_delivery_order"]:
                # tool returned a direct dict or stringified JSON
                try:
                    output = msg.content
                    if isinstance(output, str):
                        import ast
                        try:
                            output = json.loads(output)
                        except json.JSONDecodeError:
                            output = ast.literal_eval(output)
                    
                    if isinstance(output, dict):
                        ui_action = output.get("ui_action")
                        if ui_action and ui_action != "ERROR":
                            reply_text = output.get("message", "Baik, saya akan memproses permintaan Anda.")
                            command_payload = {
                                "type": ui_action,
                                "target": output.get("target", "dashboard")
                            }
                            if "entity_id" in output and output["entity_id"] is not None:
                                command_payload["data"] = {"id": output["entity_id"], "Id": output["entity_id"]}
                            elif "data" in output and output["data"] is not None:
                                command_payload["data"] = output.get("data")
                            break
                        elif ui_action == "ERROR":
                            if not reply_text:
                                reply_text = output.get("message", "Terjadi kesalahan saat memproses data.")
                            command_payload = None
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
                reply_text = _content_to_str(msg.content)

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

