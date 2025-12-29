"""
DeepSeek智能科研引擎 - 最终版
基于CrazyAgent框架的AI科研助手
作者：为申请石仁达老师实习生定制开发
"""

import os
from dotenv import load_dotenv # 新增这行
import sys
import json
import time
import asyncio
import random
from datetime import datetime
from typing import Dict, Any

load_dotenv() # 新增这行，用于加载 .env 文件


# 检查并安装依赖
def check_deps():
    try:
        from crazyagent.chat import Deepseek
        from crazyagent.memory import Memory, SystemMessage
        from crazyagent.toolkit.core import crazy_tool, Argument
        print("✓ 依赖库就绪")
        return Deepseek, Memory, SystemMessage, crazy_tool, Argument
    except ImportError:
        print("正在安装crazyagent...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "crazyagent"])
        from crazyagent.chat import Deepseek
        from crazyagent.memory import Memory, SystemMessage
        from crazyagent.toolkit.core import crazy_tool, Argument
        print("✓ 依赖库安装成功")
        return Deepseek, Memory, SystemMessage, crazy_tool, Argument


Deepseek, Memory, SystemMessage, crazy_tool, Argument = check_deps()


# ========== 配置 (您的API密钥已在此处) ==========
class Config:
    # 从名为 "DEEPSEEK_API_KEY" 的环境变量中读取密钥
    # 如果读取不到，则返回 None，程序会报错，这能提醒你正确设置
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
    if not DEEPSEEK_API_KEY:
        raise ValueError("❌ 错误：未设置环境变量 'DEEPSEEK_API_KEY'。请按照README进行配置。")


# ========== 三大核心工具 ==========
class ResearchTools:
    _llm = None
    # 新增：用于防止工具函数在同一流程中重复执行核心逻辑的标志
    _tool_execution_flag = {}

    @classmethod
    def init(cls, llm):
        cls._llm = llm

        # ========== 新增：学术问答工具 ==========
    @staticmethod
    @crazy_tool
    def academic_qa(concept: str = Argument("学术概念", required=True)) -> Dict[str, Any]:
        """解释学术概念、术语或技术"""
        print(f"[工具] 学术问答: {concept}")
        prompt = f"""请对以下学术概念或技术进行清晰、准确、全面的解释：
        概念：“{concept}”
        请按以下结构组织内容：
        1. **基本定义**：用一句话精炼概括。
        2. **核心原理**：阐述其工作原理或核心思想。
        3. **主要应用**：列举2-3个典型应用场景。
        4. **意义与挑战**：简要说明其重要性及当前面临的挑战或未来方向。
        请确保解释专业且易于理解。"""
        try:
            resp = ResearchTools._llm.invoke(prompt)
            return {"status": "success", "concept": concept, "content": resp.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    @crazy_tool
    def literature_review(topic: str = Argument("主题", required=True)) -> Dict[str, Any]:
        """生成文献综述"""
        # --- 新增：检查执行标记 ---
        # 为当前工具创建一个唯一标识，例如使用主题的前几个字符
        flag_key = f"literature_review_{topic[:20]}"
        if ResearchTools._tool_execution_flag.get(flag_key):
            print(f"[调试] 检测到 literature_review 重复调用，已跳过核心逻辑。")
            # 可以返回一个空结果或上一次的结果，这里返回一个跳过标记
            return {"status": "skipped", "note": "重复调用已跳过"}
        # 设置标记，表示正在/已经执行
        ResearchTools._tool_execution_flag[flag_key] = True
        # --- 新增结束 ---

        print(f"[工具] 文献综述: {topic}")
        prompt = f"请为研究主题'{topic}'撰写一篇结构完整的文献综述，包含背景、方法、近期进展和未来挑战。"
        try:
            resp = ResearchTools._llm.invoke(prompt)
            return {"status": "success", "topic": topic, "content": resp.content}
        except Exception as e:
            # 新增：打印具体是什么错误
            # print(f"[文献综述工具错误] 调用LLM失败：{e}")
            return {"status": "error", "error": str(e)}
        finally:
            # --- 新增：可选地，在处理完成后清除标记，但通常一次会话中不需要 ---
            # ResearchTools._tool_execution_flag[flag_key] = False
            pass
        return result

    @staticmethod
    @crazy_tool
    def code_analysis(code: str = Argument("代码", required=True)) -> Dict[str, Any]:
        """分析代码"""
        print(f"[工具] 代码分析")
        prompt = f"请分析以下代码，指出潜在问题、优化建议，并评估其质量：\n```python\n{code[:500]}\n```"
        try:
            resp = ResearchTools._llm.invoke(prompt)
            return {"status": "success", "analysis": resp.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    @crazy_tool
    def research_plan(project: str = Argument("项目名", required=True)) -> Dict[str, Any]:
        """制定研究计划"""
        print(f"[工具] 研究计划: {project}")
        prompt = f"请为研究项目'{project}'制定一份详细计划，包含目标、技术路线、时间表和预期成果。"
        try:
            resp = ResearchTools._llm.invoke(prompt)
            return {"status": "success", "project": project, "plan": resp.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ========== 智能体核心 ==========
class ResearchAgent:
    def __init__(self):
        self.llm = Deepseek(api_key=Config.DEEPSEEK_API_KEY)
        ResearchTools.init(self.llm)
        self.memory = Memory(max_turns=10)
        self.memory.system_message = SystemMessage(
            "你是DeepSeek科研助手，专业且乐于助人。可使用工具进行文献综述、代码分析和制定研究计划。"
        )
        self.history = []


    async def process(self, query: str) -> Dict[str, Any]:
        """处理用户查询"""
        print(f"\n> 处理: {query[:50]}...")
        start = time.time()

        # 初始化结果字典
        results = {}
        tools_used = []

        try:
            # 1. 分析意图
            tools_to_use = []
            if any(k in query for k in ["文献", "综述", "调研"]):
                tools_to_use.append(("literature_review", query[:30]))
            # 新增：学术问答意图识别
            if any(k in query for k in
                   ["什么是", "什么是", "解释", "定义", "简述", "介绍", "含义", "什么意思", "为何", "为什么"]):
                tools_to_use.append(("academic_qa", query))
            if any(k in query for k in ["代码", "程序", "编程", "bug", "错误"]):
                tools_to_use.append(("code_analysis", query))
            if any(k in query for k in ["计划", "方案", "项目", "规划"]):
                tools_to_use.append(("research_plan", query[:30]))

            # 2. 调用工具
            for tool_name, arg in tools_to_use:
                try:
                    if tool_name == "literature_review":
                        results[tool_name] = ResearchTools.literature_review(topic=arg)
                    elif tool_name == "academic_qa":  # 新增调用分支
                        results[tool_name] = ResearchTools.academic_qa(concept=arg)
                    elif tool_name == "code_analysis":
                        results[tool_name] = ResearchTools.code_analysis(code=arg)
                    elif tool_name == "research_plan":
                        results[tool_name] = ResearchTools.research_plan(project=arg)
                    tools_used.append(tool_name)
                except Exception as e:
                    print(f"[警告] 调用工具 {tool_name} 时出错: {e}")
                    results[tool_name] = {"status": "error", "error": str(e)}

            # 3. 生成最终回答
            if results:
                prompt = f"用户问：{query}\n\n工具分析结果：{json.dumps(results, ensure_ascii=False)}\n请整合以上信息，给出专业回答。"
            else:
                prompt = query

            try:
                response = self.llm.invoke(prompt)
                final = response.content
            except Exception as e:
                final = f"生成回答时出错：{e}"
                print(f"[警告] 调用AI模型失败: {e}")

        except Exception as e:
            # 捕获process方法中任何其他未预料到的错误
            import traceback
            error_detail = traceback.format_exc()
            print(f"[严重错误] process执行过程异常: {e}")
            print(f"错误详情:\n{error_detail}")
            final = f"处理请求时发生系统错误：{e}"
            # 可以选择返回一个表示失败的结果
            # 这里我们依然返回一个结构，但标记为失败

        # 记录历史
        self.history.append({
            "query": query,
            "response": final[:100],
            "time": time.time() - start
        })

        # 始终返回一个结构化的字典，即使出错
        return {
            "success": '出错' not in final,  # 简单判断是否出错
            "query": query,
            "response": final,
            "tools_used": tools_used,
            "time_cost": round(time.time() - start, 2)
        }


# ========== 主交互界面 ==========
async def main():
    print("=" * 60)
    print("DeepSeek科研助手 ")
    print("=" * 60)
    print("功能：1.文献综述 2.代码分析 3.研究计划 4.学术问答")
    print("输入 'exit' 退出，'status' 查看状态")
    print("=" * 60)

    agent = ResearchAgent()

    while True:
        try:
            user_input = input("\n您的问题：").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                print(f"\n会话结束。共处理 {len(agent.history)} 个问题。")
                break
            if user_input == 'status':
                print(f"系统正常 | 历史问题数：{len(agent.history)}")
                continue

            result = await agent.process(user_input)  # 假设这是第296行

            # 这是您期望执行的输出代码块 (假设是第300行开始)
            print(f"\n【回答】({result['time_cost']}秒)：")
            print("-" * 50)
            print(result["response"])
            print("-" * 50)
            if result["tools_used"]:
                print(f"使用工具：{', '.join(result['tools_used'])}")

        except KeyboardInterrupt:
            print("\n程序中断。")
            break
        except Exception as e:
            print(f"\n[主循环捕获到未处理的异常]：{e}")
            continue


# ========== 程序入口 ==========
if __name__ == "__main__":
    # 启动前检查关键环境变量
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("⚠️  提示：请先设置环境变量 'DEEPSEEK_API_KEY'")
        print("Linux/Mac: export DEEPSEEK_API_KEY='您的密钥'")
        print("Windows: set DEEPSEEK_API_KEY=您的密钥")
        print("或者在 '.env' 文件中设置。")
        exit(1)
    print("启动DeepSeek科研助手...")
    asyncio.run(main())
    # print("启动DeepSeek科研助手...")
    # asyncio.run(main())

# """
# 基于 CrazyAgent 框架的 AI 个人助手
# 功能：多轮对话记忆、调用搜索工具、调用文件操作工具
# 作者：你的名字
# 日期：2025-12-23
# """
# import os
# from crazyagent.chat import Deepseek
# from crazyagent.memory import Memory, SystemMessage
# from crazyagent.toolkit.core import crazy_tool, Argument
#
# # ------------------------ 第一部分：配置与初始化 ------------------------
# # 1. 设置你的 DeepSeek API 密钥 (请替换为你的真实密钥)
# # 方法：在终端执行 export DEEPSEEK_API_KEY='你的key'，或在下面直接赋值（不推荐）
# DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-befc1f2f948043ee8f61ab8a067ce45c")
#
# # 2. 初始化大语言模型 (使用 DeepSeek)
# llm = Deepseek(api_key=DEEPSEEK_API_KEY)
#
# # 3. 初始化记忆系统，保留最近10轮对话
# memory = Memory(max_turns=10)
# # 设置系统提示词，定义助手角色
# memory.system_message = SystemMessage(
#     "你是一个热情、专业的个人助手，名字叫小C。你能回答用户问题，并可以调用工具来搜索实时信息或管理文件。")
#
#
# # ------------------------ 第二部分：自定义工具开发 ------------------------
# # 工具1：一个模拟的联网搜索工具（实际开发时可替换为真实搜索引擎API）
# @crazy_tool
# def web_search(query: str = Argument("搜索关键词", required=True)) -> dict:
#     """
#     根据关键词进行网络搜索，获取实时信息。
#
#     Args:
#         query: 要搜索的关键词，例如“今天的天气预报”
#
#     Returns:
#         一个包含搜索结果的字典。
#     """
#     # 此处为模拟数据。真实应用中，你可以调用 SerperDev、DuckDuckGo 或 Google Custom Search API
#     print(f"[工具调用] 正在搜索：{query}")
#     # 模拟根据不同关键词返回不同的结果
#     if "天气" in query:
#         result = {
#             "query": query,
#             "result": "模拟搜索显示：今天北京晴转多云，气温 15-25°C，南风3级。"
#         }
#     elif "新闻" in query:
#         result = {
#             "query": query,
#             "result": "模拟搜索显示：AI 智能体开发框架 CrazyAgent 发布新版本，因其简洁易用受到开发者欢迎。"
#         }
#     else:
#         result = {
#             "query": query,
#             "result": f"关于 '{query}' 的模拟搜索结果：CrazyAgent 是一个极简高效、适合新手的 LLM 智能体开发框架[citation:1]。"
#         }
#     return result
#
#
# # 工具2：一个简单的文件内容读取工具
# @crazy_tool
# def read_file(file_path: str = Argument("要读取的文件的完整路径", required=True)) -> str:
#     """
#     读取指定文本文件的内容。
#
#     Args:
#         file_path: 本地文件的路径，例如 './notes.txt'
#
#     Returns:
#         文件的内容字符串。如果文件不存在，则返回错误信息。
#     """
#     print(f"[工具调用] 正在读取文件：{file_path}")
#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
#         return f"文件 '{file_path}' 的内容如下：\n{content}"
#     except FileNotFoundError:
#         return f"错误：未找到文件 '{file_path}'，请检查路径。"
#     except Exception as e:
#         return f"读取文件时出错：{str(e)}"
#
#
# # ------------------------ 第三部分：主对话循环 ------------------------
# def main():
#     """运行 AI 助手的主程序"""
#     print("=" * 50)
#     print("AI 个人助手小C 已启动！")
#     print(f"系统提示：{memory.system_message.content}")
#     print("我已具备以下能力：")
#     print("  1. 多轮对话（我会记住我们最近的聊天内容）")
#     print("  2. 实时搜索（尝试问我：'今天北京的天气怎么样？'）")
#     print("  3. 读取文件（尝试创建个 test.txt 然后问我：'读一下 ./test.txt 文件'）")
#     print("输入 'exit' 或 'quit' 退出程序。")
#     print("=" * 50)
#
#     # 将我们定义的工具放入列表，提供给 LLM[citation:1]
#     available_tools = [web_search, read_file]
#
#     while True:
#         try:
#             # 获取用户输入
#             user_input = input("\n[你]：").strip()
#             if user_input.lower() in ["exit", "quit"]:
#                 print("助手小C：再见！期待下次与你聊天。")
#                 break
#             if not user_input:
#                 continue
#
#             # 核心：将用户输入、记忆和工具列表发送给 LLM，并流式输出回复[citation:1]
#             print(f"\n[助手小C]：", end="", flush=True)
#             for response in llm.stream(user_input, memory=memory, tools=available_tools):
#                 print(response.content, end="", flush=True)
#             print()  # 换行
#
#             # 流式输出结束后，可以查看当前记忆状态（调试时使用）
#             # print(memory) # 取消注释此行可以查看详细的记忆表格
#
#         except KeyboardInterrupt:
#             print("\n\n检测到中断，程序退出。")
#             break
#         except Exception as e:
#             print(f"\n程序运行时出现错误：{e}")
#
#
# # ------------------------ 第四部分：程序入口 ------------------------
# if __name__ == "__main__":
#     # 运行主程序
#     main()
