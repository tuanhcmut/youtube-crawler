# YouTube Data Crawler API

## Project Overview

The YouTube Data Crawler API is a FastAPI application designed to interact with YouTube to retrieve and process video details, captions, and comments. This application allows users to start crawling for video data, fetch detailed information about videos, and download captions in various formats (SRT, JSON, XML). It also provides a mechanism for tracking the status of crawled videos and their associated comments.

The core functionality for crawling YouTube data is encapsulated in the `YoutubeCrawler` class, located in `crawler.py`. This class handles the retrieval of video details, captions, and comments using YouTube’s internal APIs.

## Question 2: Handling YouTube Limit
When crawling YouTube, you might encounter challenges such as rate limits and CAPTCHAs. We can handle these by:

1. Throttling and Retries
   - Throttle Requests: Introduce delays between requests to manage load such as "sleep: parameter or "comments_limt" variable
   - Exponential Backoff: Retry failed requests with increasing delay intervals.

2. Consent Handling
   - Automated Consent: Manage consent requests as shown in the `YoutubeCrawler` class by starting a new session such as new_session()

3. Proxy Usage
   - IP Rotation: Use rotating proxies to distribute requests across different IP addresses to avoid being blocked.

4. Avoid Detection
   - Randomize User-Agent: Use various User-Agent strings for requests to avoid detection patterns.
   - Simulate Human Behavior: Mimic natural browsing patterns with randomized request intervals and interactions/contexts.

5. YouTube API
   - YouTube Data API: Use the official YouTube Data API for structured access to video details, comments, and more (https://developers.google.com/youtube/v3)
     
## Setup Instructions

1. **Ensure Python 3.8 is Installed**

    This project has been tested with Python 3.8. Make sure you have Python 3.8 installed on your system.

2. **Clone the Repository**

    ```bash
    git clone https://github.com/tuanhcmut/youtube-crawler.git
    cd youtube-crawler
    ```

3. **Install Required Packages**

    Install the 3 necessary Python packages by running:

    ```bash
    pip install fastapi httpx uvicorn
    ```

4. **Run the Application**

    ```bash
    uvicorn crawl:app --reload
    ```

    The application will be available at `http://127.0.0.1:8000`.
   
6. **Modifying url list to crawl**
   
   You can set the urls list once the current crawling task is done at frontend by accessing the tracking page located at `http://127.0.0.1`
   At backend we will be modifying the `urls` global variable located in the `crawl.py` file and then we call `start_crawling(urls)` to do the work
   
## API Documentation

You can explore and test the API using the interactive documentation provided by FastAPI:

- **Swagger UI**: Access the interactive API documentation at `http://127.0.0.1:8000/docs`
- **ReDoc**: Access an alternative API documentation at `http://127.0.0.1:8000/redocs`

### `GET /status`

**Description:** Retrieve the current status of all crawled videos.

**Response:**

- **200 OK**
  ```json
  [
    {
      "videoId": "video_id",
      "details": { ... },
      "captions": 5,
      "comments": 100
    }
    ...
  ]
  ```

### `POST /crawl`

**Description:** Start or restart crawling for a new set of URLs.

**Request Body:**

- `urls` (List of strings): List of YouTube video URLs to crawl.
- `limit` (int, optional): Limit on the number of comments to retrieve (default is 1000).

**Response:**

- **200 OK**
  ```json
  true
  ```

### `GET /`

**Description:** Serve the tracking page by a static HTML file `combined.html`.

**Response:**

- **200 OK**
  Returns the `combined.html` file.

## YoutubeCrawler Class

The `YoutubeCrawler` class is responsible for fetching video details, captions, and comments from YouTube. 

### Key Methods:

- **`__init__(self, video_id: str)`**: Initializes the crawler with the given video ID and sets up the necessary HTTP client and headers.

- **`async def new_session()`**: Creates a new HTTP session with updated headers and cookies.

- **`async def _fetch_data()`**: Fetches video data from YouTube using a POST request.

- **`async def get_video_details()`**: Retrieves video details from the fetched data.

- **`async def get_captions()`**: Retrieves captions information from the fetched data.

- **`async def _fetch_and_handle_page(self, youtube_url)`**: Handles consent if required, and fetches necessary configuration and initial data from the page.

- **`async def _ajax_request(self, endpoint, retries=5, sleep=20, timeout=60)`**: Makes an AJAX request to the YouTube API and handles retries.

- **`async def stop_fetching_comments(self)`**: Stops the comment fetching process.

- **`async def get_comments(self, all_comments = [], language=None, sleep=.1, newest_first=False, limit=None)`**: Fetches comments from a YouTube video, with options to set language, sort by newest, and limit the number of comments.

### Helper Methods:

- **`_set_language(self, language)`**: Sets the language for the YouTube API context.

- **`_handle_comments(self, comments, all_comments, limit)`**: Processes and appends comments to the list.

- **`async def _get_sort_menu(self)`**: Retrieves the sorting menu for comments.

- **`def _handle_response(self, response, continuations)`**: Handles the response from the API and processes comments.

- **`def _parse_comments(self, response)`**: Parses and extracts individual comments from the response.

- **`@staticmethod def _regex_search(text, pattern, group=1, default=None)`**: Performs regex search to find specific patterns in text.

- **`@staticmethod def _search_dict(partial, search_key)`**: Searches for a key in nested dictionaries.

## Architecture Choices

1. **FastAPI**: Chosen for its performance and ease of use for creating APIs. It provides automatic interactive documentation and supports asynchronous operations, which is crucial for handling network I/O efficiently.

2. **Asynchronous Programming**: Utilizes `asyncio` and `httpx` to handle multiple video fetch operations concurrently. This design improves the efficiency and scalability of the crawling process.

3. **YoutubeCrawler Class**: Encapsulates all YouTube-specific crawling logic, separating concerns between API management and data retrieval.

4. **Data Storage**: Data is stored in a local directory structure (`crawled/`) with separate files for captions and details. This approach simplifies data access and management.

5. **Modularity**: Functions for different formats (SRT, JSON, XML) are modularized to ensure flexibility in handling various caption formats.

By adopting these architecture choices, the project aims to be robust, scalable, and maintainable while providing a clear structure for further development and enhancement.
