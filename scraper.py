import json
import os
import sys
import time
from truthbrush.api import Api
from dotenv import load_dotenv

# Load credentials from .env if present
load_dotenv()

def get_api():
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    username = os.environ.get('TRUTHSOCIAL_USERNAME')
    password = os.environ.get('TRUTHSOCIAL_PASSWORD')

    if username and password:
        print(f"Attempting to authenticate via Username: {username}")
        api = Api(username=username, password=password)
        auth_id = api.get_auth_id(username, password)
        if auth_id:
            print("Successfully obtained new token via login.")
            api.auth_id = auth_id
            return api
        else:
            print("\n[!] AUTHENTICATION FAILED: Truth Social rejected your Username or Password.")
            print("    Falling back to TRUTHSOCIAL_TOKEN from .env if it exists...\n")

    if token:
        print("Authenticating via Token...")
        return Api(token=token)
        
    print("Error: TRUTHSOCIAL_TOKEN or valid TRUTHSOCIAL_USERNAME/PASSWORD are missing from .env")
    sys.exit(1)

def main():
    api = get_api()
    file_path = 'trending_posts.jsonl'
    
    # Ensure the file exists so git add doesn't fail
    if not os.path.exists(file_path):
        open(file_path, 'w').close()
    
    # Load existing post IDs to prevent duplicates
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
    print(existing_ids)

    # Fetch top 100 trending posts
    print("Fetching top 100 trending posts...")
    try:
        # truthbrush uses 'trending' method for trending statuses
        trending_posts = api.trending(limit=10)
    except Exception as e:
        print(f"Error fetching trending posts: {e}")
        sys.exit(1)

    if not trending_posts:
        print("No trending posts returned. This might be a rate limit or connection issue.")
        sys.exit(1)

    print(trending_posts)
    # Filter and prepare new records
    new_records = []
    for post in trending_posts:
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

    # Append new records to the file
    if new_records:
        print(f"Found {len(new_records)} new trending posts. Appending to file...")
        with open(file_path, 'a', encoding='utf-8') as f:
            for record in new_records:
                f.write(json.dumps(record) + '\n')
    else:
        print("No new trending posts found.")

if __name__ == "__main__":
    main()
