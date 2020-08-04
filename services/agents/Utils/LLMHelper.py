import json
import re
from typing import Dict, Any
from json_repair import repair_json
class LLMResponseParser:
    @staticmethod
    def parse_response(content: str) -> Dict[str, Any]:
        """Universal LLM response parser with JSON extraction."""
        try:
            # First try direct JSON parse for non-wrapped responses
            return json.loads(content)
        except json.decoder.JSONDecodeError:
            # Fallback to code block extraction
            matches = re.findall(r'```json(.*?)```', content, re.DOTALL)
            if matches:
                json_str = matches[-1].strip()
                try:
                    return json.loads(json_str)
                except json.decoder.JSONDecodeError:
                    json_str = repair_json(json_str) 
                    return json.loads(json_str) if json_str else {}
            return {}
