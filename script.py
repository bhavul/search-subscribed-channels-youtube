import os
import json
import pandas as pd
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import pickle
from flask import Flask, request, redirect
import threading
import webbrowser
import logging
from tqdm import tqdm
import time

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

def run_server():
    app.run(host='0.0.0.0', port=8080)
    
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

def main():
    youtube = get_authenticated_service()

    # Function to get subscribed channels
    def get_subscribed_channels():
        request = youtube.subscriptions().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        channels = [item['snippet']['resourceId']['channelId'] for item in response['items']]
        return channels

    # Function to get videos from a channel
    def get_videos_from_channel(channel_id, query, published_after):
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            q=query,
            type="video",
            publishedAfter=published_after,
            maxResults=50
        )
        response = request.execute()
        return response['items']

    # Get current date and date based on the time duration from config
    now = datetime.datetime.now()
    time_duration = now - datetime.timedelta(days=TIME_DURATION_DAYS)
    published_after = time_duration.isoformat("T") + "Z"

    # Get subscribed channels
    logging.info("Fetching subscribed channels...")
    channels = get_subscribed_channels()
    logging.info(f"Found {len(channels)} subscribed channels.")

    # Collect video data
    video_data = []
    logging.info("Fetching videos from subscribed channels...")
    for channel in tqdm(channels, desc="Processing channels"):
        videos = get_videos_from_channel(channel, SEARCH_TERM, published_after)
        for video in videos:
            video_info = {
                'Title': video['snippet']['title'],
                'Channel Name': video['snippet']['channelTitle'],
                'Video Length': 'N/A',  # Requires an additional API call to get video details
                'Description': video['snippet']['description'],
                'Video URL': f"https://www.youtube.com/watch?v={video['id']['videoId']}"
            }
            video_data.append(video_info)

    # Create a DataFrame
    df = pd.DataFrame(video_data)

    # Save to CSV
    output_dir = '/app/output'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'youtube_videos.csv')
    df.to_csv(output_file, index=False)
    logging.info(f"CSV file saved to {output_file}")

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    main()