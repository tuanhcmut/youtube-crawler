import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import httpx
from crawler import YoutubeCrawler
import json 
import xml.etree.ElementTree as ET
from html import unescape
from fastapi.middleware.cors import CORSMiddleware
from typing import List 
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlparse, parse_qs

folder = 'crawled'
done = False 
comments_limit = 1000 
urls = [
    "https://www.youtube.com/watch?v=JXPitkep4oo"
]


# Ensure the folder exists
os.makedirs(folder, exist_ok=True)

crawler_dict = dict()
status_dict = dict()

def extract_video_id(url: str) -> str:
    """
    Extract the video ID from a YouTube URL.
    """
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get('v', [None])[0]

async def fetch_xml(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

def caption_to_xml(xml_content):
    root = ET.fromstring(xml_content)
    
    for text_element in root.findall('text'):
        start = float(text_element.get('start'))
        duration = float(text_element.get('dur'))
        end = start + duration
        
        text_element.set('end', str(end))
    
    updated_xml_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
    return updated_xml_content

def caption_to_json(xml_content):
    root = ET.fromstring(xml_content)
    subtitles = []
    
    for text_element in root.findall('text'):
        start = float(text_element.get('start'))
        duration = float(text_element.get('dur'))
        end = start + duration
        text = text_element.text.strip()
        
        subtitles.append({
            'text': text,
            'start': start,
            'dur': duration,
            'end': end
        })
    
    return subtitles

def caption_to_srt(xml_content):
    root = ET.fromstring(xml_content)
    subtitles = []
    index = 1
    
    for text_element in root.findall('text'):
        start = float(text_element.get('start'))
        duration = float(text_element.get('dur'))
        end = start + duration
        text = text_element.text.strip()
        
        start_time = f"{int(start // 3600):02}:{int((start % 3600) // 60):02}:{int(start % 60):02},{int((start % 1) * 1000):03}"
        end_time = f"{int(end // 3600):02}:{int((end % 3600) // 60):02}:{int(end % 60):02},{int((end % 1) * 1000):03}"
        
        subtitles.append(f"{index}\n{start_time} --> {end_time}\n{text}\n")
        index += 1
    
    return "\n".join(subtitles)

def save_to_file(content, filename: str):
    file_path = os.path.join(folder, filename)
    os.makedirs(folder, exist_ok=True)  # Ensure the folder exists
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def save_to_json(data: dict, filename: str):
    file_path = os.path.join(folder, filename)
    os.makedirs(folder, exist_ok=True)  # Ensure the folder exists
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def init_status_dict(urls):
    global status_dict
    status_dict.clear()
    for url in urls:
        video_id = extract_video_id(url)
        status_dict.setdefault(video_id, {})

def smaller_details(video_info):
    result = { 
        "videoId": video_info.get("videoId"),
        "title": video_info.get("title"),
        "lengthSeconds": video_info.get("lengthSeconds"),
        "channelId": video_info.get("channelId"),
        "viewCount": video_info.get("viewCount"),
        "author": video_info.get("author")
    }
    return result 

async def crawl_video_details(downloader, download_captions = True):
    try:
        video_id = downloader.video_id
        video_details = await downloader.get_video_details()
        global status_dict
        status_dict.get(video_id).setdefault("details", smaller_details(video_details))

        video_captions = await downloader.get_captions()
        video_details.setdefault("captions", video_captions)
        status_dict.get(video_id).setdefault("_captions", len(video_captions))
        save_to_json(status_dict, "details_" + video_id + ".json")
        if download_captions:
            await crawl_video_captions(downloader)
    except httpx.RequestError:
        return None

async def crawl_video_caption(video_id, caption, filetype = "srt"):
    try:
        url = caption["baseUrl"]
        languageCode = caption["languageCode"]
        languageName = caption["name"]["simpleText"]

        xml_content = await fetch_xml(url)
        xml_content = unescape(xml_content)

        if filetype == "srt":
            content = caption_to_srt(xml_content)
            filename = f"{languageCode}_({languageName})_{video_id}.srt"
            save_to_file(content, filename)
        elif filetype == "json":
            content = caption_to_json(xml_content)
            filename = f"{languageCode}_({languageName})_{video_id}.json"
            save_to_json(content, filename)
        else:
            content = caption_to_xml(xml_content)
            filename = f"{languageCode}_({languageName})_{video_id}.xml"
            save_to_file(content, filename)
        
    except Exception as e:
        return None

async def crawl_video_captions(downloader:YoutubeCrawler):
    try:
        video_id = downloader.video_id
        global status_dict 
        captions = await downloader.get_captions()
        tasks = [crawl_video_caption(video_id, caption) for caption in captions]
        await asyncio.gather(*tasks)
        status_dict.get(video_id).setdefault("captions",  len(tasks))

    except httpx.RequestError:
        return None

async def crawl_video_comments(downloader):
    try:
        video_id = downloader.video_id
        video_comments = []
        global comments_limit
        await downloader.get_comments(video_comments, limit = comments_limit)
        global status_dict
        status_dict.get(video_id).setdefault("comments", len(video_comments))
    except httpx.RequestError:
        return None

async def fetch_video(url):
    try:
        video_id = extract_video_id(url)
        crawler = YoutubeCrawler(video_id)
        crawler_dict[video_id] = crawler
        crawl_details_task = crawl_video_details(crawler)
        crawl_comments_task = crawl_video_comments(crawler)
        tasks = [crawl_details_task, crawl_comments_task]
        results = await asyncio.gather(*tasks)
        status_dict.get(video_id).setdefault("status", "Done")
        return results 
    except httpx.RequestError:
        return None

async def start_crawling(urls):
    init_status_dict(urls)
    tasks = [fetch_video(url) for url in urls]
    results = await asyncio.gather(*tasks)
    global done
    done = True




app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)



@app.on_event("startup")
async def startup_event():
    global urls
    asyncio.create_task(start_crawling(urls))

@app.get("/status")
async def get_status():
    global crawler_dict
    global status_dict
    for k,v in status_dict.items():
        if v.get("comments") is None:
            v["_comments"] = crawler_dict[k].count_fetching_comments()
        else:
            try:
                del v["_comments"]
            except KeyError:
                pass
    return list(status_dict.values())

@app.post("/crawl")
async def crawl(urls: List[str], limit: int = comments_limit):
    global done
    if not done:
        return None
    done = False 
    global comments_limit
    comments_limit = limit
    asyncio.create_task(start_crawling(urls))
    return True


@app.get("/")
async def read_index():
    return FileResponse("combined.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
