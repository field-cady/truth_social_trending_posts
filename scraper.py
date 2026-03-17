import json
import os
import sys
from truthbrush.api import Api

def main():
    # 1. Setup API with credentials from environment variables
    username = os.environ.get('TRUTHSOCIAL_USERNAME')
    password = os.environ.get('TRUTHSOCIAL_PASSWORD')
    
    if not username or not password:
        print("Error: TRUTHSOCIAL_USERNAME or TRUTHSOCIAL_PASSWORD environment variables are missing.")
        sys.exit(1)

    api = Api(username=username, password=password)

    file_path = 'trending_posts.jsonl'
    
    # 2. Load existing post IDs to prevent duplicates
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
    print("Fetching top 100 trending posts...")
    try:
        trending_posts = api.trending(limit=100)
    except Exception as e:
        print(f"Error fetching trending posts: {e}")
        sys.exit(1)

    # 4. Filter and prepare new records
    new_records = []
    for post in trending_posts:
        post_id = post.get('id')
        
        if post_id in existing_ids:
            continue
            
        author = post.get('account', {})
        media_attachments = post.get('media_attachments', [])
        
        # Extract minimal media info
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

    # 5. Append new records to the file
    if new_records:
        print(f"Found {len(new_records)} new trending posts. Appending to file...")
        with open(file_path, 'a', encoding='utf-8') as f:
            for record in new_records:
                f.write(json.dumps(record) + '\n')
    else:
        print("No new trending posts found.")

if __name__ == "__main__":
    main()
