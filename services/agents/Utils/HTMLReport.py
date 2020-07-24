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
