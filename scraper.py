import json
import os
import sys
import time
import random
import truthbrush.api
from truthbrush.api import Api

# --- MONKEY-PATCH FOR BETTER STEALTH ---
# 1. Use a persistent session instead of creating a new one for every request
# 2. Add realistic browser headers
_original_make_session = Api._make_session
_persistent_session = None

def patched_make_session(self):
    global _persistent_session
    if _persistent_session is None:
        _persistent_session = truthbrush.api.requests.Session()
        # Set persistent headers that a real browser would have
        _persistent_session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "Connection": "keep-alive",
        })
    return _persistent_session

Api._make_session = patched_make_session

def main():
    # 1. Setup API with credentials from environment variables
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    username = os.environ.get('TRUTHSOCIAL_USERNAME')
    password = os.environ.get('TRUTHSOCIAL_PASSWORD')
    
    if token:
        print("Authenticating via Token...")
        api = Api(token=token)
    elif username and password:
        print("Authenticating via Username/Password...")
        api = Api(username=username, password=password)
    else:
        print("Error: TRUTHSOCIAL_TOKEN or TRUTHSOCIAL_USERNAME/PASSWORD environment variables are missing.")
        sys.exit(1)

    file_path = 'trending_posts.jsonl'
    
    # 2. Load existing post IDs
    existing_ids = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        existing_ids.add(record.get('id'))
                    except json.JSONDecodeError:
                        continue
                        
    print(f"Loaded {len(existing_ids)} existing posts.")

    # 3. Fetch top 100 trending posts
    # Add a small random jitter to avoid perfectly robotic timing
    sleep_time = random.uniform(2.0, 5.0)
    print(f"Fetching top 100 trending posts (waiting {sleep_time:.1f}s for stealth)...")
    time.sleep(sleep_time)
    
    try:
        trending_posts = api.trending(limit=100)
    except Exception as e:
        print(f"Error fetching trending posts: {e}")
        sys.exit(1)

    if trending_posts is None:
        print("Error: The API returned None. Cloudflare is likely blocking this GitHub Action runner.")
        print("Note: Datacenter IPs (like GitHub's) are often hard-blocked by Truth Social's WAF.")
        sys.exit(1)

    # 4. Filter and prepare new records
    new_records = []
    for post in trending_posts:
        if not isinstance(post, dict): continue # Safeguard
        post_id = post.get('id')
        
        if post_id in existing_ids:
            continue
            
        author = post.get('account', {})
        media_attachments = post.get('media_attachments', [])
        
        media_info = [
            {
                'id': m.get('id'),
                'type': m.get('type'),
                'url': m.get('url')
            } for m in media_attachments
        ]

        record = {
            'id': post_id,
            'created_at': post.get('created_at'),
            'author_id': author.get('id'),
            'author_username': author.get('acct'),
            'url': post.get('url'),
            'content': post.get('content'),
            'replies_count': post.get('replies_count'),
            'reblogs_count': post.get('reblogs_count'),
            'favourites_count': post.get('favourites_count'),
            'media': media_info
        }
        new_records.append(record)

    # 5. Append new records
    if new_records:
        print(f"Found {len(new_records)} new trending posts. Appending to file...")
        with open(file_path, 'a', encoding='utf-8') as f:
            for record in new_records:
                f.write(json.dumps(record) + '\n')
    else:
        print("No new trending posts found.")

if __name__ == "__main__":
    main()
