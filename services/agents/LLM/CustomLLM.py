from langchain_openai import ChatOpenAI
from config import Config
from langchain.schema import SystemMessage
import json

# Initialize CustomLLM that are compatible with the OpenAI API standard
# A custom class to override ChatOpenAI model with function handling logic
class CustomLLM(ChatOpenAI):
    def _generate(self, messages, stop=None, **kwargs):
        # Handle the tool function descriptions embedding into the system message
        if "functions" in kwargs:
            functions = kwargs.pop("functions", [])
            functions_description = self._generate_functions_description(functions)
            # Insert system message with function details at the start
            messages.insert(
                0,
                SystemMessage(content=(
                    "You have the following tools available. Use tools only if you cannot answer without them. "
                    "Respond directly to the user if possible, but if you must use a tool, return only a valid JSON object in this format:\n"
                    "```json\n"
                    "{\n"
                    "    \"tool_calls\": [\n"
                    "        {\"function_call\": {\"name\": \"function_name\", \"args\": {\"arg1\": \"value1\", \"arg2\": \"value2\"}}},\n"
                    "        {\"function_call\": {\"name\": \"another_function\", \"args\": {\"param1\": \"valueA\"}}}\n"
                    "    ]\n"
                    "}\n"
                    "```\n\n"
                    "Use the tool descriptions provided below carefully and ensure proper argument formatting. "
                    "If unsure or unable to use tools, ask the user for clarification:\n"
                    f"{functions_description}"
                ))
            )
        
        response = super()._generate(messages, stop=stop, **kwargs)
        return response

    def _generate_functions_description(self, functions):
        """Format and return function descriptions to be embedded in the system message."""
        function_descriptions = [
            f"Name: {f['name']}\nDescription: {f['description']}\nParameters:\n{json.dumps(f['parameters'], indent=2)}"
            for f in functions
        ]
        return "\n\n".join(function_descriptions)