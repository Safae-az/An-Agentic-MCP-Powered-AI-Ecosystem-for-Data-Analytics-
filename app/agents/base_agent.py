# app/agents/base_agent.py
import requests
import json
import os

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

# Outils qui retournent (df, result) au lieu d'un simple dict
TUPLE_TOOLS = {"load_dataset"}

class BaseAgent:
    """
    Classe parent commune a tous les agents.
    Contient la methode _call_mcp() pour appeler
    les outils via le MCP Server.
    """

    def __init__(self, agent_name: str, run_id: str):
        self.agent_name = agent_name
        self.run_id = run_id
        print(f"[{self.agent_name}] Agent initialise — run: {self.run_id}")

    def _call_mcp(self, tool_name: str, params: dict) -> dict:
        """
        Appelle un outil via le MCP Server.
        C'est le SEUL moyen d'appeler un outil.
        """
        payload = {
            "agent": self.agent_name,
            "tool": tool_name,
            "params": params,
            "run_id": self.run_id
        }

        print(f"[{self.agent_name}] MCP call → {tool_name}")

        try:
            response = requests.post(
                f"{MCP_SERVER_URL}/call",
                json=payload,
                timeout=300
            )

            if response.status_code == 403:
                print(f"[{self.agent_name}] PERMISSION REFUSEE pour {tool_name}")
                return {"status": "error", "message": f"Permission refusee : {tool_name}"}

            if response.status_code != 200:
                print(f"[{self.agent_name}] ERREUR MCP {response.status_code}")
                return {"status": "error", "message": f"MCP error {response.status_code}"}

            result = response.json().get("result", {})
            print(f"[{self.agent_name}] MCP OK ← {tool_name}")
            return result

        except requests.exceptions.ConnectionError:
            print(f"[{self.agent_name}] MCP Server non disponible — appel direct")
            return self._fallback_direct(tool_name, params)

        except Exception as e:
            print(f"[{self.agent_name}] Exception MCP : {e}")
            return {"status": "error", "message": str(e)}

    def _fallback_direct(self, tool_name: str, params: dict) -> dict:
        """
        Fallback si le MCP Server n'est pas demarre.
        Gere les outils qui retournent (df, result) ou juste un dict.
        """
        print(f"[{self.agent_name}] FALLBACK direct → {tool_name}")
        import importlib

        try:
            module = importlib.import_module(f"app.tools.{tool_name}")
            func = getattr(module, tool_name)
            raw = func(**params)

            if tool_name in TUPLE_TOOLS:
                # load_dataset et clean_data retournent (df, result_dict)
                _, result = raw
                return result
            else:
                return raw

        except Exception as e:
            return {"status": "error", "message": str(e)}