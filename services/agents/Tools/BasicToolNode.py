import uuid
import json
from langchain_core.messages import ToolMessage
class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}
    def __call__(self, inputs: dict):
        if messages := inputs.get("issues", []):
            ai_message = messages[-1]
        else:
            raise ValueError("No message found in input")
        
        json_str = ai_message.content.strip("```json\n").strip("\n```")
        try:
            # Try parsing the JSON string
            tool_call_data = json.loads(json_str)
            # Check if tool_calls are present
            if isinstance(tool_call_data, dict) and "tool_calls" in tool_call_data:
                tool_calls = tool_call_data["tool_calls"]
                outputs = []
                for tool_call in tool_calls:
                    tool_result = self.tools_by_name[tool_call["function_call"]["name"]].invoke(
                        tool_call["function_call"]["args"]
                    )
                    outputs.append(
                        ToolMessage(
                            content=json.dumps(tool_result),
                            name=tool_call["function_call"]["name"],
                            tool_call_id=str(uuid.uuid4()),
                        )
                    )

                # Add the ToolMessage to the state (ensure state supports this structure)
                if isinstance(inputs, dict) and "issues" in inputs:
                    inputs["issues"] += outputs
                    # return {"messages": inputs["messages"]+outputs}
                    return inputs
        except json.JSONDecodeError:
            print("Json Str: ",inputs.get("issues", []))
            # Handle JSON decoding errors gracefully
            print("Failed to parse tool calls JSON.")
            
        return inputs