# Image Downloader

Python3 script to download full-resolution pictures from multiple sites.

### Supported Sites

| Site | URL Format |
|------|------------|
| Naver Blog | `https://blog.naver.com/{blogId}/{logNo}` |
| Naver Blog | `https://blog.naver.com/PostView.naver?blogId=XXX&logNo=XXX` |
| Naver Post | `https://post.naver.com/viewer/postView.nhn?volumeNo=XXX` (legacy) |
| SBS K-Pop | `https://sbskpop.kr/{artist}` |
| SBS Program | `https://programs.sbs.co.kr/.../visualboard/...?board_no=XXX` |
| Weverse | `https://weverse.io/{artist}/media/{post_id}` |
| Berriz | `https://berriz.in/{lang}/{artist}/media/content/{post_id}` |

### Requirements

- Python 3.7+
- requests
- beautifulsoup4
- selenium (optional, for JS-rendered pages)
- webdriver-manager (optional, for auto Chrome driver)

### Installation

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
```

### How to use

1. Run the script:
   ```bash
   python image_downloader.py
   ```

2. Paste the URL when prompted:
   ```
   Enter URL: https://blog.naver.com/jypentertainment/224072207277
   ```

3. Images will be downloaded to a folder named after the post ID in the current directory.

### Features

- Downloads full-resolution images (converts thumbnails to full size)
- Supports multiple sites with automatic detection
- Preserves original filenames
- Skips already downloaded files
- JavaScript rendering support for dynamic pages (Weverse, Berriz, SBS Program)
