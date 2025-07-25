#!/usr/bin/env python3
import requests
import json
import hashlib
import time
import random
import argparse
import os
import math
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from io import StringIO

MAX_QUESTIONS = 500


POST_URL = "https://www.patreon.com/posts/132289911"

ANU_API_URL = "https://api.quantumnumbers.anu.edu.au"
REPO_URL = "https://github.com/paul-gauthier/quantum-random-ama-questions"

INTRO="""
In the
[May 2023 AMA at 1h12m](https://www.preposterousuniverse.com/podcast/2023/05/08/ama-may-2023/),
Trevor Morrissey asked Sean
if he would consider running a "quantum universe-splitter" bracket to pick one
of the questions he wasn't planning to answer.
If Everettian QM is correct, answering this one extra question would ensure that every question
definitely gets answered in at least one branch of the multiverse.
Sean invited someone else to create and run the bracket, since it sounded like too much work for him.

The table below lists [all {num_questions} questions submitted for this AMA]({post_url}),
sorted based on quantum random numbers generated by the
[ANU QRNG service](https://qrng.anu.edu.au).
So every permutation of the list will exist in some branch.

Sean can simply find the first question he wasn't planning to answer,
and then answer it too. This will ensure that
every question gets answered in some branch of the Everettian multiverse.

This list will be [updated]({repo_url}) periodically as new questions are [posted to Patreon]({post_url}).
"""



# Map from sha1(question_text) -> QRN from AU QRNG.
# No need to re-generate new QRN for questions we've already processed.
QRNG_CACHE = "qrng_cache.json"


# Map from Patreon post URL to Gist URL.
GIST_URLS_CACHE = "cache/gist-urls.json"


# Extract post ID from POST_URL and construct API URL
POST_ID = POST_URL.split('/')[-1]
POST_API_URL = f"https://www.patreon.com/api/posts/{POST_ID}"

# Load environment variables from .env file
load_dotenv()
# API Key should be set as an environment variable: ANU_QUANTUM_API_KEY
ANU_API_KEY = os.environ.get("ANU_QUANTUM_API_KEY")
# GitHub token should be set as an environment variable: GITHUB_TOKEN
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
# Patreon cookie should be set as an environment variable: PATREON_COOKIE
PATREON_COOKIE = os.environ.get("PATREON_COOKIE")

def get_title(use_quantum):
    """Generate the title string based on randomness source."""
    randomness_type = "Quantum" if use_quantum else "Pseudo"
    return f"Mindscape AMA Questions in {randomness_type} Random Order"

def get_quantum_randomness_for_new_questions(new_question_hashes, bits_per_question):
    """Generate quantum random numbers for new question hashes not in cache."""
    if not ANU_API_KEY:
        raise ValueError("ANU_QUANTUM_API_KEY not set")

    num_new_questions = len(new_question_hashes)
    if num_new_questions == 0:
        return {}

    total_bits_needed = num_new_questions * bits_per_question
    total_bytes_needed = math.ceil(total_bits_needed / 8.0)

    # Calculate how many API calls we need (max 1024 bytes per call)
    max_bytes_per_call = 1024
    api_calls_needed = math.ceil(total_bytes_needed / max_bytes_per_call)

    print(f"Need {total_bytes_needed} bytes total for {num_new_questions} new questions, making {api_calls_needed} API call(s)")

    all_hex_data = []

    for call_num in range(api_calls_needed):
        bytes_remaining = total_bytes_needed - (call_num * max_bytes_per_call)
        bytes_this_call = min(max_bytes_per_call, bytes_remaining)

        print(f"API call {call_num + 1}/{api_calls_needed}: requesting {bytes_this_call} bytes")

        response = requests.get(
            f"{ANU_API_URL}?length={bytes_this_call}&type=hex8&size=1",
            headers={"x-api-key": ANU_API_KEY},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            raise RuntimeError(f"ANU API call failed: {data}")

        # Process the payload from this API call
        payload = data.get("data", [])
        # Flatten if the API returned a list of lists (when size > 1)
        if payload and isinstance(payload[0], list):
            payload = [item for sub in payload for item in sub]

        # Convert payload to hex string
        hex_parts = []
        for byte in payload:
            if isinstance(byte, int):
                # Convert numeric bytes to 2-digit hex
                hex_parts.append(f"{byte:02x}")
            else:
                # Ensure each string element is two hex digits
                hex_parts.append(byte.zfill(2).lower())

        hex_string = "".join(hex_parts)

        # Verify we received the expected number of bytes
        if len(hex_string) != bytes_this_call * 2:
            raise RuntimeError(f"API call {call_num + 1} returned {len(hex_string)//2} bytes, expected {bytes_this_call}")

        all_hex_data.append(hex_string)

    # Combine all hex data
    combined_hex_string = "".join(all_hex_data)

    # Convert hex data to binary string
    binary_string = bin(int(combined_hex_string, 16))[2:].zfill(len(combined_hex_string) * 4)

    # Split into individual random numbers and map to hashes
    hash_to_random = {}
    for i, question_hash in enumerate(new_question_hashes):
        start_bit = i * bits_per_question
        end_bit = start_bit + bits_per_question
        question_bits = binary_string[start_bit:end_bit]
        hash_to_random[question_hash] = int(question_bits, 2)

    return hash_to_random

def load_qrng_cache():
    """Load the QRNG cache from disk."""
    if os.path.exists(QRNG_CACHE):
        try:
            with open(QRNG_CACHE, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read QRNG cache: {e}")
    return {}

def save_qrng_cache(cache):
    """Save the QRNG cache to disk."""
    try:
        with open(QRNG_CACHE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save QRNG cache: {e}")

def load_gist_urls_cache():
    """Load the Gist URLs cache from disk."""
    if os.path.exists(GIST_URLS_CACHE):
        try:
            with open(GIST_URLS_CACHE, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read Gist URLs cache: {e}")
    return {}

def save_gist_urls_cache(cache):
    """Save the Gist URLs cache to disk."""
    try:
        with open(GIST_URLS_CACHE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save Gist URLs cache: {e}")

def get_question_hash(question_text):
    """Get SHA1 hash of question text."""
    return hashlib.sha1(question_text.encode('utf-8')).hexdigest()

def get_random_numbers_for_questions(comments, use_quantum_randomness=False):
    """Get random numbers for questions, using cache for quantum randomness."""
    # Calculate bits needed for MAX_QUESTIONS
    bits_per_question = max(16, int(2 * math.log2(MAX_QUESTIONS) + 10))
    print("Bits/question:", bits_per_question)

    # Assert total questions is within limit
    total_questions = len(comments)
    assert total_questions < MAX_QUESTIONS, f"Too many questions ({total_questions}), maximum is {MAX_QUESTIONS-1}"

    # Generate hashes for all questions
    question_hashes = []
    for comment in comments:
        question_hash = get_question_hash(comment['text'])
        question_hashes.append(question_hash)

    if use_quantum_randomness:
        # Load existing cache
        qrng_cache = load_qrng_cache()

        # Get the cache for this specific bits_per_question value
        bits_key = str(bits_per_question)
        if bits_key not in qrng_cache:
            qrng_cache[bits_key] = {}

        bits_cache = qrng_cache[bits_key]

        # Find new hashes not in cache for this bits_per_question
        new_hashes = [h for h in question_hashes if h not in bits_cache]

        if new_hashes:
            print(f"Found {len(new_hashes)} new questions not in QRNG cache for {bits_per_question} bits")
            # Generate quantum random numbers for new questions
            new_random_numbers = get_quantum_randomness_for_new_questions(new_hashes, bits_per_question)

            # Update cache for this bits_per_question
            bits_cache.update(new_random_numbers)
            save_qrng_cache(qrng_cache)
            print(f"Updated QRNG cache with {len(new_hashes)} new entries for {bits_per_question} bits")
        else:
            print(f"All questions found in QRNG cache for {bits_per_question} bits")

        # Get random numbers from cache
        random_numbers = [bits_cache[h] for h in question_hashes]
        was_quantum_used = True

    else:
        # Use pseudo-random numbers (don't update cache)
        max_value = (1 << bits_per_question) - 1
        random_numbers = [random.randint(0, max_value) for _ in range(total_questions)]
        was_quantum_used = False

    return random_numbers, was_quantum_used, bits_per_question

def fetch_patreon_comments(use_cache=False):
    """
    Fetches all comments from a Patreon API endpoint using pagination.
    Returns a list of comment objects with username, text, and comment_url.

    Args:
        use_cache: If True, read from cache when available. Always writes to cache.
    """
    # Initial URL without the page[cursor] parameter to start from the beginning.
    # Retains page[count]=10 and sort=-created from the original example.
    current_url = f"{POST_API_URL}/comments2?include=parent%2Cpost%2Con_behalf_of_campaign.null%2Ccommenter_identity%2Ccommenter_identity.primary_avatar%2Ccommenter_identity.identity_badges%2Ccommenter.campaign.null%2Cfirst_reply.commenter.campaign.null%2Cfirst_reply.commenter_identity%2Cfirst_reply.commenter_identity.primary_avatar%2Cfirst_reply.commenter_identity.identity_badges%2Cfirst_reply.parent%2Cfirst_reply.post%2Cfirst_reply.on_behalf_of_campaign.null&fields[campaign]=[]&fields[comment]=body%2Ccreated%2Cdeleted_at%2Cis_by_patron%2Cis_by_creator%2Cis_liked_by_creator%2Cvote_sum%2Ccurrent_user_vote%2Creply_count%2Cvisibility_state&fields[display-identity]=name%2Clink_url&fields[identity-badge]=badge_type&fields[post]=comment_count%2Ccurrent_user_can_comment%2Curl&fields[post_tag]=tag_type%2Cvalue&fields[user]=image_url%2Cfull_name%2Curl&page[count]=10&sort=-created&json-api-version=1.0&json-api-use-default-includes=false"

    CACHE_DIR = "cache/"
    os.makedirs(CACHE_DIR, exist_ok=True)

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/vnd.api+json",
        "Cookie": PATREON_COOKIE or "",
        "Referer": "https://www.patreon.com/posts/ama-call-for-129279432",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
    }

    all_comments_data = [] # Stores raw comment data from API
    all_included_data = [] # Stores raw included data from API
    page_num = 1 # For logging page fetches

    try:
        while current_url:
            # Generate a cache filename based on the URL
            cache_filename = hashlib.md5(current_url.encode('utf-8')).hexdigest() + ".json"
            cache_file_path = os.path.join(CACHE_DIR, cache_filename)

            response_json = None

            if use_cache and os.path.exists(cache_file_path):
                try:
                    with open(cache_file_path, 'r') as f:
                        response_json = json.load(f)
                    print(f"Fetching page {page_num} from disk cache: {cache_file_path}")
                except (IOError, json.JSONDecodeError) as e:
                    print(f"Warning: Could not read or parse cache file {cache_file_path}: {e}. Fetching from network.")
                    response_json = None # Ensure it's None if cache read failed

            if response_json is None:
                print(f"Fetching page {page_num}")
                time.sleep(0.1)  # Add delay before fetching the next page
                response = requests.get(current_url, headers=headers)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                response_json = response.json()
                try:
                    with open(cache_file_path, 'w') as f:
                        json.dump(response_json, f)
                    print(f"Saved page {page_num} to disk cache: {cache_file_path}")
                except IOError as e:
                    print(f"Warning: Could not write cache file {cache_file_path}: {e}")

            comments_page_data = response_json

            if "data" in comments_page_data and isinstance(comments_page_data["data"], list):
                all_comments_data.extend(comments_page_data["data"])
            if "included" in comments_page_data and isinstance(comments_page_data["included"], list):
                all_included_data.extend(comments_page_data["included"])
            else:
                print("Could not find comments data in the current page response.")

            # Check for the next page URL
            if "links" in comments_page_data and "next" in comments_page_data["links"]:
                current_url = comments_page_data["links"]["next"]
                if current_url:
                    page_num += 1
                else:
                    # 'next' link is null, meaning last page reached
                    current_url = None
            else:
                # No 'links' or 'next' field, assume no more pages
                current_url = None

        if not all_comments_data:
            print("No comments found.")
            return []

        # Create a map of user_id to user full_name from included data
        user_map = {}
        for item in all_included_data:
            if item.get("type") == "user" and "id" in item and "attributes" in item and "full_name" in item["attributes"]:
                user_map[item["id"]] = item["attributes"]["full_name"]

        # Calculate stats
        total_comments_count = len(all_comments_data)
        top_level_comments_count = 0
        replies_count = 0

        for comment_item in all_comments_data:
            if comment_item.get("type") == "comment":
                # Check for parent relationship to determine if it's a reply
                if "relationships" in comment_item and \
                   "parent" in comment_item["relationships"] and \
                   comment_item["relationships"]["parent"].get("data") is not None:
                    replies_count += 1
                else:
                    top_level_comments_count += 1

        print(f"\n--- Comment Statistics ---")
        print(f"Total comments fetched: {total_comments_count}")
        print(f"Top-level comments: {top_level_comments_count}")
        print(f"Replies: {replies_count}")
        print(f"--------------------------")

        # Build list of comment objects
        comments = []
        for comment_item in all_comments_data:
            if comment_item.get("type") == "comment" and "attributes" in comment_item:
                body = comment_item["attributes"].get("body")
                comment_id = comment_item.get("id")
                commenter_name = "Unknown User"

                if "relationships" in comment_item and \
                   "commenter" in comment_item["relationships"] and \
                   "data" in comment_item["relationships"]["commenter"] and \
                   comment_item["relationships"]["commenter"]["data"] is not None and \
                   "id" in comment_item["relationships"]["commenter"]["data"]:
                    commenter_id = comment_item["relationships"]["commenter"]["data"]["id"]
                    commenter_name = user_map.get(commenter_id, "Unknown User")

                if not body:
                    continue

                # Construct comment URL
                comment_url = f"{POST_URL}?comment={comment_id}"

                comments.append({
                    "username": commenter_name,
                    "text": body,
                    "comment_url": comment_url
                })

        return comments

    except requests.exceptions.RequestException as e:
        print(f"Error fetching comments: {e}")
        return []
    except json.JSONDecodeError:
        print("Error decoding JSON response.")
        return []
    except KeyError as e:
        print(f"Unexpected JSON structure in response (e.g., missing 'links' or 'next' for pagination): {e}")
        return []

def upload_to_github_gist(content, gist_url=None, filename="ama_questions.md", description=None):
    """
    Upload content to a GitHub Gist. Creates new gist if gist_url is None, otherwise updates existing gist.
    Returns the Gist URL if successful, None otherwise.
    """
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not set. Cannot upload to GitHub Gist.")
        return None

    # Debug: Check token format
    print(f"Debug: Token starts with: {GITHUB_TOKEN[:10]}...")

    gist_data = {
        "description": description,
        "public": False,
        "files": {
            filename: {
                "content": content
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Python-Gist-Uploader"
    }

    # Determine if we're creating or updating
    if gist_url is None:
        # Create new gist
        url = "https://api.github.com/gists"
        method = "POST"
        expected_status = 201
        action = "Creating new"
    else:
        # Update existing gist - extract gist ID from URL
        # URL format: https://gist.github.com/username/gist_id
        gist_id = gist_url.split('/')[-1]
        url = f"https://api.github.com/gists/{gist_id}"
        method = "PATCH"
        expected_status = 200
        action = "Updating existing"

    print(f"Debug: {action} gist...")
    print(f"Debug: Headers: {dict((k, v if k != 'Authorization' else 'Bearer ***') for k, v in headers.items())}")

    try:
        if method == "POST":
            response = requests.post(url, json=gist_data, headers=headers, timeout=10)
        else:
            response = requests.patch(url, json=gist_data, headers=headers, timeout=10)

        print(f"Debug: Response status: {response.status_code}")
        print(f"Debug: Response headers: {dict(response.headers)}")

        if response.status_code != expected_status:
            print(f"Debug: Response body: {response.text}")

        response.raise_for_status()
        gist_info = response.json()
        return gist_info.get("html_url")
    except requests.exceptions.RequestException as e:
        print(f"Error uploading to GitHub Gist: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing GitHub Gist response: {e}")
        return None

def process_comments_with_randomness(comments, use_quantum_randomness=False, upload_gist=False):
    """
    Process a list of comment objects and display them with individual random numbers.
    """
    if not comments:
        print("\nNo comment texts to process.")
        return

    num_questions = len(comments)
    print(f"Processing {num_questions} questions...")

    # Get random numbers for questions
    random_numbers, was_quantum_used, bits_per_question = get_random_numbers_for_questions(comments, use_quantum_randomness)

    # Check for collisions
    if len(set(random_numbers)) != len(random_numbers):
        print("ERROR: Random number collision detected! This should be extremely rare.")
        print("Random numbers generated:", random_numbers)
        print("Unique random numbers:", set(random_numbers))
        sys.exit(1)

    # Pair each comment with its random number
    comment_random_pairs = []
    for i, comment in enumerate(comments):
        username = comment['username'].strip()
        text = f"**{username}** says: {comment['text']}"
        comment_random_pairs.append((random_numbers[i], text, comment['comment_url']))

    # Sort by random number
    comment_random_pairs.sort(key=lambda x: x[0])

    # Prepare table data
    table_rows = []
    for random_num, text_content, comment_url in comment_random_pairs:
        # Convert random number to binary for display
        binary_repr = format(random_num, f'0{bits_per_question}b')

        # Clean up text for markdown (escape pipes and newlines)
        clean_text = text_content.replace("\n", " ").replace("|", "\\|")

        table_rows.append((binary_repr, clean_text))

    # Generate column header based on randomness type
    random_number_header = f"{'Quantum' if was_quantum_used else 'Pseudo'} Random Number (Binary)"

    # Calculate column widths
    col1_width = max(len(random_number_header), max(len(row[0]) + 2 for row in table_rows) if table_rows else 0)  # +2 for backticks

    # Capture output for potential Gist upload
    output_buffer = StringIO()

    # Generate markdown content
    randomness_type = "Quantum" if was_quantum_used else "Pseudo"
    title = get_title(was_quantum_used)
    output_buffer.write(f"# {title}\n\n")
    output_buffer.write(INTRO.format(
        num_questions=num_questions,
        repo_url=REPO_URL,
        post_url=POST_URL)
    )
    output_buffer.write(f" Last updated on {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d at %H:%M %Z')}.\n\n")
    if not was_quantum_used:
        output_buffer.write("\nNote: this data was generated using pseudo-random numbers for testing.\n\n")

    # Write table header
    output_buffer.write(f"| {random_number_header:<{col1_width}} | Question |\n")
    output_buffer.write(f"|{'-' * (col1_width + 2)}|----------|\n")

    # Write table rows
    for binary_repr, text_content in table_rows:
        output_buffer.write(f"| `{binary_repr}`{' ' * (col1_width - len(binary_repr) - 2)} | {text_content} |\n")

    markdown_content = output_buffer.getvalue()
    #print(markdown_content)

    # Upload to GitHub Gist if requested
    if upload_gist:
        gist_urls_cache = load_gist_urls_cache()
        gist_url = gist_urls_cache.get(POST_URL)

        if gist_url is None:
            print("\nCreating new GitHub Gist...")
        else:
            print(f"\nUpdating existing GitHub Gist: {gist_url}")
        title = get_title(was_quantum_used)
        new_gist_url = upload_to_github_gist(markdown_content, gist_url=gist_url, description=title)
        if new_gist_url:
            if gist_url is None:
                print(f"Successfully created new GitHub Gist: {new_gist_url}")
                gist_urls_cache[POST_URL] = new_gist_url
                save_gist_urls_cache(gist_urls_cache)
            else:
                print(f"Successfully updated GitHub Gist: {new_gist_url}")
        else:
            print("Failed to upload to GitHub Gist.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Mindscape AMA comments and display randomized SHA1 prefixes.")
    parser.add_argument("--quantum", action="store_true", help="Use ANU Quantum RNG for randomness generation.")
    parser.add_argument("--gist", action="store_true", help="Upload the markdown table to a GitHub Gist.")
    parser.add_argument("--cache-urls", action="store_true", help="Read Patreon URLs from cache when available. Always writes to cache.")
    args = parser.parse_args()

    comments = fetch_patreon_comments(use_cache=args.cache_urls)
    process_comments_with_randomness(comments, use_quantum_randomness=args.quantum, upload_gist=args.gist)
