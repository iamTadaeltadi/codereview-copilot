from Utils.HTMLReport import generate_review_report
class MemoryManager:
    def __init__(self):
        self.pr_states = {}

    def save_review(self, pr_id: str, review_data: dict):
        self.pr_states[pr_id] = {
            'review': review_data["review"],
            'status': 'completed',
            'artifacts': {
                'fixes': review_data['fixes'],
                'summary': review_data['summary']
            }
        }

    def get_pr_state(self, pr_id: str):
        return self.pr_states.get(pr_id)

    def save_to_file(self, pr_id: str):
        import json
        from datetime import datetime
        import os
        filename = f"./reviews/{pr_id}_{datetime.now().isoformat()}.json"
        directory = os.path.dirname(filename)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(self.pr_states[pr_id], f, indent=2)
        generate_review_report(filename,"./reviews")
        return filename