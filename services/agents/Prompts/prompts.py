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
    ```
    """
CODE_SUMMARIZER_PROMPT_TEMPLATE = \
    """
    Summarize the following code diff:
    Filename: {file_path}
    Content:
    {diff_content}

    Return your summary in Markdown format that includes an overview and the key changes.
    """
CODE_SUMMARY_MERGER_PROMPT_TEMPLATE = \
    """
    Merge the following code summaries into one consolidated PR summary.
    
    Summaries:
    {summaries}

    Your merged summary should be in Markdown format highlighting the overall changes and key points.
    """
CODE_REVIEWER_PROMPT_TEMPLATE = \
    """
    You are a Code Reviewer. Evaluate the provided findings and the repository summary, then generate a comprehensive review per file. Rate the following metrics: {metrics}. Ensure that each rating (from 1 to 10) is justified by the findings and provide a reason for each rating.
    
    Findings:
    {issue}
    
    Repository Summary:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}
    
    Provide your answer as valid JSON formatted like this:     
    ```json 
    {{
        "summary": "overall_assessment",
        "file": "file_path",
        "ratings": {{
            {ratings}
        }},
        "critical_issues": ["issue1", "issue2", ...]
    }}
    ```
    """
CODE_FIX_PROMPT_TEMPLATE = \
    """
    Generate a corrected version of the code diff by addressing the issues listed below.
    
    Issues: 
    {issues}
    
    File: 
    {file_path}
    
    Original diff:
    {diff_content}
    
    Repository Summary:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}
    
    Return your corrected code in unified diff format.
    """
VULNERABILITY_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED = \
    """
    You are an AI Vulnerability Analysis agent. Your task is to analyze this code diff for vulnerabilities.
    You have reached the maximum number of tool calls ({max_tool_calls}). Complete the analysis based on the available information without making further tool calls.
