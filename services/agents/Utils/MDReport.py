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

            tool_calls = analysis.get("tool_calls_made", [])
            if tool_calls:
                md += "**Tool Calls Made:**\n"
                for call in tool_calls:
                    md += "```\n" + call + "\n```\n"
                md += "\n"

    # Final review section
    final_reviews = review.get("final", [])
    if final_reviews:
        md += "## Final Review\n\n"
        # The 'final' section is a list of lists.
        for file_review in final_reviews:
            md += f"### File: {file_review.get('file', 'N/A')}\n\n"
            md += f"**Summary:** {file_review.get('summary', '')}\n\n"

            # Ratings
            ratings = file_review.get("ratings", {})
            if ratings:
                md += "**Ratings:**\n"
                for category, rating in ratings.items():
                    md += f"- **{category}:** {rating}\n"
                md += "\n"

            # Critical issues
            critical_issues = file_review.get("critical_issues", [])
            if critical_issues:
                md += "**Critical Issues:**\n"
                for issue in critical_issues:
                    md += f"- {issue}\n"
                md += "\n"

    # Artifacts section (e.g., fixes and a summary)
    artifacts = review_data.get("artifacts", {})
    if artifacts:
        md += "## Artifacts\n\n"
        fixes = artifacts.get("fixes", [])
        if fixes:
            md += "### Fixes\n\n"
            for fix in fixes:
                md += "```\n" + fix + "\n```\n\n"
        summary_artifact = artifacts.get("summary", "")
        if summary_artifact:
            md += "### Artifact Summary\n\n" + summary_artifact + "\n\n"

    return md

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Markdown report from a JSON review file."
    )
    parser.add_argument("json_file", help="Path to the JSON review file")
    parser.add_argument("output_file", help="Path for the output Markdown file")
    args = parser.parse_args()

    # Load the JSON data
    try:
        with open(args.json_file, "r", encoding="utf-8") as infile:
            review_data = json.load(infile)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return

    # Generate Markdown content
    markdown_content = generate_markdown(review_data)

    # Save the Markdown content to a file
    try:
        with open(args.output_file, "w", encoding="utf-8") as outfile:
            outfile.write(markdown_content)
        print(f"Markdown report generated at: {args.output_file}")
    except Exception as e:
        print(f"Error writing Markdown file: {e}")

if __name__ == "__main__":
    main()
