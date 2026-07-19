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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

# --- Pydantic Schema for incoming requests ---
class SendRequest(BaseModel):
    id: str
    mirrorUrl: str
    md5: str
    title: str
    convert: bool

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
    s.mirrors = ["https://libgen.rs", "https://libgen.is", "https://libgen.li"]
    if search_type == "author":
        raw_results = s.search_author(query)
    elif search_type == "title":
        raw_results = s.search_title(query)
    else:
        raw_results = s.search_default(query)

    print(f"Found {len(raw_results)} results for query '{query}'.")

    # Sort by year descending
    sorted_results = sorted(raw_results, key=lambda x: getattr(x, 'year', '0'), reverse=True)
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
    # 🟢 STEP 1: LOAD GMAIL SMTP VARIABLES FROM ENVIRONMENT MEMORY
    gmail_user = os.getenv("GMAIL_USER")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
    kindle_email = os.getenv("KINDLE_EMAIL")

    if not all([gmail_user, gmail_app_password, kindle_email]):
        raise HTTPException(
            status_code=500, 
            detail="Server environment Gmail configurations are missing."
        )

    try:
        # 🟢 STEP 2: RUNTIME IMPORT & INITIALIZE NATIVE CLASS PROPERLY 
        # Import directly inside the route block from the verified library submodule
        
        print(f"Rebuilding target native book class for ID: {payload.id}")
        temp_book = NativeBook(
            id=payload.id,
            title=payload.title,
            author="",
            publisher="",
            year="",
            language="",
            pages="",
            size="",
            extension="",  
            md5=payload.md5,
            mirrors=[payload.mirrorUrl],  # Securely maps to self.mirrors[0]
            cover_url="",
            date_added="",
            date_last_modified=""
        )
        
        print("Executing library deep resolution algorithm...")
        temp_book.resolve_direct_download_link()
        resolved_url = temp_book.resolved_download_link
        
        if not resolved_url:
            raise HTTPException(
                status_code=500, 
                detail="Library failed to extract direct file download address link."
            )
            
        print(f"Link resolved successfully: {resolved_url}")

        # 🟢 STEP 3: STREAM STREAMING PAYLOAD WITH PROGRESS PERCENTAGE
        print(f"Opening content stream from target link...")
        file_res = requests.get(resolved_url, stream=True, timeout=90)
        
        if file_res.status_code != 200:
            raise HTTPException(
                status_code=400, 
                detail="Could not read file data from target domain link."
            )
            
        total_size = file_res.headers.get('content-length')
        total_bytes = int(total_size) if total_size else None
        
        file_bytes = bytearray()
        downloaded_bytes = 0
        chunk_size = 1024 * 100  # Read data updates in crisp 100 KB chunks

        for chunk in file_res.iter_content(chunk_size=chunk_size):
            if chunk:
                file_bytes.extend(chunk)
                downloaded_bytes += len(chunk)
                if total_bytes:
                    percent = (downloaded_bytes / total_bytes) * 100
                    print(f"\r⏳ Downloading: {percent:.1f}% ({downloaded_bytes / (1024*1024):.2f} MB)", end="", flush=True)
                else:
                    print(f"\r⏳ Streaming downloaded chunks: {downloaded_bytes / (1024*1024):.2f} MB", end="", flush=True)
        print("\n✅ Download finished completely! Data cached in memory buffer.")

        # 🟢 STEP 4: DYNAMIC FILENAME SANITIZATION & MATCHING
        ext = payload.mirrorUrl.split('.')[-1][:4]
        if '?' in ext:
            ext = ext.split('?')[0]
        
        raw_filename = f"{payload.title.lower().replace(' ', '_')}.{ext}"
        if not raw_filename.endswith(('.epub', '.mobi', '.pdf', '.txt')):
            raw_filename = f"{payload.title.lower().replace(' ', '_')}.epub"
            
        # Strip out any non-ascii formatting bytes to prevent email generation failures
        clean_filename = raw_filename.encode('ascii', 'ignore').decode('ascii')

        # 🟢 STEP 5: BULLETPROOF MIME GENERATION PIPELINE
        print("Constructing native SMTP multi-part email payload...")
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = kindle_email
        msg['Subject'] = "Convert" if payload.convert else "Deliver Document"
        
        msg.attach(MIMEText("Automated book delivery via Kibge app.", 'plain'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(bytes(file_bytes)) # Force cast back to standard un-mutable bytes
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment', filename=clean_filename)
        msg.attach(part)

        # 🟢 STEP 6: TLS HANDSHAKE & TRANSMISSION VIA GMAIL SMTP
        print("Opening secure TLS handshake tunnel connection with smtp.gmail.com...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        server.login(gmail_user, gmail_app_password)
        
        print("Transmitting email package array onto Google mail servers...")
        server.sendmail(gmail_user, kindle_email, msg.as_string())
        server.quit()
        
        print("✅ Delivery transaction complete!")
        return {"success": True}
        
    except Exception as e:
        # Catch any sub-system exceptions and safely bubble up 500 logs to the terminal
        print(f"❌ Route processing critical crash trace: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Library processing or SMTP transmission failed: {str(e)}"
        )