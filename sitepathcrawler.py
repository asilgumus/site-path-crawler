#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urldefrag
from collections import deque
from tqdm import tqdm
from colorama import init as colorama_init, Fore, Back, Style
import os, re, sys, time, threading

colorama_init(autoreset=True)

USER_AGENT = "site-path-crawler/1.0"
MAX_PAGES = 500
DELAY_BETWEEN_REQS = 0.25

def styl(msg, fg=Fore.GREEN, bold=False):
    return (Style.BRIGHT if bold else "") + fg + msg + Style.RESET_ALL

def banner(example_domain):
    print(styl("╔══════════════════════════════════════════════════════╗", Fore.GREEN, True))
    print(styl("║", Fore.GREEN, True) + "  " + styl("PATH CRAWLER", Fore.WHITE, True))
    print(styl("║", Fore.GREEN, True) + "  " + styl("Example:", Fore.CYAN) + " " + styl(example_domain, Fore.YELLOW, True))
    print(styl("╚══════════════════════════════════════════════════════╝", Fore.GREEN, True))
    print()

def color_print(msg, level="info", end="\n"):
    if level == "info":
        print(styl("ℹ️ " + msg, Fore.GREEN, True), end=end)
    elif level == "debug":
        print(styl("🔎 " + msg, Fore.GREEN), end=end)
    elif level == "warn":
        print(styl("⚠️ " + msg, Fore.YELLOW), end=end)
    elif level == "error":
        print(styl("❌ " + msg, Fore.RED, True), end=end)
    elif level == "succ":
        print(styl("✅ " + msg, Fore.GREEN, True), end=end)
    else:
        print(msg, end=end)

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        color_print(f"Output directory created: {path}", "succ")
    else:
        color_print(f"Output directory already exists: {path}", "info")

def sanitize_filename(path):
    if not path or path == "/":
        name = "root"
    else:
        name = path.lstrip("/")
        name = name.replace("/", "__")
        name = re.sub(r"[?#].*$", "", name)
        name = re.sub(r"[^\w\.-]", "_", name)
        if not name:
            name = "root"
    return name + ".html"

def normalize_link(base, link):
    if not link:
        return None
    link = link.strip()
    if any(link.lower().startswith(s) for s in ("javascript:", "mailto:", "tel:", "data:")):
        return None
    joined = urljoin(base, link)
    joined, _ = urldefrag(joined)
    return joined

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def fetch_html(url):
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        if r.status_code >= 400:
            return None, r.status_code
        ctype = r.headers.get("Content-Type", "")
        if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
            return None, r.status_code
        return r.text, r.status_code
    except Exception:
        return None, None

def extract_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        norm = normalize_link(base_url, href)
        if norm:
            links.add(norm)
    return links

def spinner(stop_event, status_text):
    chars = "|/-\\"
    i = 0
    while not stop_event.is_set():
        print(styl(f"\r{chars[i%4]} {status_text}", Fore.CYAN), end="")
        i += 1
        time.sleep(0.12)
    print("\r", end="")

def crawl(start_url, output_dir, max_pages=MAX_PAGES, delay=DELAY_BETWEEN_REQS):
    parsed = urlparse(start_url)
    base_netloc = parsed.netloc
    ensure_dir(output_dir)
    visited = set()
    queued = set()
    q = deque()
    q.append(start_url)
    queued.add(start_url)
    saved_count = 0
    pbar = tqdm(total=max_pages, desc=styl("Pages", Fore.MAGENTA), unit="page", ncols=80)
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=spinner, args=(stop_event, f"Target: {base_netloc}"))
    spinner_thread.start()

    try:
        while q and saved_count < max_pages:
            url = q.popleft()
            queued.discard(url)
            if url in visited:
                continue
            color_print(f"Visiting: {url}", "info")
            html, status = fetch_html(url)
            visited.add(url)

            if html:
                path = urlparse(url).path
                filename = sanitize_filename(path)
                filepath = os.path.join(output_dir, filename)
                final_path = filepath
                idx = 1

                while os.path.exists(final_path):
                    name, ext = os.path.splitext(filepath)
                    final_path = f"{name}_{idx}{ext}"
                    idx += 1

                try:
                    with open(final_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    color_print(f"Saved: {final_path}", "succ")
                    saved_count += 1
                    pbar.update(1)
                except Exception as e:
                    color_print(f"File could not be saved: {final_path} -> {e}", "error")

                links = extract_links(html, url)
                color_print(f"{len(links)} links found.", "debug")

                for link in links:
                    if urlparse(link).netloc != base_netloc:
                        continue
                    if link not in visited and link not in queued:
                        q.append(link)
                        queued.add(link)

            else:
                color_print(f"HTML could not be retrieved or is not valid HTML: {url} (status: {status})", "warn")

            time.sleep(delay)

    finally:
        stop_event.set()
        spinner_thread.join()
        pbar.close()

    color_print(f"Total saved pages: {saved_count}", "succ")
    color_print("Crawl completed. Goodbye! ✨", "info")
    return visited

if __name__ == "__main__":
    example = "https://instagram.com"
    banner(example)
    user_domain = input(styl("Enter target domain or URL (example: " + example + "): ", Fore.CYAN))

    if not user_domain:
        color_print("No domain entered. Exiting.", "error")
        sys.exit(1)

    user_output = input(styl("Enter output directory name (example: output): ", Fore.CYAN)).strip()
    if not user_output:
        user_output = "output"

    crawl(user_domain, user_output)
