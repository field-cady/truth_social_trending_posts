import json
import os
import sys
import re
import requests as std_requests
from curl_cffi import requests
import time
from dotenv import load_dotenv

# Load credentials from .env if present
load_dotenv()

def fetch_trending(token):
    url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=100"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    # STEP 1: Attempt a direct request with curl_cffi (impersonating Chrome)
    # This works perfectly on Residential IPs (like your laptop) without needing FlareSolverr.
    print("Attempting direct authenticated API request...")
    try:
        api_res = requests.get(url, headers=headers, timeout=15, impersonate="chrome120")
        if api_res.status_code == 200:
            print("Direct request successful!")
            return api_res.json()
        elif api_res.status_code == 403:
            print("Direct request got 403 (Cloudflare block). Falling back to FlareSolverr...")
        else:
            print(f"Direct request failed with status {api_res.status_code}. Response: {api_res.text[:100]}")
    except Exception as e:
        print(f"Direct request failed: {e}. Falling back to FlareSolverr...")

    # STEP 2: FlareSolverr Fallback (for GitHub Actions/Datacenter IPs)
    setup_payload = {
        "cmd": "request.get",
        "url": "https://truthsocial.com/",
        "maxTimeout": 60000
    }
    
    print("Asking FlareSolverr to solve Cloudflare challenge on main page...")
    # Give it a moment to ensure FlareSolverr is up if we just started
    try:
        res = std_requests.post("http://localhost:8191/v1", json=setup_payload, timeout=65)
        res.raise_for_status()
        data = res.json()
        
        if data.get("status") == "ok":
            solution = data.get("solution", {})
            cookie_dict = {cookie['name']: cookie['value'] for cookie in solution.get("cookies", [])}
            user_agent = solution.get("userAgent", headers["User-Agent"])
            
            print(f"Obtained {len(cookie_dict)} cookies from FlareSolverr. Retrying API request...")
            headers["User-Agent"] = user_agent
            api_res = requests.get(url, headers=headers, cookies=cookie_dict, timeout=30, impersonate="chrome120")
            api_res.raise_for_status()
            return api_res.json()
    except Exception as e:
        print(f"FlareSolverr fallback failed: {e}")
        return None

def get_token():
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    username = os.environ.get('TRUTHSOCIAL_USERNAME')
    password = os.environ.get('TRUTHSOCIAL_PASSWORD')
    
    if username and password:
        print("Attempting to authenticate via Username/Password to get a fresh token...")
        try:
            from truthbrush.api import Api
            api = Api(username=username, password=password)
            new_token = api.get_auth_id(username, password)
            if new_token:
                print("Successfully obtained new token via login.")
                return new_token
        except Exception as e:
            print(f"Failed to login with username/password: {e}")
            print("Falling back to provided token if available...")
            
    if token:
        print("Using provided TRUTHSOCIAL_TOKEN...")
        return token
        
    print("Error: No valid TRUTHSOCIAL_TOKEN provided, and username/password login failed or was not provided.")
    sys.exit(1)

def main():
    token = get_token()

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
