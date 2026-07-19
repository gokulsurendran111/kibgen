import os
import requests
from  dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from libgen_api_enhanced import LibgenSearch
from libgen_api_enhanced.book import Book as NativeBook
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()
load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---

class BookModel(BaseModel):
    id: str
    title: str
    author: str
    publisher: str
    year: str
    language: str
    pages: str
    size: str
    extension: str
    cover_url: str
    mirror_url: str  # 🟢 PASSES THE SCRAPER mirror PAGE URL
    md5: str         # 🟢 PASSES THE SCRAPER md5 HASH KEY

class SendRequest(BaseModel):
    id: str          # 🟢 REQUIRED FOR BOOK INITIALIZATION
    mirrorUrl: str   # 🟢 REQUIRED FOR SEARCH ENGINE ENVIRONMENT
    md5: str         # 🟢 REQUIRED FOR SEARCH ENGINE ENVIRONMENT
    title: str
    convert: bool

# --- SEARCH CATALOG (OPTIMIZED AND CORRECTED) ---

def search_catalog(query: str, search_type: str) -> List[BookModel]:
    print(f"Executing search... Query: '{query}', Type: '{search_type}'")
    
    results = []
    s = LibgenSearch()
    search_results = s.search_default(query)  # returns a list of Book objects
    print(f"Found {len(search_results)} results for query '{query}'.")

    # Sort by year descending
    sorted_results = sorted(search_results, key=lambda x: getattr(x, 'year', '0'), reverse=True)
    print()    
    for book in sorted_results:
        try:
            first_mirror = ""
            if hasattr(book, 'mirrors') and book.mirrors:
                first_mirror = str(book.mirrors[0]) if book.mirrors[0] else ""
            
            # 2. Safe extraction of the MD5 hash
            md5_hash = str(book.md5) if hasattr(book, 'md5') and book.md5 else ""

            # 3. Build the model with strict fallbacks to empty strings or defaults
            book_model = BookModel(
                id=str(book.id) if book.id else "",
                title=str(book.title) if book.title else "Unknown Title",
                author=str(book.author) if book.author else "Unknown Author",
                publisher=str(book.publisher) if book.publisher else "N/A",
                year=str(book.year) if book.year else "N/A",
                language=str(book.language) if book.language else "N/A",
                pages=str(book.pages) if book.pages else "N/A",
                size=str(book.size) if book.size else "N/A",
                extension=str(book.extension) if book.extension else "N/A",
                cover_url=str(book.cover_url) if book.cover_url else "",
                mirror_url=first_mirror,          
                md5=md5_hash 
            )
            results.append(book_model)
        except Exception as e:
        # Log the single failed book item and skip it, keeping the endpoint alive!
            print(f"Skipping a corrupted entry (ID: {getattr(book, 'id', 'Unknown')}): {e}")
            continue
        results.append(book_model)
    
    return results

# --- API ROUTES ---

@app.get("/api/proxy-cover")
def proxy_cover(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="Missing targeted cover URL string.")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://libgen.li/"
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Cover host rejected request.")
        return Response(content=response.content, media_type=response.headers.get("Content-Type", "image/jpeg"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search", response_model=List[BookModel])
def search_books(q: str, type: Optional[str] = "title"):
    if not q:
        raise HTTPException(status_code=400, detail="Missing search query string.")
    try:
        return search_catalog(q, type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failure: {str(e)}")

@app.post("/api/send")
def send_to_kindle(payload: SendRequest):
    sender_email = os.getenv("SENDER_EMAIL")
    kindle_email = os.getenv("KINDLE_EMAIL")
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")

    if not all([sender_email, kindle_email, mailgun_api_key, mailgun_domain]):
        raise HTTPException(status_code=500, detail="Server environment secrets are missing.")

    try:
        # 🟢 IMPORT THE NATIVE CLASS AT RUNTIME
        # from libgen_api_enhanced.libgen_search import Book as NativeBook
        
        # 🟢 INITIALIZE NATIVE BOOK USING EVERY PARAMETER REQUIRED BY THE CONSTRUCTOR
        # We fill missing metadata fields with empty strings or lists since resolve_direct_download_link only needs id, title, extension, mirrors, and md5.
        temp_book = NativeBook(
            id=payload.id,
            title=payload.title,
            author="",
            publisher="",
            year="",
            language="",
            pages="",
            size="",
            extension="",  # Will be extracted from the filename downstream or sent generic
            md5=payload.md5,
            mirrors=[payload.mirrorUrl],  # Populates self.mirrors[0] perfectly!
            cover_url="",
            date_added="",
            date_last_modified=""
        )
        
        # Trigger the built-in library scraping resolver method directly
        print("Executing library deep resolution algorithm...")
        temp_book.resolve_direct_download_link()
        resolved_url = temp_book.resolved_download_link
        
        if not resolved_url:
            raise HTTPException(status_code=500, detail="Library failed to extract direct file download address link.")
            
        print(f"Link resolved successfully: {resolved_url}")

        # STEP 2: Download the book file into a memory stream
        file_res = requests.get(resolved_url, timeout=90)
        if file_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not read file data from target domain link.")
            
        file_bytes = file_res.content
        print(f"Downloaded {len(file_bytes)} bytes from the resolved link.")
        
        # Clean file naming extensions dynamically
        ext = payload.mirrorUrl.split('.')[-1][:4]
        if '?' in ext:
            ext = ext.split('?')[0]
        
        safe_filename = f"{payload.title.lower().replace(' ', '_')}.{ext}"
        if not safe_filename.endswith(('.epub', '.mobi', '.pdf', '.txt')):
            safe_filename = f"{payload.title.lower().replace(' ', '_')}.epub"

        # STEP 3: Build the Mailgun email payload
        email_url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"
        subject_header = "Convert" if payload.convert else "Deliver Document"
        
        email_payload = {
            "from": f"Kibgen <{sender_email}>", 
            "to": kindle_email,
            "subject": subject_header,
            "text": f"Automated book delivery: {payload.title}"
        }
        
        files = [("attachment", (safe_filename, file_bytes, "application/octet-stream"))]
        
        print(f"Forwarding payload to Mailgun...")
        response = requests.post(email_url, auth=("api", mailgun_api_key), data=email_payload, files=files, timeout=60)
        
        if response.status_code != 200:
            return {"success": False, "error": f"Mailgun relay rejected: {response.text}"}
            
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Library processing or transmission failed: {str(e)}")