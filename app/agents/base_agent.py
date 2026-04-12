import groq
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

MCP_URL = "http://localhost:8000/call"


class BaseAgent:

    agent_name    = "base_agent"
    system_prompt = "Tu es un agent IA."

    def __init__(self, run_id: str = ""):
        self.run_id = run_id
        self.client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model  = "llama-3.1-8b-instant"
        print(f"🚀 Groq — modèle : {self.model} — agent : {self.agent_name}")

    def _call_llm(self, messages: list, tools: list):
        all_messages = [
            {"role": "system", "content": self.system_prompt}
        ] + self._convert_messages(messages)

        groq_tools = [
            {
                "type": "function",
                "function": {
                    "name":        t["name"],
                    "description": t["description"],
                    "parameters":  t["input_schema"]
                }
            }
            for t in tools
        ]

        return GroqResponse(
            self.client.chat.completions.create(
                model       = self.model,
                messages    = all_messages,
                tools       = groq_tools if groq_tools else None,
                temperature = 0.1
            )
        )

    def _convert_messages(self, messages: list) -> list:
        converted = []
        for msg in messages:
            role    = msg["role"]
            content = msg["content"]

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            converted.append({
                                "role":         "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content":      block["content"]
                            })
                    elif hasattr(block, "type"):
                        if block.type == "tool_use":
                            converted.append({
                                "role":    "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id":   block.id,
                                    "type": "function",
                                    "function": {
                                        "name":      block.name,
                                        "arguments": json.dumps(block.input)
                                    }
                                }]
                            })
                        elif block.type == "text":
                            converted.append({
                                "role":    "assistant",
                                "content": block.text
                            })
            else:
                converted.append({"role": role, "content": content})

        return converted

    def _run_loop(self, messages: list, tools: list, run_id: str) -> str:
        max_iterations = 10
        iteration      = 0

        while iteration < max_iterations:
            iteration += 1
            response = self._call_llm(messages, tools)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        return block.text
                return "Terminé."

            if response.stop_reason == "tool_use":
                messages.append({
                    "role":    "assistant",
                    "content": response.content
                })

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"    🔧 [{self.agent_name}] → {block.name}")
                        result = self._call_mcp(block.name, block.input, run_id)
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     json.dumps(result)
                        })

                messages.append({
                    "role":    "user",
                    "content": tool_results
                })

            elif response.stop_reason == "max_tokens":
                return "Réponse tronquée — augmenter max_tokens"

        return "Limite d'itérations atteinte"

    def _call_mcp(self, tool: str, params: dict, run_id: str) -> dict:
        try:
            response = requests.post(MCP_URL, json={
                "agent":  self.agent_name,
                "tool":   tool,
                "params": params,
                "run_id": run_id
            }, timeout=60)
            response.raise_for_status()
            return response.json().get("result", {})
        except requests.Timeout:
            return {"error": "Timeout"}
        except Exception as e:
            return {"error": str(e)}

    def run(self, step: str = "", context: dict = {}) -> dict:
        raise NotImplementedError("Chaque agent doit implémenter run()")


# ── Wrappers ─────────────────────────────────────────────

class GroqResponse:
    def __init__(self, raw):
        choice  = raw.choices[0]
        message = choice.message

        if choice.finish_reason == "tool_calls":
            self.stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            self.stop_reason = "max_tokens"
        else:
            self.stop_reason = "end_turn"

        self.content = []

        if message.content:
            self.content.append(_TextBlock(message.content))

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    input_data = json.loads(tc.function.arguments)
                except:
                    input_data = {}
                self.content.append(_ToolUseBlock(
                    id    = tc.id,
                    name  = tc.function.name,
                    input = input_data
                ))


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _ToolUseBlock:
    def __init__(self, id, name, input):
        self.type  = "tool_use"
        self.id    = id
        self.name  = name
        self.input = input
