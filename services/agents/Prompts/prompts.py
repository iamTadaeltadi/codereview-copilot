STANDARD_CHECKER_PROMPT_TEMPLATE = \
    """
    You are a compliance analyzer. Using the standards provided below, review the code diff (ignore diff markers like '+' and '-' and line numbers) and identify any deviations.
    
    Standards:
    {standards_str}

    Code diff:
    {diff_content}
    
    Additional Instructions:
    {additional_instructions}
    
    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "standard": "..."
            }}
        ]
    }}
    ```
    """

SYNTAX_CHECKER_PROMPT_TEMPLATE = \
    """
    You are a syntax analyzer for {language} code. Examine the code diff (ignoring diff markers and line numbers) and detect any syntax errors.
    
    Code Diff
    {diff_content}
    
    Additional Instructions:
    {additional_instructions}

    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "description": "..."
            }}
        ]
    }}
    ```
    """
REPO_SUMMARIZER_PROMPT_TEMPLATE = \
    """
    You are an AI specialized in analyzing codebases. The following JSON represents the file structure of the repository at '{repo_folder_path}':

    {file_tree_json}

    Using this structure, describe:
    1. The primary language or framework (type of project).
    2. The tools, libraries, or frameworks used by the project.
    3. The repository’s architecture and how it’s organized.
    4. Any notable patterns or setups (e.g., CI/CD, containerization).

    Return your findings in valid JSON:
    ```json 
        {{
        "project_type": "...",
        "tools_and_libraries": ["...", "..."],
        "architecture_summary": "...",
        "notable_patterns": ["..."]
    }}
