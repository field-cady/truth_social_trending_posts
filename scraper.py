import json
import os
import sys
import re
import requests
import time

def fetch_trending(token):
    url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=100"
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,
        "headers": {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
    }
    
    print("Asking FlareSolverr to bypass Cloudflare and fetch API...")
    
    # Wait for flaresolverr to be ready (it might take a few seconds on boot)
    time.sleep(10)
    
    try:
        res = requests.post("http://localhost:8191/v1", json=payload, timeout=65)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"FlareSolverr request failed: {e}")
        return None
        
    if data.get("status") == "ok":
        html = data.get("solution", {}).get("response", "")
        
        # Chrome wraps JSON in a <pre> tag when viewing directly
        match = re.search(r'<pre[^>]*>(.*?)</pre>', html, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Fallback: strip basic HTML tags
            json_str = re.sub(r'<[^>]+>', '', html)
            
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            print("Failed to decode JSON from FlareSolverr. Raw response excerpt:")
            print(html[:1000])
            return None
    else:
        print(f"FlareSolverr returned error status: {data}")
        return None

def main():
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    
    if not token:
        print("Error: TRUTHSOCIAL_TOKEN environment variable is missing.")
        sys.exit(1)

    file_path = 'trending_posts.jsonl'
    
    # Ensure the file exists so git add doesn't fail
    if not os.path.exists(file_path):
        open(file_path, 'w').close()
    
    # Load existing post IDs
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

    # Fetch top 100 trending posts
    trending_posts = fetch_trending(token)

    if not trending_posts:
        print("Error: The API returned None or failed to bypass Cloudflare.")
        sys.exit(1)

    if not isinstance(trending_posts, list):
        print(f"Error: Expected a list of posts, got {type(trending_posts)}. Response was: {trending_posts}")
        sys.exit(1)

    # Filter and prepare new records
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

    # Append new records
    if new_records:
        print(f"Found {len(new_records)} new trending posts. Appending to file...")
        with open(file_path, 'a', encoding='utf-8') as f:
            for record in new_records:
                f.write(json.dumps(record) + '\n')
    else:
        print("No new trending posts found.")

if __name__ == "__main__":
    main()
