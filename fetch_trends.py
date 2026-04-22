import os
import sys
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

def main():
    print("Running truthbrush trends...")
    
    # Run the truthbrush trends command and capture output
    result = subprocess.run(
        ["truthbrush", "trends"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode != 0:
        print("Error running truthbrush trends:", result.stderr)
        sys.exit(1)
        
    try:
        # Extract the JSON array from truthbrush output (ignoring any log prefix)
        stdout = result.stdout.strip()
        if not stdout.startswith('['):
            idx = stdout.find('[')
            if idx != -1:
                stdout = stdout[idx:]
        
        posts = json.loads(stdout)
    except json.JSONDecodeError as e:
        print("Failed to decode JSON from truthbrush output:", e)
        print("Output was:", result.stdout[:500])
        sys.exit(1)

    now = datetime.utcnow().isoformat()
    
    # 1. Save the full response blob to responses.jsonl
    response_blob = {
        "pulled_at": now,
        "data": posts
    }
    with open("responses.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(response_blob) + "\n")
        
    # 2. Check existing IDs and save unique posts to posts.jsonl
    existing_ids = set()
    posts_file = "posts.jsonl"
    if os.path.exists(posts_file):
        with open(posts_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        if "id" in record:
                            existing_ids.add(record["id"])
                    except json.JSONDecodeError:
                        pass
                        
    new_posts_count = 0
    with open(posts_file, "a", encoding="utf-8") as f:
        for post in posts:
            post_id = post.get("id")
            if post_id and post_id not in existing_ids:
                f.write(json.dumps(post) + "\n")
                existing_ids.add(post_id)
                new_posts_count += 1
                
    print(f"Successfully appended response to responses.jsonl")
    print(f"Added {new_posts_count} new unique posts to posts.jsonl out of {len(posts)} fetched.")

if __name__ == "__main__":
    main()
