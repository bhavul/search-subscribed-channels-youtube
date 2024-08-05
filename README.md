# Search Subscribed Channels on YouTube for any Term

<p>
<img src="https://img.shields.io/github/last-commit/bhavul/search-subscribed-channels-youtube"/>
  <a href="https://www.buymeacoffee.com/bhavul" target="_blank"><img src="https://img.shields.io/badge/-buy_me_a%C2%A0coffee-gray?logo=buy-me-a-coffee" alt="Buy Me A Coffee"></a>
<br>  
</p>

This repository allows you to search matching videos from your subscribed channels on YouTube.

This project fetches videos from your subscribed YouTube channels that contain a specific search term in their title or description and were published within a specified time duration. The results are saved in a CSV file.

## Features

- Fetch videos from subscribed YouTube channels
- Search for videos containing a specific term
- Filter videos by a custom time duration
- Save results to a CSV file

## Prerequisites

- Docker
- Google Cloud Project with YouTube Data API v3 API enabled ("HOW TO" below)
- Service account credentials with necessary permissions ("HOW TO" below)

## Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:bhavul/search-subscribed-channels-youtube.git
   cd search-subscribed-channels-youtube
   ```
  
2. **[CRITICAL] Create and configure Google Cloud Project (get 'credentials.json')**:
  - Enable the YouTube Data API v3 API.
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project or select an existing one.
    - Enable the YouTube Data API v3 API for your project.
    - Create OAuth 2.0 Credentials:
      - In the left-hand menu, go to APIs & Services > Credentials.
      - Click on Create Credentials and select OAuth client ID.
      - (Optional) Configure OAuth Consent Screen:
        - If this is your first time creating an OAuth client ID, you will need to configure the OAuth consent screen.
        - Provide the required information such as application name, support email, and authorized domains.
        - Save the configuration.
      - Create OAuth Client ID:
        - Choose Web application as the application type
        - For Authorized JavaScript origins, you can leave it empty.
        - For Authorized redirect URIs, add http://localhost (this is required for the OAuth flow to work).
      - After creating the client ID, download the JSON and rename it to `credentials.json` and place it in the project directory.

3. **Edit `config.json`**:
  The config.json file allows you to customize the search term and time duration:
  ```json
  {
    "search_term": "LLM",
    "time_duration_days": 180
  }
  ```

  `search_term`: The term to search for in video titles and descriptions.
  `time_duration_days`: The number of days to look back from the current date.

4. **Build the Docker image**
  `docker build -t search-subscribed-channels-youtube .`

5. **Run the docker container**:
  `docker run -it -p 8080:8080 -v $(pwd)/output:/app/output search-subscribed-channels-youtube`

  - Authorization Process:
   - When you run the container, it will print a URL for authorization.
   - Copy this URL and open it in a web browser on your host machine.
   - Follow the authorization process in the browser.
   - After authorization, you should see "Authorization successful! You can close this window and return to the terminal.". 
   - Once that is done, get back to terminal and wait for output to be generated, and script to exit.

6. **Output** 
  The script saves the results in a CSV file located in the output directory.

## Troubleshooting

- If you encounter permission issues, ensure that your service account has the correct roles and that the APIs are enabled in your Google Cloud project.

- Docker logs, in case container fails to run : 
  `docker logs $(docker ps -lq)`

## Contributions & Feedback

Any Issues and Contributions are welcome! 