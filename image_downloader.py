import pathlib
import re
import time
from urllib.parse import unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

# Try to import Selenium for JS-rendered pages
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def parse_url(url):
    """
    Parse different URL formats and return (site_type, identifier).

    Supported sites:
    - blog.naver.com/{blogId}/{logNo}
    - blog.naver.com/PostView.naver?blogId=...&logNo=...
    - post.naver.com/viewer/postView.nhn?volumeNo=...
    - sbskpop.kr/{artist}
    - programs.sbs.co.kr/...?board_no=...
    - weverse.io/{artist}/media/{post_id}
    - berriz.in/{lang}/{artist}/media/content/{post_id}
    """
    parsed = urlparse(url)

    # Naver blog: blog.naver.com/{blogId}/{logNo}
    if parsed.netloc == 'blog.naver.com':
        # New format: blog.naver.com/{blogId}/{logNo}
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[1].isdigit():
            return ('naver_blog', path_parts[0], path_parts[1])

        # Format: blog.naver.com/PostView.naver?blogId=...&logNo=...
        if 'blogId=' in parsed.query and 'logNo=' in parsed.query:
            blog_id = parsed.query.split('blogId=')[1].split('&')[0]
            log_no = parsed.query.split('logNo=')[1].split('&')[0]
            return ('naver_blog', blog_id, log_no)

    # Naver post (legacy): post.naver.com/viewer/postView.nhn?volumeNo=...
    if 'post.naver.com' in parsed.netloc and 'volumeNo=' in parsed.query:
        volume_no = parsed.query.split('volumeNo=')[1].split('&')[0]
        return ('naver_post', None, volume_no)

    # sbskpop.kr/{artist}
    if 'sbskpop.kr' in parsed.netloc:
        path_parts = parsed.path.strip('/').split('/')
        if path_parts and path_parts[0]:
            return ('sbskpop', path_parts[0], None)
        return ('sbskpop', 'unknown', None)

    # programs.sbs.co.kr or m.programs.sbs.co.kr
    if 'programs.sbs.co.kr' in parsed.netloc:
        query = parse_qs(parsed.query)
        board_no = query.get('board_no', ['unknown'])[0]
        return ('sbs_program', board_no, None)

    # weverse.io/{artist}/media/{post_id}
    if 'weverse.io' in parsed.netloc:
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[1] == 'media':
            artist = path_parts[0]
            post_id = path_parts[2]
            return ('weverse', artist, post_id)
        elif len(path_parts) >= 1:
            return ('weverse', path_parts[0], None)
        return ('weverse', 'unknown', None)

    # berriz.in/{lang}/{artist}/media/content/{post_id}
    if 'berriz.in' in parsed.netloc:
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 5 and path_parts[2] == 'media':
            artist = path_parts[1]
            post_id = path_parts[4]
            return ('berriz', artist, post_id)
        elif len(path_parts) >= 2:
            return ('berriz', path_parts[1], None)
        return ('berriz', 'unknown', None)

    return (None, None, None)


def get_selenium_driver():
    """Create a headless Chrome driver."""
    if not SELENIUM_AVAILABLE:
        return None

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"Could not create Chrome driver: {e}")
        return None


def fetch_page(url, needs_js=False, scroll=False):
    """Fetch page content, optionally with JavaScript rendering."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    if needs_js and SELENIUM_AVAILABLE:
        print("Using Selenium for JavaScript rendering...")
        driver = get_selenium_driver()
        if driver:
            try:
                driver.get(url)
                time.sleep(5)

                if scroll:
                    for _ in range(3):
                        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                        time.sleep(1)
                    driver.execute_script('window.scrollTo(0, 0);')
                    time.sleep(1)

                html = driver.page_source
                driver.quit()
                return BeautifulSoup(html, 'html.parser')
            except Exception as e:
                print(f"Selenium error: {e}")
                driver.quit()

    response = requests.get(url, headers=headers)
    return BeautifulSoup(response.text, 'html.parser')


def convert_naver_to_full_size(thumbnail_url):
    """Convert Naver thumbnail URL to full-size image URL."""
    base_url = thumbnail_url.split('?')[0]
    if 'postfiles.pstatic.net' in base_url:
        base_url = base_url.replace('postfiles.pstatic.net', 'blogfiles.naver.net')
    return base_url


def extract_naver_images(soup, blog_id, post_id):
    """Extract images from Naver blog posts."""
    image_urls = []

    # SmartEditor format (se-image-resource)
    smart_editor_images = soup.find_all(class_='se-image-resource')
    print(f'Found {len(smart_editor_images)} SmartEditor images')

    if smart_editor_images:
        for img in smart_editor_images:
            picture_url = img.get('data-lazy-src') or img.get('data-src') or img.get('src', '')
            if picture_url:
                picture_url = convert_naver_to_full_size(picture_url)
                if picture_url not in image_urls:
                    image_urls.append(picture_url)
        return image_urls

    # Legacy format: .img_attachedfile.thumb
    first_try = soup.find_all(class_=['img_attachedfile', 'thumb'])
    print(f'Found {len(first_try)} legacy format images (.img_attachedfile.thumb)')

    if first_try:
        for img in first_try:
            src = img.get('src', '')
            if src:
                picture_url = src.split('?')[0]
                if picture_url not in image_urls:
                    image_urls.append(picture_url)
        return image_urls

    # Legacy format: .se_mediaImage.__se_img_el
    second_try = soup.find_all(class_=['se_mediaImage', '__se_img_el'])
    print(f'Found {len(second_try)} legacy format images (.se_mediaImage)')

    if second_try:
        for img in second_try:
            src = img.get('src', '')
            if src:
                picture_url = src.split('?')[0]
                if picture_url not in image_urls:
                    image_urls.append(picture_url)

    return image_urls


def extract_sbskpop_images(soup, base_url):
    """Extract high-resolution images from sbskpop.kr pages."""
    html_text = str(soup)
    best_urls = {}

    for match in re.finditer(r'https://cdn\.myportfolio\.com/[a-f0-9-]+/([a-f0-9-]+)(_[^.]+)?(\.(jpg|png))\?h=[a-f0-9]+', html_text):
        url = match.group(0)
        img_id = match.group(1)
        suffix = match.group(2) or ''

        # Skip cropped thumbnails
        if '_carw_' in suffix or '_rwc_' in suffix:
            continue

        # Calculate priority (higher = better)
        if not suffix:
            priority = 10000
        elif suffix.startswith('_rw_'):
            width_match = re.search(r'_rw_(\d+)', suffix)
            priority = int(width_match.group(1)) if width_match else 500
        else:
            priority = 50

        if img_id not in best_urls or priority > best_urls[img_id][0]:
            best_urls[img_id] = (priority, url)

    full_res_count = sum(1 for p, _ in best_urls.values() if p >= 10000)
    resized_count = len(best_urls) - full_res_count
    print(f"Found {full_res_count} full-resolution + {resized_count} resized = {len(best_urls)} total images")

    return [url for _, url in best_urls.values()]


def extract_sbs_program_images(soup, base_url):
    """Extract images from SBS program visualboard pages."""
    image_urls = []
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    html_text = str(soup)

    # SBS content images: {24-hex-chars}-p.jpg
    for match in re.finditer(r'(https?://[^\s"\'<>]+/([a-f0-9]{24})-p\.(jpg|png))', html_text, re.IGNORECASE):
        url = match.group(1)
        if url not in image_urls:
            image_urls.append(url)

    for img in soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        if not src or src.startswith('data:'):
            continue

        filename = src.split('/')[-1].split('?')[0]
        if re.match(r'^[a-f0-9]{24}-p\.(jpg|png)$', filename, re.IGNORECASE):
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = base_domain + src
            if src not in image_urls:
                image_urls.append(src)

    print(f"Found {len(image_urls)} content images (hex-p pattern)")
    return image_urls


def extract_berriz_images(soup, base_url):
    """Extract images from Berriz media pages."""
    image_urls = []
    seen_ids = set()

    content_containers = soup.find_all(class_=re.compile(r'xl:w-\[880px\]'))

    for container in content_containers:
        for img in container.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if not src or 'statics.berriz.in/cdn/partner' not in src:
                continue

            id_match = re.search(r'/(\d+)\.(jpg|jpeg|png|webp)$', src, re.IGNORECASE)
            if id_match:
                img_id = id_match.group(1)
                if img_id in seen_ids:
                    continue
                seen_ids.add(img_id)

            if src not in image_urls:
                image_urls.append(src)

    # Fallback
    if not image_urls:
        html_text = str(soup)
        pattern = r'https://statics\.berriz\.in/cdn/partner/image/[^\s"<>]+\.(jpg|jpeg|png|webp)'
        for match in re.finditer(pattern, html_text, re.IGNORECASE):
            url = match.group(0)
            id_match = re.search(r'/(\d+)\.(jpg|jpeg|png|webp)$', url, re.IGNORECASE)
            if id_match:
                img_id = id_match.group(1)
                if img_id in seen_ids:
                    continue
                seen_ids.add(img_id)
            if url not in image_urls:
                image_urls.append(url)

    print(f"Found {len(image_urls)} Berriz images")
    return image_urls


def extract_weverse_images(soup, base_url):
    """Extract images from Weverse media pages."""
    image_urls = []
    seen_ids = set()

    content_containers = soup.find_all(class_=re.compile(r'media-image-simple-list'))

    for container in content_containers:
        for img in container.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if not src or 'phinf.wevpstatic.net' not in src:
                continue

            full_url = src.split('?')[0]

            filename_match = re.search(r'/([a-f0-9-]+)\.(jpeg|jpg|png|webp)$', full_url, re.IGNORECASE)
            if filename_match:
                img_id = filename_match.group(1)
                if img_id in seen_ids:
                    continue
                seen_ids.add(img_id)

            if full_url not in image_urls:
                image_urls.append(full_url)

    # Fallback
    if not image_urls:
        html_text = str(soup)
        pattern = r'https://phinf\.wevpstatic\.net/[^"\s<>]+\.(?:jpeg|jpg|png|webp)'
        for match in re.finditer(pattern, html_text, re.IGNORECASE):
            url = match.group(0)
            full_url = url.split('?')[0]

            filename_match = re.search(r'/([a-f0-9-]+)\.(jpeg|jpg|png|webp)$', full_url, re.IGNORECASE)
            if filename_match:
                img_id = filename_match.group(1)
                if img_id in seen_ids:
                    continue
                seen_ids.add(img_id)

            if full_url not in image_urls:
                image_urls.append(full_url)

    print(f"Found {len(image_urls)} Weverse images")
    return image_urls


def queue_downloads(url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    site_type, id1, id2 = parse_url(url)

    if site_type == 'naver_blog':
        blog_id, post_id = id1, id2
        print(f'Naver Blog detected: {blog_id}/{post_id}')
        iframe_url = f'https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_id}'
        print(f'Fetching iframe content: {iframe_url}')
        soup = fetch_page(iframe_url, needs_js=False)
        image_urls = extract_naver_images(soup, blog_id, post_id)
        title = post_id

    elif site_type == 'naver_post':
        post_id = id2
        print(f'Naver Post (legacy) detected: {post_id}')
        print(f'Fetching page: {url}')
        soup = fetch_page(url, needs_js=True)
        image_urls = extract_naver_images(soup, None, post_id)
        title = post_id

    elif site_type == 'sbskpop':
        identifier = id1
        print(f'SBS K-Pop Magazine detected: {identifier}')
        print(f'Fetching page: {url}')
        soup = fetch_page(url, needs_js=False)
        image_urls = extract_sbskpop_images(soup, url)
        title = identifier

    elif site_type == 'sbs_program':
        identifier = id1
        if 'm.programs.sbs.co.kr' not in url:
            url = url.replace('programs.sbs.co.kr', 'm.programs.sbs.co.kr')
        print(f'SBS Program detected: board_no={identifier}')
        print(f'Fetching page: {url}')
        soup = fetch_page(url, needs_js=True)
        image_urls = extract_sbs_program_images(soup, url)
        title = identifier

    elif site_type == 'weverse':
        artist, post_id = id1, id2
        identifier = f'{artist}_{post_id}' if post_id else artist
        print(f'Weverse detected: {identifier}')
        print(f'Fetching page: {url}')
        soup = fetch_page(url, needs_js=True, scroll=True)
        image_urls = extract_weverse_images(soup, url)
        title = identifier

    elif site_type == 'berriz':
        artist, post_id = id1, id2
        identifier = f'{artist}_{post_id}' if post_id else artist
        print(f'Berriz detected: {identifier}')
        print(f'Fetching page: {url}')
        soup = fetch_page(url, needs_js=True, scroll=True)
        image_urls = extract_berriz_images(soup, url)
        title = identifier

    else:
        print('Unknown URL format, trying generic extraction')
        soup = fetch_page(url, needs_js=False)
        image_urls = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                image_urls.append(src)
        title = 'downloaded'

    print(f'\nFound {len(image_urls)} images to download')

    if image_urls:
        desired_path = pathlib.Path.cwd().joinpath(title)
        desired_path.mkdir(parents=False, exist_ok=True)

        for idx, picture_url in enumerate(image_urls, 1):
            parsed_url = urlparse(picture_url)
            picture_name = unquote(parsed_url.path.split('/')[-1])

            if not picture_name or picture_name == '/' or '.' not in picture_name:
                picture_name = f'image_{idx}.jpg'

            if '?' in picture_name:
                picture_name = picture_name.split('?')[0]

            picture_name = re.sub(r'[<>:"/\\|?*]', '_', picture_name).strip()
            picture_path = desired_path.joinpath(picture_name)

            save_picture(session, picture_url, picture_path)
    else:
        print('No images found to download')


def save_picture(session, picture_url, picture_path: pathlib.Path):
    try:
        r = session.get(picture_url)
        if not picture_path.is_file():
            if r.status_code == 200:
                picture_path.write_bytes(r.content)
                print(f'Downloaded: {picture_path.name}')
            else:
                print(f'Error {r.status_code}: {picture_url}')
        else:
            print(f'Skipped (exists): {picture_path.name}')
    except Exception as e:
        print(f'Error downloading {picture_url}: {e}')


if __name__ == "__main__":
    print("=" * 50)
    print("Image Downloader")
    print("Supported sites: Naver Blog, sbskpop, SBS Program, Weverse, Berriz")
    print("=" * 50)
    try:
        urlinput = input('\nEnter URL: ')
        queue_downloads(urlinput)
    except Exception as e:
        print(f'\nError: {e}')
        import traceback
        traceback.print_exc()
    finally:
        input('\nPress Enter to exit...')
