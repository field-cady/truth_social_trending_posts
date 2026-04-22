import os
import sys
import json
import subprocess
import requests
import time
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime
from dotenv import load_dotenv
import re

# Load credentials from .env
load_dotenv()

def send_alert_email(subject, body):
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USERNAME')
    smtp_pass = os.environ.get('SMTP_PASSWORD')
    alert_email = os.environ.get('ALERT_EMAIL')

    if not all([smtp_server, smtp_user, smtp_pass, alert_email]):
        print("Skipping email alert: SMTP environment variables are not fully configured.")
        return

    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = alert_email

        print(f"Sending alert email to {alert_email}...")
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print("Alert email sent successfully.")
    except Exception as e:
        print(f"Failed to send alert email: {e}")

def fetch_via_flaresolverr():
    flaresolverr_url = os.environ.get('FLARESOLVERR_URL')
    if not flaresolverr_url:
        return None
        
    print(f"Using FlareSolverr at {flaresolverr_url} to bypass Cloudflare...")
    url = "https://truthsocial.com/api/v1/truth/trending/truths?limit=20"
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000
    }
    
    try:
        response = requests.post(flaresolverr_url, json=payload, timeout=70)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "ok":
                body = res_json.get("solution", {}).get("response", "")
                
                # FlareSolverr often returns the raw HTML of the page.
                # If the endpoint returns JSON, it might be wrapped in <pre> or body tags.
                # Let's try parsing it directly first
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    pass
                
                # If not direct JSON, extract with regex (it usually wraps it in HTML)
                match = re.search(r'(\{.*\}|\[.*\])', body, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass
                
                # Try scraping out HTML tags entirely
                text_only = re.sub(r'<[^>]+>', '', body).strip()
                try:
                    return json.loads(text_only)
                except json.JSONDecodeError:
                    print("Failed to decode JSON from FlareSolverr response.")
                    print("First 500 chars:", body[:500])
                    
        else:
            print(f"FlareSolverr HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error calling FlareSolverr: {e}")
        
    return None

def fetch_via_truthbrush():
    print("Running truthbrush trends locally...")
    result = subprocess.run(
        ["truthbrush", "trends"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode != 0:
        error_msg = f"CRITICAL ERROR RUNNING TRUTHBRUSH!\n\n{result.stderr}\n\nFailing loudly due to Truthbrush error (e.g. login failed, security code required)."
        print("\n" + "="*80)
        print(error_msg)
        print("="*80)
        send_alert_email("Truth Social Scraper Failed", error_msg)
        sys.exit(1)
        
    try:
        stdout = result.stdout.strip()
        if not stdout.startswith('['):
            idx = stdout.find('[')
            if idx != -1:
                stdout = stdout[idx:]
        
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        print("Failed to decode JSON from truthbrush output:", e)
        print("Output was:", result.stdout[:500])
        return None

def main():
    # Pause for a random time interval between 0 and 2 minutes
    delay = random.uniform(0, 120)
    print(f"Sleeping for {delay:.2f} seconds to randomize request timing...")
    time.sleep(delay)
    
    # 1. Try FlareSolverr first (for GitHub Actions)
    posts = fetch_via_flaresolverr()
    
    # 2. Fallback to truthbrush (for local testing)
    if not posts:
        posts = fetch_via_truthbrush()
        
    if not posts:
        print("Failed to fetch trending posts using any method.")
        sys.exit(1)

    now = datetime.utcnow().isoformat()
    
    # Save the full response blob to responses.jsonl
    response_blob = {
        "pulled_at": now,
        "data": posts
    }
    with open("responses.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(response_blob) + "\n")
        
    # Check existing IDs and save unique posts to posts.jsonl
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
