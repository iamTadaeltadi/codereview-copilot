import json
import html  # new import
from pathlib import Path
import argparse

# Load the JSON data
def load_review_json(json_path):
    with open(json_path, 'r') as f:
        return json.load(f)

# Generate HTML content from the template and JSON data
def generate_html_report(review_data):
    # Calculate summary statistics
    critical_count = sum(len(file['critical_issues']) for file in review_data["review"]['final'])
    warning_count = sum(len(file.get("issues",[])) for file in review_data['review']['syntax'])
    standards_count = sum(len(file.get("issues",[])) for file in review_data['review']['standards'])

    # Generate file links for the sidebar
    file_links = "\n".join(
        f'<a href="#file-{index}" class="list-group-item list-group-item-action">'
        f'{file_data["file"]}'
        f'<span class="badge bg-danger float-end">{len(file_data["critical_issues"])}</span>'
        f'</a>'
        for index, file_data in enumerate(review_data["review"]['final'])
    )

    # Generate file summaries for the summary section
    file_summaries = "\n".join(
        f'<li class="list-group-item d-flex justify-content-between align-items-center">'
        f'{file_data["file"]}'
        f'<span class="badge bg-danger">{len(file_data["critical_issues"])}</span>'
        f'</li>'
        for file_data in review_data["review"]['final']
    )

    # Generate the main content for each file
    main_content = "\n".join(
        f'''
        <div class="review-section" id="file-{index}">
            <div class="file-header mb-4">
                <h4>{file_data["file"]}</h4>
                <p class="mb-0">{file_data["summary"]}</p>
            </div>

            <!-- Ratings -->
            <div class="card mb-4">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Ratings</h6>
                    <div class="row">
                        {"".join(
                            f"""<div class="col-md-4">
                                <div class="card mb-2">
                                <div class="card-body p-2">
                                <small>{category}</small>
                                <div class="progress">
                                <div class="progress-bar" role="progressbar" style="width: {(int(score.split(':')[0] if score.split(':')[0].isdigit() else 0) / 10) * 100}%" aria-valuenow="{int(score.split(':')[0] if score.split(':')[0].isdigit() else 0)}" aria-valuemin="0" aria-valuemax="10">
                                {str(int(score.split(':')[0]))+"/10" if score.split(':')[0].isdigit() else "N/A"}
                                </div>
                                </div>
                                </div>
                                </div>
                                </div>"""
                            for category, score in file_data["ratings"].items()
                        )}
                    </div>
                </div>
            </div>

            <!-- Critical Issues -->
            <div class="card vulnerability mb-4">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Critical Issues</h6>
                    {"".join(
                        f"""<div class="issue-card">
                            <div class="card-body p-3">
                                <p class="card-text">{(issue)}</p>
                            </div>
                        </div>"""
                        for issue in file_data["critical_issues"]
                    )}
                </div>
            </div>

            <!-- Syntax Issues -->
            <div class="card syntax-issue mb-4">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Syntax Issues</h6>
                    {"".join(
                        f"""<div class="issue-card">
                            <div class="card-body p-3">
                                <h6 class="card-subtitle mb-2 text-muted">Line {issue["location"]}</h6>
                                <p class="card-text">{issue["description"]}</p>
                            </div>
                        </div>"""
                        for syntax in review_data["review"]["syntax"]
                        for issue in syntax.get("issues",{})
                        if issue and issue["file"] == file_data["file"]
                    )}
                </div>
            </div>

            <!-- Standards Issues -->
            <div class="card standard-issue mb-4">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Standards Issues</h6>
                    {"".join(
                        f"""<div class="issue-card">
                            <div class="card-body p-3">
                                <h6 class="card-subtitle mb-2 text-muted">Line {issue["location"]}</h6>
                                <p class="card-text">{issue["standard"]}</p>
                            </div>
                        </div>"""
                        for standard in review_data["review"]["standards"]
                        for issue in standard.get("issues",{})
                        if issue and issue["file"] == file_data["file"]
                    )}
                </div>
            </div>

            <!-- Suggested Fixes -->
            <div class="card mb-4">
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">Suggested Fixes</h6>
                    <div class="fixes" data-markdown="{html.escape(review_data['artifacts']['fixes'][index])}"></div>
                </div>
            </div>
        </div>
        '''
        for index, file_data in enumerate(review_data["review"]['final'])
    )

    # Format the HTML template with the data
    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Code Review Report</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f8f9fa; }}
            .nav-sidebar {{ position: sticky; top: 20px; }}
            .review-section {{ margin-bottom: 2rem; }}
            .issue-card {{ margin-bottom: 1rem; border-left: 4px solid #6c757d; }}
            .vulnerability {{ border-left-color: #dc3545; }}
            .syntax-issue {{ border-left-color: #ffc107; }}
            .standard-issue {{ border-left-color: #0dcaf0; }}
            pre {{ background-color: #f8f9fa; padding: 1rem; border-radius: 4px; }}
            .file-header {{ background-color: #e9ecef; padding: 1rem; border-radius: 4px; }}
            .fixes {{ display: block; padding: 1rem; margin-top: 1rem; color: #000; background-color: #fff; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container py-5">
            <h1 class="mb-4">Code Review Report</h1>
            
            <!-- Summary Section -->
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Summary</h5>
                    <p class="card-text">
                        <span class="badge bg-danger">{critical_count} Critical Issues</span>
                        <span class="badge bg-warning">{warning_count} Warnings</span>
                        <span class="badge bg-info">{standards_count} Standards Issues</span>
                    </p>
                    <ul class="list-group list-group-flush">
                        {file_summaries}
                    </ul>
                </div>
            </div>

            <!-- Navigation Sidebar -->
            <div class="row">
                <div class="col-md-3">
                    <div class="nav-sidebar">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="card-subtitle mb-2 text-muted">Files Reviewed</h6>
                                <div class="list-group">
                                    {file_links}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Content -->
                <div class="col-md-9">
                    {main_content}
                </div>
            </div>
        </div>

