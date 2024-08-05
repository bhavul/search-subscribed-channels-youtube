import os
import json
import pandas as pd
import datetime
import time
import logging
from tqdm import tqdm
import webbrowser
import threading
from flask import Flask, request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import pickle
import sys
from googleapiclient.errors import HttpError

app = Flask(__name__)

# Load configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

SEARCH_TERM = config.get('search_term', 'LLM')
TIME_DURATION_DAYS = config.get('time_duration_days', 180)

# Define constants
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
REDIRECT_URI = 'http://localhost:8080/'

flow = None
credentials = None
server_thread = None
stop_server = threading.Event()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def callback():
    global flow, credentials
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    with open('token.pickle', 'wb') as token:
        pickle.dump(credentials, token)
    stop_server.set()
    return "Authorization successful! You can close this window and return to the terminal."

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'

def run_server():
    app.run(host='0.0.0.0', port=8080, threaded=True)

def get_authenticated_service():
    global flow, credentials, server_thread
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'credentials.json', 
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            logging.info(f"Please visit this URL to authorize the application: {auth_url}")
            webbrowser.open(auth_url)  # Automatically open the URL in the default browser
            
            server_thread = threading.Thread(target=run_server)
            server_thread.start()
            
            # Wait for credentials to be set by the callback
            while not credentials:
                time.sleep(1)
            
            # Stop the Flask server
            stop_server.set()
            server_thread.join(timeout=5)  # Wait for up to 5 seconds for the server to stop
            
            logging.info("Authorization complete. Proceeding with the script.")
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)
    
    return build('youtube', 'v3', credentials=credentials)

def exponential_backoff(func, max_retries=5, initial_delay=1):
    retries = 0
    delay = initial_delay
    while retries < max_retries:
        try:
            return func()
        except HttpError as e:
            if e.resp.status in [403, 429]:  # Quota exceeded or rate limit
                logging.warning(f"Quota exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay *= 2
            else:
                raise
    raise Exception("Max retries reached. Please try again later.")

def get_all_subscribed_channels(youtube):
    channels = []
    next_page_token = None
    while True:
        request = youtube.subscriptions().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=next_page_token
        )
        response = exponential_backoff(request.execute)
        channels.extend([item['snippet']['resourceId']['channelId'] for item in response['items']])
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return channels

def get_videos_from_channel(youtube, channel_id, query, published_after):
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        q=query,
        type="video",
        publishedAfter=published_after,
        maxResults=50
    )
    response = exponential_backoff(request.execute)
    return [video for video in response['items'] if query.lower() in video['snippet']['title'].lower()]

def save_progress(data, filename='progress.json'):
    with open(filename, 'w') as f:
        json.dump(data, f)

def load_progress(filename='progress.json'):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return None

def main():
    youtube = get_authenticated_service()

    # Get current date and date based on the time duration from config
    now = datetime.datetime.now()
    time_duration = now - datetime.timedelta(days=TIME_DURATION_DAYS)
    published_after = time_duration.isoformat("T") + "Z"

    # Load progress if available
    progress = load_progress()
    if progress:
        channels = progress['channels']
        video_data = progress['video_data']
        start_index = progress['last_processed_index'] + 1
        logging.info(f"Resuming from channel index {start_index}")
    else:
        # Get all subscribed channels
        logging.info("Fetching all subscribed channels...")
        channels = get_all_subscribed_channels(youtube)
        logging.info(f"Found {len(channels)} subscribed channels.")
        video_data = []
        start_index = 0

    # Collect video data
    logging.info(f"Fetching videos from subscribed channels containing '{SEARCH_TERM}'...")
    for i, channel in enumerate(tqdm(channels[start_index:], desc="Processing channels", initial=start_index, total=len(channels))):
        try:
            videos = get_videos_from_channel(youtube, channel, SEARCH_TERM, published_after)
            for video in videos:
                video_info = {
                    'Title': video['snippet']['title'],
                    'Channel Name': video['snippet']['channelTitle'],
                    'Video Length': 'N/A',  # Requires an additional API call to get video details
                    'Description': video['snippet']['description'],
                    'Video URL': f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                }
                video_data.append(video_info)
            
            # Save progress every 10 channels
            if (i + 1) % 10 == 0:
                save_progress({'channels': channels, 'video_data': video_data, 'last_processed_index': start_index + i})
                
            # Implement rate limiting
            time.sleep(1)  # Wait for 1 second between requests to avoid hitting rate limits
        except Exception as e:
            logging.error(f"Error processing channel {channel}: {str(e)}")
            save_progress({'channels': channels, 'video_data': video_data, 'last_processed_index': start_index + i - 1})
            raise

    # Create a DataFrame
    df = pd.DataFrame(video_data)

    # Save to CSV
    output_dir = '/app/output'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'youtube_videos.csv')
    df.to_csv(output_file, index=False)
    logging.info(f"CSV file saved to {output_file}")
    logging.info(f"Total videos found: {len(df)}")

    # Clean up progress file
    if os.path.exists('progress.json'):
        os.remove('progress.json')

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    try:
        main()
        logging.info("Script execution completed successfully. Exiting...")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        logging.info("Script execution interrupted. You can resume later from the last saved progress.")
    finally:
        sys.exit(0)