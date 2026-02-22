"""Prompt templates for DAG generation and task decomposition."""
# Material design / alloy domain prompts (simplified set for KnowMat)
PARSE_TASK_PROMPT = """\
工具列表如下:
{tools_description},
用户提问为: {user_question},
请使用这些工具解析用户提问，返回 json 格式解析结果
"""

PARSE_TASK_EXAMPLES = [
    {
        "user_question": "请给出合金 Inconel 625 的密度",
        "llm_response": """[\
{"task_id": 0, "dep": [-1], "tool_id": "query_database", "args": {"sql": "SELECT c.element, c.value FROM compositions c INNER JOIN alloys a ON c.alloy_id = a.alloy_id AND a.name = 'Inconel 625'"}},\
{"task_id": 1, "dep": [0], "tool_id": "predict_alloy_density", "args": {"alloy_compositions": "<GENERATED>-0"}}\
]"""
    },
    {
        "user_question": "Estimate the γ' solvus temperature of a superalloy with the following composition: 10% Ti, 20% Al, 70% Ni.",
        "llm_response": """[\
{"task_id": 0, "dep": [-1], "tool_id": "predict_alloy_gamma_prime_solvus_temperature", "args": {"alloy_compositions": "10% Ti, 20% Al, 70% Ni"}}\
]"""
    }
]

SYSTEM_PROMPT_CoT = """\
你是数据库和高温合金材料领域的专家，理解并分解用户的提问，使用提供的工具一步接一步地解决用户提问。
若选择调用数据库查询工具，调用时应生成 sql 语句对数据库中的表进行查询。生成 sql 语句以数据库信息为优先，生成后应检查 sql 语句，保证其有效。
请优先调用数据库查询工具，若数据库查询工具返回的结果无法满足用户提问，请使用其他工具
"""

SYSTEM_PROMPT_PL = """\
你是数据库和高温合金材料领域的专家，理解并分解用户的提问，使用提供的工具一步接一步将用户输入解析为多个任务，按照如下格式返回解析结果:
[{"task_id": task_id, "dep": [dependency_task_id], "tool_id": tool_id, "args": {"arg_name": arg_value or <GENERATED>-dep_id}}]。
"dep"字段为当前任务所依赖的先前任务的 task_id 列表。若当前任务不依赖任何先前任务，使用 [-1]。
"args"为工具输入参数字典。特殊标签"<GENERATED>-dep_id"指的是当前任务所依赖的任务生成的数据，请保证"dep_id"位于"dep"列表中。
分步思考能够解决用户请求所需的所有任务。在确保用户请求能够被解析的前提下，解析得到的任务数量尽可能少。
注意任务之间的依赖关系和顺序。如果无法解析用户输入，则返回空的JSON列表 []。
"""

RESPONSE_PROMPT = """请根据以上对话内容回答用户初始提问: {user_question}。请总结工作流，包括调用的工具与其结果。若无法回答用户提问，请总结原因。
若用户初始提问为英文，请使用英文回答；若用户初始提问为中文，请使用中文回答。"""

RESPONSE_PROMPT_TP = """\
执行前一步生成的任务流程，得到以下执行结果：{task_results}
请根据以上信息回答"用户初始提问": {user_question}。请在回答中总结工作流，包括调用的工具与其结果。
若无法回答用户提问，请总结原因。若"用户初始提问"为英文，请使用英文回答；若"用户初始提问"为中文，请使用中文回答。"""

DATA_CLEANING_PROMPT_TEMPLATE = "Here is some raw data in json form: {data}\n. {context}. Please only response the new json."

RE_PLANNING_PROMPT_TEMPLATE = """
任务 {error_task_id} 执行失败，错误信息: {error_task_res}。
以下是执行成功的任务与执行结果：
{task_results}
请根据以上信息重新解析用户提问，返回 json 格式解析结果
"""
