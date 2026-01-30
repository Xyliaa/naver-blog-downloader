import pathlib
import re
from urllib.parse import unquote, urlparse

import requests_html


def parse_blog_url(url):
    """
    Parse different Naver blog/post URL formats and return (blog_id, log_no).

    Supported formats:
    - https://blog.naver.com/{blogId}/{logNo}
    - https://blog.naver.com/PostView.naver?blogId={blogId}&logNo={logNo}
    - https://post.naver.com/viewer/postView.nhn?volumeNo={volumeNo}&memberNo={memberNo}
    """
    parsed = urlparse(url)

    # New format: blog.naver.com/{blogId}/{logNo}
    if parsed.netloc == 'blog.naver.com' and parsed.path.count('/') >= 2:
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[1].isdigit():
            return ('blog', path_parts[0], path_parts[1])

    # Format: blog.naver.com/PostView.naver?blogId=...&logNo=...
    if 'blogId=' in parsed.query and 'logNo=' in parsed.query:
        blog_id = parsed.query.split('blogId=')[1].split('&')[0]
        log_no = parsed.query.split('logNo=')[1].split('&')[0]
        return ('blog', blog_id, log_no)

    # Old format: post.naver.com/viewer/postView.nhn?volumeNo=...
    if 'volumeNo=' in parsed.query:
        volume_no = parsed.query.split('volumeNo=')[1].split('&')[0]
        return ('post', None, volume_no)

    return (None, None, None)


def convert_to_full_size_url(thumbnail_url):
    """
    Convert thumbnail URL to full-size image URL.

    Thumbnail: https://postfiles.pstatic.net/...?type=w466
    Full size: https://blogfiles.naver.net/... (no query params)
    """
    # Remove query parameters (like ?type=w466)
    base_url = thumbnail_url.split('?')[0]

    # Convert postfiles.pstatic.net to blogfiles.naver.net
    if 'postfiles.pstatic.net' in base_url:
        base_url = base_url.replace('postfiles.pstatic.net', 'blogfiles.naver.net')

    return base_url


def queue_downloads(url):
    session = requests_html.HTMLSession()

    url_type, blog_id, post_id = parse_blog_url(url)

    if url_type == 'blog':
        # For blog.naver.com, we need to access the iframe content directly
        iframe_url = f'https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_id}'
        print(f'Blog detected: {blog_id}/{post_id}')
        print(f'Fetching iframe content: {iframe_url}')
        r = session.get(iframe_url)
        # Try without JS rendering first - Naver blog images are often in static HTML
        title = post_id
    elif url_type == 'post':
        print('Legacy post.naver.com format detected')
        print('Getting the page')
        r = session.get(url)
        print('Rendering javascript content')
        r.html.render()
        title = post_id
    else:
        print('Getting the page (unknown format, trying direct access)')
        r = session.get(url)
        print('Rendering javascript content')
        r.html.render()
        title = 'downloaded_images'

    desired_path = pathlib.Path.cwd().joinpath(title)

    # Try new SmartEditor format first (se-image-resource)
    smart_editor_images = r.html.find('.se-image-resource')
    print(f'{len(smart_editor_images)} entries with ".se-image-resource" pattern (SmartEditor)')

    # Legacy patterns
    first_try = r.html.find('.img_attachedfile.thumb')
    print(f'{len(first_try)} entries with ".img_attachedfile.thumb" pattern')
    second_try = r.html.find('.se_mediaImage.__se_img_el')
    print(f'{len(second_try)} entries with ".se_mediaImage.__se_img_el" pattern')

    if len(smart_editor_images) != 0:
        desired_path.mkdir(parents=False, exist_ok=True)
        for idx, img in enumerate(smart_editor_images, 1):
            # Get the data-src attribute (full resolution) or src
            picture_url = img.attrs.get('data-lazy-src') or img.attrs.get('data-src') or img.attrs.get('src', '')
            if not picture_url:
                continue

            # Convert to full-size URL
            picture_url = convert_to_full_size_url(picture_url)

            # Extract filename from URL
            picture_name = unquote(urlparse(picture_url).path.split('/')[-1])
            if not picture_name or picture_name == '/':
                picture_name = f'image_{idx}.jpg'

            # Remove special characters not allowed in filenames
            picture_path = desired_path.joinpath(re.sub('[<>:\"/|?*]', ' ', picture_name).strip())
            save_picture(session, picture_url, picture_path)
    elif len(first_try) != 0:
        desired_path.mkdir(parents=False, exist_ok=True)
        for i in first_try:
            picture_url = i.attrs['src'].split('?')[0]
            picture_path = desired_path.joinpath(i.attrs['alt'])
            save_picture(session, picture_url, picture_path)
    elif len(second_try) != 0:
        desired_path.mkdir(parents=False, exist_ok=True)
        for j in second_try:
            picture_url = j.attrs['src'].split('?')[0]
            picture_name = unquote(urlparse(picture_url).path.split('/')[-1])
            # remove all special characters not allowed in filenames in windows and mostly in unix
            picture_path = desired_path.joinpath(re.sub('[<>:\"/|?*]', ' ', picture_name).strip())
            save_picture(session, picture_url, picture_path)
    else:
        print('Nothing has been downloaded, current page type is not supported')


def save_picture(session, picture_url, picture_path: pathlib.Path):
    r = session.get(picture_url)
    if not picture_path.is_file():  # don't overwrite files
        if r.status_code == 200:
            picture_path.write_bytes(r.content)
            print(f'Downloaded {picture_url}')
        else:
            print(f'Error {r.status_code} while getting request for {picture_url}')


if __name__ == "__main__":
    try:
        urlinput = input('Enter post URL: ')
        queue_downloads(urlinput)
    except Exception as e:
        print(f'\nError: {e}')
        import traceback
        traceback.print_exc()
    finally:
        input('\nPress Enter to exit...')
