import json
import os
import sys
import time
import requests
from truthbrush.api import Api
from dotenv import load_dotenv

# Load credentials from .env if present
load_dotenv()

def fetch_via_flaresolverr(url, token=None):
    flaresolverr_url = os.environ.get('FLARESOLVERR_URL')
    if not flaresolverr_url:
        return None
    
    print(f"Attempting to fetch {url} via FlareSolverr at {flaresolverr_url}...")
    
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000
    }
    
    if token:
        payload["headers"] = {"Authorization": f"Bearer {token}"}
        
    try:
        response = requests.post(flaresolverr_url, json=payload, timeout=70)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "ok":
                solution = res_json.get("solution", {})
                # For JSON endpoints, FlareSolverr might put the response in 'response' or we might need to parse 'response' from HTML if it's not handled correctly
                # But usually for API calls it works if the content-type is correct.
                # If it's a JSON response, 'response' field contains the body.
                body = solution.get("response", "")
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    print("Warning: Response body is not valid JSON. FlareSolverr might have returned HTML.")
                    print(f"Body preview: {body[:1000]}")
                    # Try to extract JSON from HTML using regex
                    import re
                    match = re.search(r'>(\s*\[.*?\]|\s*\{.*?\})\s*<', body, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(1))
                        except json.JSONDecodeError:
                            pass
                    return None
        print(f"FlareSolverr failed: {response.text}")
    except Exception as e:
        print(f"Error calling FlareSolverr: {e}")
    return None

def fetch_via_drissionpage(url, token):
    try:
        from DrissionPage import ChromiumPage
        from DrissionPage import ChromiumOptions
        import time
        import re
        
        print("Attempting to fetch via DrissionPage (local browser)...")
        co = ChromiumOptions()
        co.set_argument('--no-sandbox')
        page = ChromiumPage(co)
        
        # Go to main site to clear Cloudflare
        print("Loading truthsocial.com to solve Cloudflare challenge...")
        page.get('https://truthsocial.com')
        time.sleep(10) # Wait for challenge
        
        print("Fetching API endpoint via injected JS fetch...")
        js = f"""
            return fetch('{url}', {{
                method: 'GET',
                headers: {{
                    'Authorization': 'Bearer {token if token else ""}',
                    'Accept': 'application/json'
                }}
            }}).then(res => res.json()).catch(err => ({{'error': err.toString()}}));
        """
        data = page.run_js(js)
        
        page.quit()
        
        return data
    except ImportError:
        print("DrissionPage not installed. Skipping local browser fallback.")
        return None
    except Exception as e:
        print(f"Error fetching via DrissionPage: {e}")
        try:
            page.quit()
        except:
            pass
        return None

def get_api():
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    if token:
        print("Using TRUTHSOCIAL_TOKEN for authentication.")
        return Api(token=token)
        
    print("Warning: TRUTHSOCIAL_TOKEN missing. Attempting unauthenticated access (likely to fail).")
    return Api()

def main():
    file_path = 'trending_posts.jsonl'
    token = os.environ.get('TRUTHSOCIAL_TOKEN')
    flaresolverr_url = os.environ.get('FLARESOLVERR_URL')
    
    # Ensure the file exists
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

    # Fetch trending posts
    print("Fetching trending posts...")
    trending_posts = None
    
    # If in GitHub Actions (FlareSolverr is available)
    if flaresolverr_url:
        url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=20"
        trending_posts = fetch_via_flaresolverr(url, token)
    
    # Fallback to truthbrush (local testing)
    if not trending_posts:
        try:
            api = get_api()
            trending_posts = api.trending(limit=20)
        except Exception as e:
            print(f"Error fetching trending posts via truthbrush: {e}")
            
    # Fallback to DrissionPage (local residential connection bypassing Cloudflare)
    if not trending_posts:
        url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=20"
        trending_posts = fetch_via_drissionpage(url, token)

    if isinstance(trending_posts, dict) and 'errors' in trending_posts:
        print(f"API Error returned: {trending_posts}")
        trending_posts = None

    if not trending_posts:
        print("No trending posts returned by any method.")
        sys.exit(1)

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
