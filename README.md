# Truth Social Trending Posts Scraper

This repository contains an automated pipeline designed to continuously scrape and archive the "Trending Truths" from Truth Social. Because trending topics change rapidly and are not historically archived by the platform, this tool ensures a permanent, durable record of trending posts.

## Architecture

This scraper runs entirely within **GitHub Actions** as a cron job every 10 minutes. Because Truth Social sits behind heavy Cloudflare Bot Management that actively blocks datacenter IP addresses (like those used by GitHub Actions), this project uses a specialized architecture to bypass those protections:

1. **GitHub Actions Workflow (`scrape.yml`)**: Orchestrates the cron schedule and commits the resulting data directly back to this repository, acting as a free, permanent database.
2. **FlareSolverr Service**: The workflow spins up a `ghcr.io/flaresolverr/flaresolverr` Docker container in the background. FlareSolverr acts as a proxy server that spins up a headless browser to solve Cloudflare's JavaScript challenges ("Just a moment...") before passing the API request through.
3. **Python Scraper (`scraper.py`)**: A lightweight script that asks FlareSolverr to fetch the Truth Social API using a pre-authenticated session token. It parses the resulting JSON, extracts relevant metadata (Author, URL, Timestamps, Media Attachments), and appends only *new*, deduplicated posts to a local file.

## Data Output (`trending_posts.jsonl`)

The extracted data is stored in the `trending_posts.jsonl` file. This is a **JSON Lines** file, meaning every single line in the file is a valid, independent JSON object representing one trending post. This format is highly memory-efficient and ideal for continuous appending.

### Example Record Format
```json
{
  "id": "11210987654321",
  "created_at": "2026-03-17T14:30:00.000Z",
  "author_id": "987654321",
  "author_username": "SomeUser",
  "url": "https://truthsocial.com/@SomeUser/posts/11210987654321",
  "content": "This is a trending post!",
  "replies_count": 142,
  "reblogs_count": 55,
  "favourites_count": 300,
  "media": [
    {
      "id": "123456",
      "type": "image",
      "url": "https://static-assets.truthsocial.com/..."
    }
  ]
}
```

## Setup & Configuration

To run this scraper in your own fork, you will need to extract a session token from an active Truth Social account and add it to your GitHub Secrets.

1. Log into `truthsocial.com` in your web browser.
2. Open **Developer Tools** (F12) -> **Network** tab.
3. Filter by `api` and trigger any action on the page (like viewing your profile).
4. Click on an API request, go to the **Headers** tab, and find the `Authorization` header in the Request Headers.
5. Copy the long string of characters *after* the word `Bearer `.
6. Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions**.
7. Create a new repository secret named `TRUTHSOCIAL_TOKEN` and paste your token as the value.

The GitHub Action will automatically pick up the token on its next scheduled run.
