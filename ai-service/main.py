from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import PromptTemplate

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatOllama(model="llama3.2", num_ctx=2048, base_url="http://152.118.31.57:11434")

pg_uri = "postgresql+psycopg2://postgres:postgres@db:5432/paragon"
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

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

custom_suffix = """
When you find a list of items from the database, please present them as a clean, 
comma-separated sentence without brackets or quotes. 
Example: "The categories are: cereals, salads, and desserts."
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
    handle_parsing_errors=True,
)

class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        response = agent_executor.invoke(request.query)
        return {"reply": response.get('output')}
    except Exception as e:
        return {"error": str(e)}