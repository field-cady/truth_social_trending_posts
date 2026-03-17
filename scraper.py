import json
import os
import sys
from curl_cffi import requests
import time
from dotenv import load_dotenv

# Load credentials from .env if present
load_dotenv()

# The ultimate Cloudflare bypass: Act like the official Android App.
MOBILE_USER_AGENT = "TruthSocial/334 (Android; 13; Scale/2.625)"

def get_token():
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    username = os.environ.get('TRUTHSOCIAL_USERNAME')
    password = os.environ.get('TRUTHSOCIAL_PASSWORD')
    
    if username and password:
        print("Attempting to authenticate via Username/Password to get a fresh token...")
        try:
            # We perform the login manually to capture specific backend error messages
            # rather than relying on truthbrush which swallows the 403 JSON body.
            payload = {
                'client_id': '9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4',
                'client_secret': 'ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M',
                'grant_type': 'password',
                'username': username,
                'password': password
            }
            headers = {
                'User-Agent': MOBILE_USER_AGENT,
                'Accept': 'application/json'
            }
            res = requests.post('https://truthsocial.com/oauth/token', json=payload, headers=headers, impersonate='chrome120')
            
            if res.status_code == 200:
                print("Successfully obtained new token via login.")
                return res.json().get("access_token")
            else:
                print("\n[!] AUTHENTICATION FAILED: Truth Social rejected your Username or Password.")
                print(f"    Server Response: {res.text}")
                print("    Falling back to TRUTHSOCIAL_TOKEN from .env if it exists...\n")
                
        except Exception as e:
            print(f"Network error during login: {e}")
            print("Falling back to provided token if available...")
            
    if token:
        print("Using provided TRUTHSOCIAL_TOKEN...")
        return token
        
    print("\nError: Could not obtain a token.")
    print("Your username/password was rejected (or missing), AND no TRUTHSOCIAL_TOKEN was provided.")
    print("Please fix your credentials in .env and try again.")
    sys.exit(1)

def fetch_trending(token):
    url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=100"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": MOBILE_USER_AGENT
    }

    print("Fetching trending truths via direct mobile API request...")
    try:
        api_res = requests.get(url, headers=headers, timeout=15, impersonate="chrome120")
        
        if api_res.status_code == 200:
            print("Direct request successful!")
            return api_res.json()
        elif api_res.status_code == 401:
            print(f"API rejected the token as invalid or expired (401 Unauthorized). Response: {api_res.text}")
            return None
        elif api_res.status_code == 403:
            print(f"Direct request got 403 (Cloudflare block or backend rejection). Response: {api_res.text}")
            return None
        else:
            print(f"Direct request failed with status {api_res.status_code}. Response: {api_res.text[:100]}")
            return None
            
    except Exception as e:
        print(f"Direct request failed: {e}")
        return None

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
