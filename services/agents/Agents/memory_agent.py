# memory_agent.py
from typing import List, Dict, Any
import datetime
import json
from Utils.LLMHelper import LLMResponseParser
from Prompts import LONG_TERM_MEMORY_PROMPT_TEMPLATE
class LongTermMemoryAgent:
    def __init__(self, llm, long_term_manage_tool, long_term_search_tool):
        self.llm = llm
        self.long_term_manage_tool = long_term_manage_tool
        self.long_term_search_tool = long_term_search_tool

    def analyze_preferences(self, interaction: str, existing_preferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prompt = self._create_analysis_prompt(interaction, existing_preferences)
        response = self.llm.invoke(prompt)
        return self._parse_preference_analysis(response.content)

    def update_preferences(self, preferences: List[Dict[str, Any]], config: dict):
        for pref in preferences:
            self.long_term_manage_tool.invoke(
                {
                    "content": json.dumps({
                        "type": "preference",
                        "data": pref,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }),
                    "action": "create"
                },
                config=config
            )

    def _create_analysis_prompt(self, interaction: str, existing_preferences: List[Dict[str, Any]]) -> str:
        return LONG_TERM_MEMORY_PROMPT_TEMPLATE.format(
            interaction=json.dumps(interaction, indent=2),
            existing_preferences=json.dumps(existing_preferences, indent=2)
        )

    def _parse_preference_analysis(self, response: str) -> List[Dict[str, Any]]:
        # Implementation of response parsing
        return LLMResponseParser.parse_response(response)