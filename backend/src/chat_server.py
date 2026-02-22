"""
KnowMat Chat Server - Dependency-aware Dynamic Planning for Material Design

This module implements the core reasoning strategy: dependency-aware dynamic planning,
which constructs explicit dependency graphs (DAGs) to guide multi-step material design workflows.
"""
import asyncio
import sys
from typing import Any
from fastapi import FastAPI
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from openai import OpenAI
import time
from pydantic import BaseModel
from contextlib import AsyncExitStack
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from prompt_templates import (
    RE_PLANNING_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_CoT,
    SYSTEM_PROMPT_PL,
    PARSE_TASK_PROMPT,
    PARSE_TASK_EXAMPLES,
    RESPONSE_PROMPT,
    RESPONSE_PROMPT_TP,
)
from utils import find_task
import json
from collections import deque
import logging
from mcp.types import TextContent, ImageContent, EmbeddedResource, CallToolResult

logging.basicConfig(
    filename="log_chat_server.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


def convert_content(
    content: TextContent | ImageContent | EmbeddedResource
) -> str:
    if type(content) == TextContent:
        return content.text
    return str(content)


def convert_call_tool_result(res: CallToolResult) -> str:
    """Extract text content from call tool result."""
    result = ""
    content_list = res.content
    if len(content_list) == 1:
        return convert_content(content_list[0])
    for a_content in content_list:
        if type(a_content) == TextContent:
            result += a_content.text + ", "
    return result.rstrip(", ")


class Message(BaseModel):
    content: str
    convid: str
    method: str  # 'CoT' | 'planning'


class MCPClient:
    """Manages MCP server connections and tool execution."""

    def __init__(self) -> None:
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        if self.session:
            logger.info("Session already initialized.")
            return

        server_params = StdioServerParameters(
            command="python",
            args=["mcp_server.py"],
            env=None,
        )

        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
            logger.info("Session initialized.")
        except Exception as e:
            logging.error(f"Error initializing server: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[Any]:
        if not self.session:
            raise RuntimeError("Server not initialized")
        tools_response = await self.session.list_tools()
        return tools_response.tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism (P_s = 1 - p_f^(R+1))."""
        if not self.session:
            raise RuntimeError("Server not initialized")

        attempt = 0
        while attempt <= retries:
            try:
                logging.info(f"Executing {tool_name}...")
                t1 = time.perf_counter()
                result = await self.session.call_tool(tool_name, arguments)
                t2 = time.perf_counter()
                logging.info(f"Execution completed in {t2-t1}s.")
                return result
            except Exception as e:
                attempt += 1
                logging.warning(f"Error executing tool: {e}. Attempt {attempt} of {retries+1}.")
                if attempt <= retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise

    async def cleanup(self) -> None:
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")


class ChatSession:
    """
    Implements the Dependency-aware Dynamic Planning strategy.
    See Algorithm 1 in paper: DAG generation -> Topological execution -> LLM summarization.
    """

    def __init__(self, mcp_client: MCPClient, llm_client: OpenAI) -> None:
        self.mcp_client = mcp_client
        self.llm_client = llm_client
        self.convs = {"planning": {}, "CoT": {}}
        self.initialized = False
        self.tools = []
        self.cur_user_question = ""

    def llm(self, model: str, messages: list, tools=None) -> Any:
        t1 = time.perf_counter()
        response = self.llm_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools
        )
        t2 = time.perf_counter()
        logger.info(f"[call llm] {t2-t1} s.")
        return response

    async def initialize(self) -> None:
        if self.initialized:
            return
        await self.mcp_client.initialize()
        self.initialized = True

    async def chat(self, message: Message) -> str:
        self.tools = await self.mcp_client.list_tools()
        conv_id = message.convid
        method = message.method
        self.cur_user_question = message.content
        convs = self.convs[method]

        if method == "CoT":
            if conv_id not in convs:
                convs[conv_id] = [{"role": "system", "content": SYSTEM_PROMPT_CoT}]
            message.content += "\n 思考解决该问题需要使用的工具，利用这些工具将该问题拆分为多个子问题，一步接一步地解决"
            convs[conv_id].append({"role": "user", "content": message.content})
            resp = await self.chat_cot(convs[conv_id])
        elif method == "planning":
            tools_description = self.get_tools_description()
            if conv_id not in convs:
                convs[conv_id] = [{"role": "system", "content": SYSTEM_PROMPT_PL}]
                for example in PARSE_TASK_EXAMPLES:
                    convs[conv_id].append({
                        "role": "user",
                        "content": PARSE_TASK_PROMPT.format(
                            tools_description=tools_description,
                            user_question=example["user_question"]
                        )
                    })
                    convs[conv_id].append({
                        "role": "assistant",
                        "content": example["llm_response"]
                    })
            convs[conv_id].append({
                "role": "user",
                "content": PARSE_TASK_PROMPT.format(
                    tools_description=tools_description,
                    user_question=message.content
                )
            })
            resp = await self.chat_planning(convs[conv_id])

        convs[conv_id].append({"role": "assistant", "content": resp})
        return resp

    def get_tools_list(self, tool_id_list: list = None) -> list:
        tools = self.tools if tool_id_list is None else [
            t for t in self.tools if t.name in tool_id_list
        ]
        return [{
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema
            }
        } for t in tools]

    def get_tools_description(self, tool_id_list: list = None) -> str:
        tools = self.tools if tool_id_list is None else [
            t for t in self.tools if t.name in tool_id_list
        ]
        return ";\n---\n".join([
            f"tool_id: {t.name}, description: {t.description}, input_schema: {t.inputSchema}"
            for t in tools
        ])

    async def topological_execution(self, tasks: list) -> dict:
        """
        Topological execution of the task DAG.
        Complexity O(|V|+|E|). Executes nodes with zero in-degree first.
        """
        task_results = {task["task_id"]: {"task": task} for task in tasks}
        in_degree = {}
        adj = {}
        q = deque()

        for task in tasks:
            task_id = task["task_id"]
            if task["dep"] == [-1]:
                q.append(task_id)
                in_degree[task_id] = 0
            else:
                in_degree[task_id] = len(task["dep"])
            adj[task_id] = []

        for task in tasks:
            task_id = task["task_id"]
            dep_list = task["dep"]
            if dep_list == [-1]:
                continue
            for dep_id in dep_list:
                adj[dep_id].append(task_id)

        while q:
            task_id = q.popleft()
            task = task_results[task_id]["task"]
            args = task["args"]
            deps = task["dep"]
            args_str = json.dumps(args)
            for dep_id in deps:
                if dep_id == -1:
                    continue
                task_res = task_results[dep_id]["result"]
                args_str = args_str.replace(f"<GENERATED>-{dep_id}", task_res)
            args = json.loads(args_str)
            tool_name = task["tool_id"]
            logger.info(f"[task {task_id} running] tool: {tool_name}")
            t1 = time.perf_counter()
            task_res = await self.mcp_client.execute_tool(tool_name, args)
            task_res = convert_call_tool_result(task_res)
            if isinstance(task_res, str) and "error" in task_res.lower():
                return {
                    "error": {"task_id": task_id, "task_res": task_res},
                    "task_results": task_results
                }
            task_results[task_id]["result"] = task_res
            t2 = time.perf_counter()
            logger.info(f"[task {task_id} completed] {t2-t1} s.")

            for neighbor_id in adj[task_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    q.append(neighbor_id)

        return task_results

    async def chat_cot(self, messages: list) -> str:
        available_tools = self.get_tools_list()
        try:
            first = True
            max_count = 10
            i = 0
            response = None
            while (first or (response and response.choices[0].finish_reason == 'tool_calls')) and i < max_count:
                i += 1
                logger.info(f"Round {i}")
                first = False
                response = self.llm(
                    model=os.environ.get("LLM_MODEL_ID", "gpt-4"),
                    messages=messages,
                    tools=available_tools
                )
                content = response.choices[0]
                if content.finish_reason == "tool_calls":
                    for tool_call in content.message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        result = await self.mcp_client.execute_tool(tool_name, tool_args)
                        messages.append(content.message.model_dump())
                        messages.append({
                            "role": "tool",
                            "content": str(result.content),
                            "tool_call_id": tool_call.id,
                        })
                else:
                    break
            messages.append({
                "role": "user",
                "content": RESPONSE_PROMPT.format(user_question=self.cur_user_question)
            })
            response = self.llm(
                model=os.environ.get("LLM_MODEL_ID", "gpt-4"),
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            return str(e)

    async def chat_planning(self, messages: list) -> str:
        """Dependency-aware planning: DAG generation -> execution -> localized re-planning -> summarization."""
        response = self.llm(
            model=os.environ.get("LLM_MODEL_ID", "gpt-4"),
            messages=messages
        ).choices[0].message.content
        logger.info(f"[llm response] {response}")

        task_json_str = find_task(response)
        tasks = []
        try:
            tasks = json.loads(task_json_str)
        except Exception as e:
            logger.info(e)

        messages.append({"role": "assistant", "content": task_json_str})
        task_results = await self.topological_execution(tasks)

        while "error" in task_results:
            error_task_id = task_results["error"]["task_id"]
            error_task_res = task_results["error"]["task_res"]
            logger.info(f"Localized re-planning: task {error_task_id} failed: {error_task_res}")
            messages.append({
                "role": "user",
                "content": RE_PLANNING_PROMPT_TEMPLATE.format(
                    error_task_id=str(error_task_id),
                    error_task_res=str(error_task_res),
                    task_results=str(task_results["task_results"]),
                )
            })
            response = self.llm(
                model=os.environ.get("LLM_MODEL_ID", "gpt-4"),
                messages=messages
            ).choices[0].message.content
            task_json_str = find_task(response)
            tasks = []
            try:
                tasks = json.loads(task_json_str)
            except Exception as e:
                logger.info(e)
            messages.append({"role": "assistant", "content": task_json_str})
            task_results = await self.topological_execution(tasks)

        messages.append({
            "role": "user",
            "content": RESPONSE_PROMPT_TP.format(
                task_results=str(task_results),
                user_question=self.cur_user_question
            )
        })
        response = self.llm(
            model=os.environ.get("LLM_MODEL_ID", "gpt-4"),
            messages=messages
        )
        return response.choices[0].message.content


if __name__ == '__main__':
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            os.environ.get("FRONTEND_ENDPOINT", "http://127.0.0.1:8080"),
            "http://127.0.0.1:8080",
            "http://localhost:8080"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    mcp_client = MCPClient()
    llm_client = OpenAI(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    chat_session = ChatSession(mcp_client=mcp_client, llm_client=llm_client)

    @app.get("/")
    async def read_root():
        return {"Hello": "KnowMat", "status": "running"}

    @app.post("/chat")
    async def chat(message: Message):
        await chat_session.initialize()
        resp = await chat_session.chat(message)
        return {"reply": resp}

    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", "7896"))
    uvicorn.run(app, host="0.0.0.0", port=port)
