import anthropic
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

MCP_URL = "http://localhost:8000/call"


class BaseAgent:
    """
    Classe parent commune à tous les agents.
    Contient la boucle while True (tool use loop),
    l'appel à l'API Claude, et l'appel au MCP Server.
    Chaque agent hérite de cette classe et définit
    son propre system_prompt et ses outils autorisés.
    """

    agent_name:  str = "base_agent"
    system_prompt: str = "Tu es un agent IA."

    def __init__(self):
        self.client = anthropic.Anthropic()

    def run(self, step: str, context: dict) -> dict:
        """
        Lance la boucle agent pour accomplir une tâche.
        À surcharger dans les classes enfants si besoin.
        """
        raise NotImplementedError("Chaque agent doit implémenter run()")

    def _call_llm(self, messages: list, tools: list) -> object:
        """Appelle l'API Claude avec les messages et outils."""
        return self.client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 2000,
            system     = self.system_prompt,
            tools      = tools,
            messages   = messages
        )

    def _call_mcp(self, tool: str, params: dict, run_id: str) -> dict:
        """Appelle un outil via le MCP Server."""
        try:
            response = requests.post(MCP_URL, json={
                "agent":  self.agent_name,
                "tool":   tool,
                "params": params,
                "run_id": run_id
            }, timeout=60)
            response.raise_for_status()
            return response.json().get("result", {})
        except Exception as e:
            return {"error": str(e)}

    def _run_loop(self, messages: list, tools: list, run_id: str) -> str:
        """
        Boucle principale tool use.
        Tourne jusqu'à ce que Claude retourne stop_reason == end_turn.
        Retourne le texte final de Claude.
        """
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            response = self._call_llm(messages, tools)

            # Cas 1 : Claude a fini
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return "Terminé."

            # Cas 2 : Claude veut appeler un outil
            if response.stop_reason == "tool_use":

                # Ajouter la réponse de Claude dans l'historique
                messages.append({
                    "role":    "assistant",
                    "content": response.content
                })

                # Exécuter chaque outil demandé
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"    🔧 {self.agent_name} → {block.name}({list(block.input.keys())})")

                        result = self._call_mcp(block.name, block.input, run_id)

                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     json.dumps(result)
                        })

                # Ajouter les résultats dans l'historique
                messages.append({
                    "role":    "user",
                    "content": tool_results
                })

            # Cas 3 : tokens dépassés
            elif response.stop_reason == "max_tokens":
                return "Réponse tronquée — augmenter max_tokens"

        return "Limite d'itérations atteinte"
