import argparse
import time
import sys
from typing import List, Tuple
import urllib.request
import urllib.error


def parse_m3u(path: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Parse a simple M3U file into:
      - header lines (anything before the first #EXTINF)
      - a list of (extinf_line, url_line) channel entries
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f]

    header_lines: List[str] = []
    entries: List[Tuple[str, str]] = []

    i = 0
    seen_first_extinf = False

    while i < len(lines):
        line = lines[i].strip()

        # Everything before the first #EXTINF we treat as header/preamble
        if not seen_first_extinf and not line.startswith("#EXTINF"):
            header_lines.append(lines[i])
            i += 1
            continue

        if line.startswith("#EXTINF"):
            seen_first_extinf = True
            extinf_line = lines[i]
            # Next non-empty, non-comment line is assumed to be the URL
            url_line = ""
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate == "" or candidate.startswith("#"):
                    j += 1
                    continue
                url_line = lines[j]
                break

            if url_line:
                entries.append((extinf_line, url_line))
                i = j + 1
            else:
                # dangling EXTINF with no URL; skip
                i += 1
        else:
            # Any other lines after the first EXTINF that aren't part of an entry
            # are ignored for simplicity
            i += 1

    return header_lines, entries


def test_url(url: str, timeout: float = 5.0) -> bool:
    """
    Test a stream URL by trying to open it and read a small chunk.
    Returns True if it appears to work, False otherwise.
    """
    req = urllib.request.Request(
        url,
        headers={
            # Some servers are picky about User-Agent
            "User-Agent": "Mozilla/5.0 (Kodi-Check/1.0)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Basic status check
            if resp.status < 200 or resp.status >= 300:
                return False

            # Try to read a small chunk of data
            chunk = resp.read(1024)
            if not chunk:
                return False

            return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False
    except Exception:
        # Don't crash on weird edge cases
        return False


def clean_m3u(input_path: str, output_path: str, max_channels: int = None) -> None:
    header_lines, entries = parse_m3u(input_path)

    print(f"Loaded {len(entries)} channels from {input_path}")

    working_entries: List[Tuple[str, str]] = []

    for idx, (extinf, url) in enumerate(entries, start=1):
        if max_channels is not None and idx > max_channels:
            break

        print(f"[{idx}/{len(entries)}] Testing: {url}")
        ok = test_url(url)
        if ok:
            print("  → OK")
            working_entries.append((extinf, url))
        else:
            print("  → FAILED")

        # Small delay so we don't hammer servers
        time.sleep(0.3)

    print(f"\nWorking channels: {len(working_entries)}")

    # Ensure the file starts with #EXTM3U
    if not header_lines or not header_lines[0].strip().startswith("#EXTM3U"):
        header_lines = ["#EXTM3U"] + header_lines

    with open(output_path, "w", encoding="utf-8") as out:
        for line in header_lines:
            out.write(line + "\n")
        for extinf, url in working_entries:
            out.write(extinf + "\n")
            out.write(url + "\n")

    print(f"Cleaned playlist written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Test M3U playlist links and output only working channels."
    )
    parser.add_argument("input", help="Path to input M3U file")
    parser.add_argument(
        "output", nargs="?", default="combined_clean.m3u",
        help="Path to output cleaned M3U file (default: combined_clean.m3u)"
    )
    parser.add_argument(
        "--max-channels", type=int, default=None,
        help="Optional: only test the first N channels (for quick tests)"
    )

    args = parser.parse_args()

    try:
        clean_m3u(args.input, args.output, max_channels=args.max_channels)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
