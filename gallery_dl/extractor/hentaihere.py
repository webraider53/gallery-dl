# -*- coding: utf-8 -*-

# Copyright 2016-2018 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extract hentai-manga from https://hentaihere.com/"""

from .common import ChapterExtractor, MangaExtractor, Extractor
from .. import text
import re
import json


class HentaihereExtractor(Extractor):
    """Base class for hbrowse extractors"""
    category = "hentaihere"
    root = "https://hentaihere.com"

    @staticmethod
    def parse_page(page, data):
        """Parse metadata on 'page' and add it to 'data'"""
        minfo, pos = text.extract(page, '<div id="info">', '</div>')

        # data = {}
        text.extract_all(page, (
            ('-', '<div class="fieldname">', '</div>'),  # parody
            ('-', '<div class="fieldname">', '</div>'),  # ranking
            ('-', '<div class="fieldname">', '</div>'),  # status
            ('-', '<div class="fieldname">', '</div>'),  # release_year
            ('-', '<div class="fieldname">', '</div>'),  # rating
            ('-', '<div class="fieldname">', '</div>'),  # views
            ('circle', '<div class="fieldname">', '</div>'),
            ('artist', '<div class="fieldname">', '</div>'),
            ('category', '<div class="fieldname">', '</div>'),
            ('content', '<div class="fieldname">', '</div>'),  # tags
            ('character', '<div class="fieldname">', '</div>'),
            ('language', '<div class="fieldname">', '</div>'),
        ), values=data, pos=pos)

        data.pop("-", None)
        # data["-"] = text.remove_html(data["-"])

        if "tags" not in data:
            data["tags"] = []

        for i in ["artist", "content", "category", "circle", "character", "language"]:
            for t in text.extract_iter(data[i], 'class="tagbutton">', "</a>"):
                t = text.remove_html(t).strip().lower()
                if t == "-":
                    continue
                data["tags"].append(t)

        for key in data:
            if data[key] == "-":
                data[key] = ""

        # data["tags"] = " ".join([data["tags"], data["category"], data["circle"], data["character"]])
        data.pop("content", None)

        # data["circle"] = text.remove_html(data["circle"]).split(':', 1)[1].strip().lower()
        data.pop("circle", None)
        # data["artist"] = text.remove_html(data["artist"]).split(':', 1)[1].strip().lower()
        data.pop("artist", None)
        # data["category"] = text.remove_html(data["category"]).split(':', 1)[1].strip().lower()
        data.pop("category", None)
        # data["tags"] = text.remove_html(data["tags"]).split(':', 1)[1].strip().lower()
        # data["character"] = text.remove_html(data["character"]).split(':', 1)[1].strip().lower()
        data.pop("character", None)
        data["language"] = text.remove_html(data["language"]).split(':', 1)[1].strip().lower()

        data["rating"] = "e"

        return data


class HentaihereMangaExtractor(HentaihereExtractor, MangaExtractor):
    """Extractor for hmanga from hentaihere.com"""
    category = "hentaihere"
    pattern = [r"(?:https?://)?(?:www\.)?(hentaihere\.com/m/S\d+)/?$"]
    scheme = "https"
    test = [
        ("https://hentaihere.com/m/S13812", {
            "url": "d1ba6e28bb2162e844f8559c2b2725ba0a093559",
            "keyword": "13c1ce7e15cbb941f01c843b0e89adc993d939ac",
        }),
        ("https://hentaihere.com/m/S7608", {
            "url": "6c5239758dc93f6b1b4175922836c10391b174f7",
            "keyword": "675c7b7a4fa52cf569c283553bd16b4200a5cd36",
        }),
    ]

    def chapters(self, page):
        results = []
        manga_id = text.parse_int(self.url.rstrip("/").rpartition("/")[2][1:])
        manga, pos = text.extract(page, '<span itemprop="name">', '</span>')
        mtype, pos = text.extract(page, '<span class="mngType text-danger">[', ']</span>', pos)

        while True:
            marker, pos = text.extract(
                page, '<li class="sub-chp clearfix">', '', pos)
            if marker is None:
                return results
            url, pos = text.extract(page, '<a href="', '"', pos)
            chapter, pos = text.extract(page, 'title="Tagged: -">\n', '<', pos)
            chapter_id, pos = text.extract(page, '/C', '"', pos)
            chapter, _, title = text.unescape(chapter).strip().partition(" - ")
            results.append((url, self.parse_page(page, {
                "manga_id": manga_id, "manga": manga, "type": mtype,
                "chapter_id": text.parse_int(chapter_id),
                "chapter": text.parse_int(chapter),
                "title": title, "lang": "en", "language": "English",
            })))


class HentaihereChapterExtractor(HentaihereExtractor, ChapterExtractor):
    """Extractor for a single manga chapter from hentaihere.com"""
    category = "hentaihere"
    archive_fmt = "{chapter_id}_{page}"
    pattern = [r"(?:https?://)?(?:www\.)?hentaihere\.com/m/S(\d+)/(\d+)"]
    test = [("https://hentaihere.com/m/S13812/1/1/", {
        "url": "964b942cf492b3a129d2fe2608abfc475bc99e71",
        "keyword": "e9382a9be337abce3db2b1132e85751379dc05c5",
    })]

    def __init__(self, match):
        self.manga_id, self.chapter = match.groups()
        url = "https://hentaihere.com/m/S{}/{}/1".format(
            self.manga_id, self.chapter)
        ChapterExtractor.__init__(self, url)

    def get_metadata(self, page):
        title = text.extract(page, "<title>", "</title>")[0]
        chapter_id = text.extract(page, 'report/C', '"')[0]
        pattern = r"Page 1 \| (.+) \(([^)]+)\) - Chapter \d+: (.+) by (.+) at "
        match = re.match(pattern, title)
        return {
            "manga": match.group(1),
            "manga_id": text.parse_int(self.manga_id),
            "chapter": text.parse_int(self.chapter),
            "chapter_id": text.parse_int(chapter_id),
            "type": match.group(2),
            "title": match.group(3),
            "author": match.group(4),
            "lang": "en",
            "language": "English",
            "category": self.category
        }

    @staticmethod
    def get_images(page):
        images = text.extract(page, "var rff_imageList = ", ";")[0]
        return [
            ("https://hentaicdn.com/hentai" + part, None)
            for part in json.loads(images)
        ]
