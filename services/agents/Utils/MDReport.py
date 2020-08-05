import json
import argparse

def generate_markdown(review_data):
    md = "# Code Review Report\n\n"

    # Report status
    md += "## Status\n"
    md += f"**Status:** {review_data.get('status', 'N/A')}\n\n"

    # Review sections
    review = review_data.get("review", {})

    # Syntax issues
    syntax_reviews = review.get("syntax", [])
    if syntax_reviews:
        md += "## Syntax Issues\n\n"
        for syntax in syntax_reviews:
            issues = syntax.get("issues", [])
            for issue in issues:
                md += f"- **File:** {issue.get('file', 'N/A')}\n"
                md += f"  - **Location:** {issue.get('location', 'N/A')}\n"
                md += f"  - **Description:** {issue.get('description', 'N/A')}\n\n"

    # Standards issues
    standards_reviews = review.get("standards", [])
    if standards_reviews:
        md += "## Standards Issues\n\n"
        for standard in standards_reviews:
            issues = standard.get("issues", [])
            for issue in issues:
                md += f"- **File:** {issue.get('file', 'N/A')}\n"
                md += f"  - **Location:** {issue.get('location', 'N/A')}\n"
                md += f"  - **Standard:** {issue.get('standard', 'N/A')}\n\n"

    # Error analysis
    error_analysis_list = review.get("error_analysis", [])
    if error_analysis_list:
        md += "## Error Analysis\n\n"
        for analysis in error_analysis_list:
            messages = analysis.get("messages", [])
            if messages:
                md += "**Messages:**\n"
                for message in messages:
                    md += f"- {message}\n"
                md += "\n"

            current_diff = analysis.get("current_diff", {})
            if current_diff:
                # Display the diff content inside a diff code block if available
                diff_content = current_diff.get("content", "")
                if diff_content:
                    md += "**Current Diff:**\n"
                    md += "```diff\n" + diff_content + "\n```\n\n"

            issues_info = analysis.get("issues", {})
            if issues_info:
                md += "**Issues Summary:**\n"
                summary = issues_info.get("summary", "")
                if summary:
                    md += f"- **Summary:** {summary}\n"
                file_name = issues_info.get("file", "")
                if file_name:
                    md += f"- **File:** {file_name}\n"
                detailed_issues = issues_info.get("issues", [])
                if detailed_issues:
                    md += "\n**Detailed Issues:**\n"
                    for issue in detailed_issues:
                        issue_type = issue.get("type", "N/A")
                        locations = issue.get("locations", [])
                        descriptions = issue.get("descriptions", [])
                        md += f"  - **Type:** {issue_type}\n"
                        if locations:
                            md += f"    - **Locations:** {', '.join(locations)}\n"
                        if descriptions:
                            md += f"    - **Descriptions:** {' '.join(descriptions)}\n"
                    md += "\n"
