from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from pytube import YouTube
from django.conf import settings
import os
import assemblyai as aai
import sys
import requests
import re
import html
import yt_dlp
import time
from openai import OpenAI 
import time

sys.stdout.reconfigure(encoding="utf-8")  # Ensure UTF-8 encoding for output
#from urllib.error import HTTPError
YOUTUBE_API_KEY = "AIzaSyAp1w0fbU6_XXGKWUpvkeSXrdVSvhPJSwU"
# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

# Function to generate blog


# Function to generate blog
@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data.get('link')  # Use .get() to avoid KeyError
            
            if not yt_link:
                return JsonResponse({'error': 'Missing YouTube link'}, status=400)

            # Get YouTube title
            title_info = yt_title(yt_link)
            if "error" in title_info:
                return JsonResponse({'error': title_info["error"]}, status=400)

            print(title_info)  # Debugging output
            
            # Download YouTube audio
            audio_path = download_audio(yt_link, title_info["title"])
            if not audio_path:
                return JsonResponse({'error': 'Failed to download audio'}, status=500)
            # Future functionality: fetch transcript, generate blog, save to DB
            # FETCH TRANSCRIPT
            local_audio_path = os.path.join(settings.MEDIA_ROOT, os.path.basename(audio_path))  # Convert URL to file path
            transcription = get_transcript(local_audio_path)  # Pass local file path
            print(transcription)
            
            # GENERATE BLOG
            blog_content= generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error':'Failed to generate blog'})
            
             # Return the blog as response
            #return JsonResponse({'title_info': title_info, 'audio_path': audio_path, 'message': 'Blog generation in progress'})
            return JsonResponse({'content': transcription})
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Function to extract video ID from YouTube link
def extract_video_id(link):
    pattern = (
        r"(?:https?:\/\/)?(?:www\.)?"
        r"(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)"
        r"([a-zA-Z0-9_-]{11})"
    )
    match = re.search(pattern, link)
    return match.group(1) if match else None

# Clean special characters in description
def clean_description(description):
    return html.unescape(description) if description else "No description available"

# Extract social media links & emails
def extract_social_links(description):
    social_patterns = {
        "Instagram": r"(https?://(www\.)?instagram\.com/[^\s]+)",
        "Twitter": r"(https?://(www\.)?twitter\.com/[^\s]+)",
        "Facebook": r"(https?://(www\.)?facebook\.com/[^\s]+)",
        "TikTok": r"(https?://(www\.)?tiktok\.com/[^\s]+)"
    }
    social_links = {platform: re.findall(pattern, description)[0][0] for platform, pattern in social_patterns.items() if re.findall(pattern, description)}
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", description)
    return {"social_links": social_links, "emails": emails}

# Fetch YouTube video details
def yt_title(link):
    video_id = extract_video_id(link)
    if not video_id:
        return {"error": "Invalid YouTube URL"}

    api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(api_url)
        data = response.json()
        if "items" in data and data["items"]:
            video_info = data["items"][0]["snippet"]
            description = clean_description(video_info["description"])
            social_info = extract_social_links(description)

            return {
                "title": video_info["title"],
                "description": description,
                "social_media": social_info["social_links"],
                "emails": social_info["emails"]
            }
        return {"error": "Video not found"}
    except Exception as e:
        return {"error": str(e)}

# Download YouTube audio as MP3

def sanitize_filename(filename):
    """Removes special characters and keeps only alphanumeric and spaces."""
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')

"""
def download_audio(video_url, video_title):
    if not video_title:
        return None  # Ensure we have a valid title

    # Extract first two words from the title
    title_words = video_title.split()[:2]  # Get first two words
    clean_title = sanitize_filename("_".join(title_words))  # Clean the filename
    output_filename = f"{clean_title}"
    if not output_filename.endswith(".mp3"):
        output_filename+= ".mp3"

    # Define full path in media folder
    media_folder = settings.MEDIA_ROOT
    if not os.path.exists(media_folder):
        os.makedirs(media_folder)  # Create media folder if it doesn't exist

    output_file = os.path.join(media_folder, output_filename)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': output_file
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return f"{settings.MEDIA_URL}{output_filename}"  # Return relative media URL
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None
"""


def download_audio(video_url, video_title):
    if not video_title:
        return None  

    title_words = video_title.split()[:2]  
    clean_title = sanitize_filename("_".join(title_words))  
    output_filename = f"{clean_title}.mp3"

    media_folder = settings.MEDIA_ROOT
    if not os.path.exists(media_folder):
        os.makedirs(media_folder)  

    output_file = os.path.join(media_folder, output_filename)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [
            {
            'key': 'FFmpegExtractAudio', 
            'preferredcodec': 'mp3', 
            'preferredquality': '192'
            }
            ],
        'outtmpl': output_file,
        'keepvideo': True  # Prevents deletion of the original file
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Wait for the file to be fully released
        time.sleep(2)  

        return f"{settings.MEDIA_URL}{output_filename}"  
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

# FUNCTION TO GET TRANSCRIPT
def get_transcript(audio_file):
   # audio_file = download_audio(link, video_title["title"])
    aai.settings.api_key = "dd37f42650004083b3f2865ef23b30ad"
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    return transcript.text

"""
def generate_blog_from_transcription(transcript):
    HUGGINGFACE_TOKEN = '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'
    API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}  # Replace with your token

    data = {"inputs": f"Summarize this transcript into a blog post: {transcript}"}
    response = requests.post(API_URL, headers=headers, json=data)
    # Get the JSON response from Hugging Face API
    response_data = response.json()

    # Print the response to debug and check its structure
    print(response_data)  # This will help you inspect the structure of the response
    """



def generate_blog_from_transcription(transcript):
        
    # Replace with your API token
    HUGGINGFACE_TOKEN = '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'
    API_URL = "https://api-inference.huggingface.co/models/google/gemma-2-2b-it"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}
    
    
    """
    f"As a professional transcriber, your task is to accurately rewrite {transcript}, ensuring all speech is accurately captured and formatted correctly. Additionally, you will need to ensure that the transcripts are polished and professional in tone, grammar, and structure. Rewrite any unclear or incoherent sections to improve readability and coherence. Double-check the transcripts for accuracy and make any necessary corrections before finalizing them. Your goal is to deliver transcripts that are clear, error-free, and professionally formatted to meet the client's expectations."
    """
    
    prompt = f"Act as a professional blog writer. Take the provided {transcript} and transform it into a well-detailed and engaging blog article. The article should not sound like a transcribed text from YouTube, but rather a polished and captivating piece of content. Focus on structuring the information in a coherent and engaging manner, highlighting key points and adding your own unique insights. Make sure to incorporate storytelling elements, use a variety of engaging language, and keep the reader interested from start to finish. The end result should be a high-quality blog post that educates, entertains, and resonates with the target audience."
    
    
    payload = {"inputs": prompt}
    response = requests.post(API_URL, headers=headers, json=payload)
    
        
    # Check for errors
    # Handle response errors
    # Handle response errors
    if response.status_code != 200:
        return f"Error: {response.status_code}, {response.json()}"

    response_data = response.json()

    # Check if response is a list and extract content
    if isinstance(response_data, list) and len(response_data) > 0:
        return response_data[0].get("generated_text", "No content generated")

    return "Unexpected response format"

    """
    API_KEY = "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"
    client = OpenAI(api_key=API_KEY)
    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:"
    completion = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)
    print(completion.choices[0].message.content)
    """
    
    """
    HUGGINGFACE_TOKEN = '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'  # Your Hugging Face token
    API_URL = "https://api-inference.huggingface.co/models/google/gemma-2-2b-it"  # Model URL
    headers = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}  # Authorization header

    # Refined input data for better results
    refined_prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:"

  

    # Prepare the input data with the refined prompt
    data = {"inputs": refined_prompt}

    # Make the API call to generate the blog post
    response = requests.post(API_URL, headers=headers, json=data)

    # Get the JSON response from Hugging Face API
    response_data = response.json()

    # Extract the generated text from the response
    generated_text = response_data[0].get("generated_text", "No generated text found")

    return generated_text  # Return the generated blog post
"""

# function to login

def user_login(request):
    if request.method == 'POST':
        username = request.POST['Username']
        pwd = request.POST['Password']
        
        user = authenticate(request, username=username, password=pwd)
        
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = 'Invalid username or password'
            return render(request, 'login.html', {'error_message': error_message})
    return render(request, 'login.html')


# function to signup
def user_signup(request):
    if request.method == 'POST':
        username = request.POST['Username']
        email = request.POST['email']
        pwd = request.POST['Password']
        rpwd = request.POST['repeatPassword']
        
        if pwd == rpwd:
            try:
                user = User.objects.create_user(username, email, pwd)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message': error_message})
    return render(request, 'signup.html')
def user_logout(request):
    logout(request)
    return redirect('/')

"""
def download_audio(video_url, output_path=settings.MEDIA_ROOT):
    video_id = extract_video_id(video_url)
    if not video_id:
        return None  # Invalid YouTube link

    # Define the output file name
    output_file = os.path.join(output_path, f"{video_id}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': output_file
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return output_file  # Return the audio file path
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None  # Return None on failure

"""

"""
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data.get('link')  # Use .get() to avoid KeyError
            
            if not yt_link:
                return JsonResponse({'error': 'Missing YouTube link'}, status=400)

            # Get YouTube title
            title_info = yt_title(yt_link)
            if "error" in title_info:
                return JsonResponse({'error': title_info["error"]}, status=400)

            print(title_info)  # Debugging output
            
            # Future functionality: fetch transcript, generate blog, save to DB
            
            # Return the blog as response
            return JsonResponse({'title_info': title_info, 'message': 'Blog generation in progress'})
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Function to extract video ID from YouTube link
def extract_video_id(link):
    pattern = (
        r"(?:https?:\/\/)?(?:www\.)?"
        r"(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)"
        r"([a-zA-Z0-9_-]{11})"
    )
    match = re.search(pattern, link)
    return match.group(1) if match else None

# Clean special characters in description
def clean_description(description):
    return html.unescape(description) if description else "No description available"

# Extract social media links & emails
def extract_social_links(description):
    social_patterns = {
        "Instagram": r"(https?://(www\.)?instagram\.com/[^\s]+)",
        "Twitter": r"(https?://(www\.)?twitter\.com/[^\s]+)",
        "Facebook": r"(https?://(www\.)?facebook\.com/[^\s]+)",
        "TikTok": r"(https?://(www\.)?tiktok\.com/[^\s]+)"
    }
    social_links = {platform: re.findall(pattern, description)[0][0] for platform, pattern in social_patterns.items() if re.findall(pattern, description)}
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", description)
    return {"social_links": social_links, "emails": emails}

# Fetch YouTube video details
def yt_title(link):
    video_id = extract_video_id(link)
    if not video_id:
        return {"error": "Invalid YouTube URL"}

    api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(api_url)
        data = response.json()
        if "items" in data and data["items"]:
            video_info = data["items"][0]["snippet"]
            description = clean_description(video_info["description"])
            social_info = extract_social_links(description)

            return {
                "title": video_info["title"],
                "description": description,
                "social_media": social_info["social_links"],
                "emails": social_info["emails"]
            }
        return {"error": "Video not found"}
    except Exception as e:
        return {"error": str(e)}

"""

### NEW VERSION


"""
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
            #return JsonResponse({'content': yt_link})
        except(KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        # get yt title
        title = yt_title(yt_link)
        print(title)
        
        # get transcript
        
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': 'Failed to get transcript'}, status=500)
    
        
        
        # use openai to generate blog
        
        # save blog to DB
        
        # return blog as response
        
        
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)



# Function to extract video ID from any YouTube link
def extract_video_id(link):
    pattern = (
        r"(?:https?:\/\/)?(?:www\.)?"
        r"(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)"
        r"([a-zA-Z0-9_-]{11})"
    )
    match = re.search(pattern, link)
    return match.group(1) if match else None

# Clean special characters in description
def clean_description(description):
    return html.unescape(description) if description else "No description available"

# Extract social media links & emails
def extract_social_links(description):
    social_patterns = {
        "Instagram": r"(https?://(www\.)?instagram\.com/[^\s]+)",
        "Twitter": r"(https?://(www\.)?twitter\.com/[^\s]+)",
        "Facebook": r"(https?://(www\.)?facebook\.com/[^\s]+)",
        "TikTok": r"(https?://(www\.)?tiktok\.com/[^\s]+)"
    }
    social_links = {platform: re.findall(pattern, description)[0][0] for platform, pattern in social_patterns.items() if re.findall(pattern, description)}
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", description)
    return {"social_links": social_links, "emails": emails}

# Fetch YouTube video details
def yt_title(link):
    video_id = extract_video_id(link)
    if not video_id:
        return {"error": "Invalid YouTube URL"}

    api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(api_url)
        data = response.json()
        if "items" in data and data["items"]:
            video_info = data["items"][0]["snippet"]
            description = clean_description(video_info["description"])
            social_info = extract_social_links(description)

            return {
                "title": video_info["title"],
                "description": description,
                "social_media": social_info["social_links"],
                "emails": social_info["emails"]
            }
        return {"error": "Video not found"}
    except Exception as e:
        return {"error": str(e)}
    

"""
"""
# PREVIOUS SESSION

def yt_title(link):
    try:
        yt = YouTube(link)
        title = yt.title
        return title
    except HTTPError as e:
        print(f"Error fetching title: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "dd37f42650004083b3f2865ef23b30ad"
    
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    
    return transcript.text
"""
