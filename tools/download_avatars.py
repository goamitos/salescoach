#!/usr/bin/env python3
"""
One-time script to download and process real headshot photos for sales experts.
Downloads images from publicly accessible URLs, resizes to 200x200 RGBA PNG.
Skips avatars that already have real photos (> 10KB).
"""

import os
import sys
import requests
from PIL import Image, ImageOps
from io import BytesIO

AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "avatars")
SIZE = (200, 200)
MIN_REAL_SIZE = 10_000  # bytes — below this is a placeholder

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# slug → list of image URLs to try (first success wins)
AVATAR_URLS = {
    "anthony-iannarino": [
        "https://images1.penguinrandomhouse.com/author/2141124",
        "https://www.thesalesblog.com/hs-fs/hubfs/Anthony.jpg?width=628&height=744&name=Anthony.jpg",
    ],
    "giulio-segantini": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/66eb2435b34209f8d8375e32_Giulio.png",
    ],
    "mark-hunter": [
        "https://thesaleshunter.com/wp-content/uploads/2024/11/MH-Story-002-m.jpg",
    ],
    "jill-konrath": [
        "https://www.score.org/sites/default/files/styles/responsive_1_1_350w/public/d7_migration/04/jillkonrath.jpg?itok=KwUj8Iq4",
        "https://www.insidesalessummit.com/wp-content/uploads/2017/10/Jill-Konrath-Bubble-300x300.png",
    ],
    "shari-levitin": [
        "https://www.sharilevitin.com/wp-content/uploads/2023/02/Shari_web_img_19.jpg",
    ],
    "jim-keenan": [
        "https://media.licdn.com/dms/image/v2/D5603AQFWy9HRW8p7bw/profile-displayphoto-shrink_200_200/profile-displayphoto-shrink_200_200/0/1665051794060?e=2147483647&v=beta&t=lVBJxA4z6NkS2M7Td_0c4DoZEfwIRRc_C2g48kejN9E",
    ],
    "tiffani-bova": [
        "https://www.tiffanibova.com/wp-content/uploads/2024/01/tiffani-bova-short-bio-1.jpg",
    ],
    "amy-volas": [
        "https://images.squarespace-cdn.com/content/v1/5b3527969f8770f3f6c3ef7d/1586190450315-JLDMH7C8NF0EEAI6CT77/Amy+Volas+Headshot+2020.jpeg",
    ],
    "ron-kimhi": [
        "https://monday.com/elevate/wp-content/uploads/2024/06/Ron-Kimhi.png",
    ],
    "chris-orlob": [
        "https://cdn.prod.website-files.com/63b8a183ca2e4e7ea96dbc97/63d00b719902381d218825e0_About%20-%20Chris%20Image.webp",
        "https://cdn.prod.website-files.com/64132b83c8d22971aa1b9aa8/64132b83c8d229a93e1b9ad0_Rectangle%20237.webp",
    ],
    "becc-holland": [
        "https://media.licdn.com/dms/image/v2/D4E03AQFC7u2p5GGbYg/profile-displayphoto-scale_200_200/B4EZs1QQfYHUAY-/0/1766125013461?e=2147483647&v=beta&t=cbwnOfG9Rd56P5X3nelqXi_yX2PAuYYl-q_k7SrzWhg",
    ],
    "jen-allen-knuth": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/65665a7333d1a980144265c9_Jen.jpg",
    ],
    "alexandra-carter": [
        "https://alexcarterasks.com/wp-content/uploads/2023/10/new-alex-carter-homepage-v1.jpg",
    ],
    "kwame-christian": [
        "https://images.squarespace-cdn.com/content/v1/67a1f637f3e9ec60508de8a1/1ae9827a-2093-47cb-8edb-88c756cd8ef4/Kwame+Headshot+2024+-+4.JPG",
    ],
    "mo-bunnell": [
        "https://bunnellideagroup.com/wp-content/uploads/2025/12/mo-bunnell-speaking-bunnell-idea-group-business-development-training.webp",
    ],
    "rosalyn-santa-elena": [
        "https://www.revenueoperationsalliance.com/content/images/2023/03/rosalyn_santa_elena.jpeg",
    ],
    "mark-kosoglow": [
        "https://cdn.theorg.com/c9c3c2ca-5224-4ac4-a944-077544386f61_medium.jpg",
    ],
    "scott-leese": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/67925248655129979f83f149_Scott%20Leese.jpg",
    ],
    "sarah-brazier": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/67336c930ea9fc433d82fdd2_Sarah.jpg",
    ],
    "jesse-gittler": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/63d1348c32a91d35de1a6d8c_Jesse%20G.jpg",
    ],
    "chantel-george": [
        "https://cdn.prod.website-files.com/68ad812b7c9c6ad23ab40412/68cd9e2b700250e196071a18_68cd9e26f0812abbb59cb96e_chantel-george.jpeg",
    ],
    "bryan-tucker": [
        "https://www.stage2.capital/hs-fs/hubfs/1741276180641.jpg?width=200&height=200&name=1741276180641.jpg",
    ],
    "colin-specter": [
        "https://cdn.theorg.com/ab3e5196-8619-450d-ae7f-9accf3a857cf_medium.jpg",
        "https://dealhub.io/wp-content/uploads/2024/03/Avatar-Desktop-3.png",
    ],
    "kevin-dorsey": [
        "https://cdn.prod.website-files.com/66ad4a7975ff33f70e8584ab/66e0f9d7266f274093734156_kd.sketch.png",
    ],
    "belal-batrawy": [
        "https://kajabi-storefronts-production.kajabi-cdn.com/kajabi-storefronts-production/file-uploads/themes/2154047421/settings_images/a4e0db-aab1-a581-de73-2dec7bc243_face.png",
        "https://www.mixmax.com/hubfs/Belal%20Batrawy%20header%20Image.png",
    ],
    "caroline-celis": [
        "https://media.licdn.com/dms/image/v2/D5603AQG6dDaJyndKcw/profile-displayphoto-scale_200_200/B56ZjOpAO4IEAc-/0/1755813514983?e=2147483647&v=beta&t=VpA54bYw8J_UKqdXcoUpC4w28CMvCaya9lrOmAhYPtE",
    ],
    "julie-hansen": [
        "https://womensalespros.com/wp-content/uploads/2018/01/Julie_Hansen_230.png",
        "https://juliehansen.live/wp-content/uploads/2021/04/Julie-Hansen-about.png",
    ],
    "hannah-ajikawo": [
        "https://cdn.prod.website-files.com/62a76705791dc0a98eff4716/68afb84f5964ed22d2a8616b_Hannah.PNG",
    ],
    "justin-michael": [
        "https://cdn.prod.website-files.com/60e2668446bdfa278dfa6ae2/6128b8a3c3500fa149ea21db_JM%20borg.jpeg",
    ],
    "erica-franklin": [
        "https://cdn.theorg.com/d4249781-3810-48b0-8166-5d39ea8faaf1_medium.jpg",
        "https://iconelevenspeakers.com/wp-content/uploads/2024/06/Erica-Franklin-Headshot.jpg",
    ],
    "maria-bross": [
        "https://media.licdn.com/dms/image/v2/D5603AQFIoP9OdVSZ8w/profile-displayphoto-shrink_200_200/profile-displayphoto-shrink_200_200/0/1700591541315?e=2147483647&v=beta&t=L5kzYDc2CHXm_gnU2Fg4gLqwTF17Igiwbu4fxAPsaxM",
    ],
    "niraj-kapur": [
        "https://images.gr-assets.com/authors/1522197910p5/17770648.jpg",
        "https://nirajkapur.com/wp-content/uploads/2025/09/Everybody-Works-in-Sales-Niraj-Kapur-Sales-Trainer.webp",
    ],
}


def download_and_process(slug: str, urls: list[str]) -> bool:
    """Download first working URL, resize to 200x200 RGBA PNG."""
    dest = os.path.join(AVATAR_DIR, f"{slug}.png")

    # Skip if already a real photo
    if os.path.exists(dest) and os.path.getsize(dest) >= MIN_REAL_SIZE:
        print(f"  SKIP {slug} — already has real photo ({os.path.getsize(dest):,} bytes)")
        return True

    if not urls:
        print(f"  MISS {slug} — no URLs to try")
        return False

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            img = Image.open(BytesIO(resp.content))

            # Center-crop to square, then resize
            img = ImageOps.fit(img, SIZE, method=Image.LANCZOS)

            # Convert to RGBA
            img = img.convert("RGBA")

            img.save(dest, "PNG")
            size = os.path.getsize(dest)
            if size >= MIN_REAL_SIZE:
                print(f"  OK   {slug} — {size:,} bytes from {url[:80]}")
                return True
            else:
                print(f"  TINY {slug} — {size:,} bytes (keeping placeholder)")
                return False

        except Exception as e:
            print(f"  FAIL {slug} — {type(e).__name__}: {e} — {url[:80]}")
            continue

    print(f"  MISS {slug} — all URLs failed")
    return False


def main():
    print(f"Avatar directory: {os.path.abspath(AVATAR_DIR)}")
    print(f"Processing {len(AVATAR_URLS)} experts...\n")

    ok, skip, fail = 0, 0, 0
    for slug, urls in AVATAR_URLS.items():
        dest = os.path.join(AVATAR_DIR, f"{slug}.png")
        if os.path.exists(dest) and os.path.getsize(dest) >= MIN_REAL_SIZE:
            skip += 1
            print(f"  SKIP {slug}")
        elif download_and_process(slug, urls):
            ok += 1
        else:
            fail += 1

    print(f"\nDone: {ok} downloaded, {skip} skipped (already real), {fail} failed")
    if fail:
        print("\nFailed slugs still have placeholder avatars.")
        sys.exit(1)


if __name__ == "__main__":
    main()
