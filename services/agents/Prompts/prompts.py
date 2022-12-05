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
    
    Code diff:
    {diff_content}
    
    Here is the summary of the repository for context:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}
    
    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "type": "vulnerability",
                "description": "...",
                "severity": "high/medium/low"
            }}
        ]
    }}
    ```
    """
VULNERABILITY_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED = \
    """
    You are an AI Vulnerability Analysis agent. Your task is to analyze this code diff for vulnerabilities.
    If you need context, a tool call may have already been made and the context is in the previous tool result message. Use that context to complete the analysis. Do not make redundant tool calls for the same node.
    If no context is available, you may make a tool call.
    
    Tool calls made till now: 
    {tool_calls_made}
    
    Code diff:
    {diff_content}
    
    Here is the summary of the repository for context:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}
    
    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "type": "vulnerability",
                "description": "...",
                "severity": "high/medium/low"
            }}
        ]
    }}
    ```
    """
BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_EXCEEDED = \
    """
    You are an AI bug detection agent. Your task is to analyze this code diff for potential bugs.
    You have reached the maximum number of tool calls ({max_tool_calls}). Complete the analysis based on the available information without making further tool calls.
    
    Code diff:
    {diff_content}
    
    Here is the summary of the repository for context:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}
    
    Provide your answer as valid JSON formatted like this: 
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "type": "bug",
                "description": "...",
                "certainty": "high/medium/low"
            }}
        ]
    }}
    ```
    """
BUG_CHECKER_PROMPT_TEMPLATE_TOOL_CALL_LIMIT_NOT_EXCEEDED = \
    """
    You are an AI bug detection agent. Your task is to analyze this code diff for potential bugs.
    If you need context, a tool call may have already been made and the context is in the previous message (specifically Tool Message). But if not atleast make one. And if you already made one and you got no context, then move on with the analysis.
    
    Tool calls made till now:
    {tool_calls_made}
    
    Code diff:
    {diff_content}
    
    Here is the summary of the repository for context:
    {repo_summary}
    
    Additional Instructions:
    {additional_instructions}

    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "issues": [
            {{
                "location": "line X",
                "file": "file_path",
                "type": "bug",
                "description": "...",
                "certainty": "high/medium/low"
            }}
        ]
    }}
    ```
    """
ERROR_SUMMARIZER_PROMPT_TEMPLATE = \
    """
    Synthesize these findings into a unified report:
    , ensuring to aggregate issues based on their type (vulnerability or bug)
    {results}
    
    Provide your answer as valid JSON formatted like this:
    ```json
    {{
        "summary": "overall_analysis",
        "file: "file_path",
        "issues": [
            {{
                "type": "vulnerability|bug|other",
                "locations": ["line X", ...],
                "descriptions": ["...", ...]
            }}
        ]
    }}
    ```
    """
GUARDRAIL_CHECKER_PROMPT_TEMPLATE = \
    """
    Analyze the following feedback for relevance to code review improvement. Feedback is relevant if it:
    - Mentions specific files (e.g., 'file1.py'), code issues (e.g., 'syntax error'), or review sections ('syntax', 'standards','fixes','error analysis').
    - Provides actionable suggestions tied to code or review quality.
    Feedback is irrelevant if it:
    - Is general praise (e.g., 'good job'), criticism without context, or off-topic.
    Provide a JSON response with:
    - classification: 'relevant' or 'irrelevant'
    - explanation: Detailed reason for the classification
    - suggestion: If irrelevant, how to make it relevant
    Feedback: {feedback}
    Format: {{"classification": "relevant/irrelevant", "explanation": "reason", "suggestion": "how to improve if irrelevant"}}
    """
REVIEW_STRUCTURE_PROMPT_TEMPLATE = \
    """
    The review has sections: syntax, standards, error_analysis, final, each containing lists of issues per file.
    {{
        "review": {{
            "syntax": [ # syntax issues per file
                {{
                    "issues": [
                        {{
                            "location": "line number",
                            "file": "file name",
                            "description": "description text"
                        }},
                        {{
                            ...
                        }}
                    ]
                }},
                {{
                    ...
                }}
            ],
            "standards": [ # coding standards issues per file
                {{
                    "issues": [
                        {{
                            "location": "line number",
                            "file": "file name",
                            "standard": "standards text"
                        }},
                        {{
                            ...
                        }}
                    ]
                }},
                {{
                    ...
                }}
            ],
            "error_analysis": [ # error analysis per file
                {{
                    "messages": [
                        "analysis message"
                    ],
                    "issues": {{
                        "summary": "summary text",
                        "file": "file name",
                        "issues": [
                            {{
                                "type": "bug or vulnerability or others",
                                "locations": [
                                    "line numbers"
                                ],
                                "descriptions": [
                                    "description text"
                                ],
                                "certainty": [
                                    "certainty level"
                                ]
                            }},
                            {{
                                ...
                            }}
                        ]
                    }},
                    "current_diff": {{
                        "id": "diff id",
                        "file_path": "file name",
                        "content": "diff content"
                    }},
                    "tool_calls": [
                        "tool call detail"
                    ]
                }},
                {{
                    ...
                }}
            ],
            "final": [ # final review per file
                {{
                    "summary": "final summary",
                    "file": "file name",
                    "ratings": {{
                        "Rating Criteria for code quality": "rating value",
                        ...
                    }},
                    "critical_issues": [
                        "issue description",
                        ...
                    ]
                }},
                {{
                    ...
                }}
            ]
        }},
        "status": "completed",
        "artifacts": {{
            "fixes": [
                "fix detail or diff content",
                ...
            ],
            "summary": "consolidated diff summary"
        }}
    }}
    """
REREVIEW_PLANNER_PROMPT_TEMPLATE = \
    """
    Based on the feedback and previous context, identify which files and review steps (syntax, standards, error_analysis, final) need re-running.
    {review_structure}
    
    Current Feedback: {feedback}
    
    Previous Context:
    {episodic_context}
    Output a JSON like: {{"filename_1.py": ["syntax", "standards"], "filename_2.py": ["error_analysis"]}}
    """
REREVIEW_INSTRUCTION_GENERATOR_PROMPT_TEMPLATE = \
    """
    For the file {file} regarding the {step} step, based on:
    - Current feedback: '{feedback}'
    - User preferences: {preference_context}
    - Previous context: {episodic_context}
    
    Using the following code‐review JSON structure:
    {review_structure}
    
    These are the files associated with the review: 
    {files} 
    
    Use the files list to correct file names if you have been provided with the wrong file name or 
    in case you have to use indexes to access content from the review json the indexes for the files are given 
    in the list use them to access the content for the appropriate file.
    
    Your task: craft an instruction that suggests how to modify the existing {step} step
    in line with the user's feedback and previous context. The instruction must be phrased as a concrete suggestion
    to adjust the current {step} process.
    
    When asked a question, return a JSON object with:
    "queries": [ "<JMESPath expr1>", "<JMESPath expr2>", … ]
    You may emit multiple queries if the answer requires gathering data from different parts.
    
    Example for how the queries might look like:
        "queries":[
        "review.error_analysis[?current_diff.file_path=='file_1.py']",
        "review.syntax[].issues[?file=='file_2.py']"
        ]
    
    Provide specific instructions for re-running the {step} step.
    Return your response in JSON format with keys:
    "queries" and "instruction".
    """
SUFFICIENCY_CHECKER_PROMPT_TEMPLATE = \
    """
    Evaluate if the following feedback is detailed enough to guide code review changes. Sufficient feedback:
    These are the files associated with the review: {files} Use the files list to check if the user provided a non-existing or ambigious file.
    - Specifies files, issues, or review sections (e.g., 'syntax in file1.py').
    Insufficient feedback is vague or lacks context.
    Provide a JSON response with:
    - classification: 'sufficient' or 'insufficient'
    - explanation: Detailed reason for the classification
    - suggestion: If insufficient, how to make it sufficient
    Feedback: {feedback}
    Events that occurred in the episodic context: {episodic_context}
    Format: {{"classification": "sufficient/insufficient", "explanation": "reason", "suggestion": "how to improve if insufficient"}}
    """
LONG_TERM_MEMORY_PROMPT_TEMPLATE = \
    """
        Analyze the following interaction and existing preferences to identify or update user preferences.
        
        Current Interaction:
        {interaction}
        
        Existing Preferences:
        {existing_preferences}
        
        Return a single consolidated list of JSON objects representing the final state of all preferences.
        For each preference, include:
        {{
            "category": "The type of preference (code_style, review_focus, communication)",
            "preference": "The specific preference",
            "context": "Why this preference is important",
            "confidence": "How confident you are in this preference (0-1)",
            "supporting_evidence": ["List of interactions that support this preference"],
        }}
        
        Rules:
        1. Return a single list of JSON objects
        2. Include all valid preferences (both existing and new)
        3. Keep confidence scores between 0 and 1
        4. Ensure all JSON objects are valid and complete
        
        Return only the JSON array, no additional text or explanation.
    """