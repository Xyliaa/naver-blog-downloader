# naver-post-downloader

Python3 script to download full-resolution pictures from Naver Blog and Naver Post.

### Supported URL Formats

- `https://blog.naver.com/{blogId}/{logNo}` (new format)
- `https://blog.naver.com/PostView.naver?blogId=XXX&logNo=XXX`
- `https://post.naver.com/viewer/postView.nhn?volumeNo=XXX` (legacy)

### Requirements

- Python 3.7+
- requests-html
- lxml_html_clean

### Installation

```bash
pip install requests-html lxml_html_clean
```

### How to use

1. Run the script:
   ```bash
   python naver_post_downloader.py
   ```

2. Paste the URL when prompted:
   ```
   Enter post URL: https://blog.naver.com/jypentertainment/224072207277
   ```

3. Images will be downloaded to a folder named after the post ID in the current directory.

### Features

- Downloads full-resolution images (converts thumbnails to full size)
- Supports Naver SmartEditor format
- Preserves original filenames
- Skips already downloaded files
