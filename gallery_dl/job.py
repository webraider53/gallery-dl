# -*- coding: utf-8 -*-

# Copyright 2015-2018 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

import sys
import time
import json
import hashlib
import logging
from . import extractor, downloader, postprocessor
from . import config, text, util, output, exception
from .extractor.message import Message


class Job():
    """Base class for Job-types"""
    ulog = None
    kwds = {}

    def __init__(self, url, parent=None):
        self.url = url
        self.extractor = extractor.find(url)
        if self.extractor is None:
            raise exception.NoExtractorError(url)
        self.extractor.log.debug(
            "Using %s for '%s'", self.extractor.__class__.__name__, url)

        # url predicates
        self.pred_url = self._prepare_predicates(
            "image", [util.UniquePredicate()], True)

        # queue predicates
        self.pred_queue = self._prepare_predicates(
            "chapter", [], False)

        # category transfer
        if parent and parent.extractor.config(
                "category-transfer", parent.extractor.categorytransfer):
            self.extractor.category = parent.extractor.category
            self.extractor.subcategory = parent.extractor.subcategory

        # user-supplied metadata
        self.userkwds = self.extractor.config("keywords")

    def run(self):
        """Execute or run the job"""
        try:
            log = self.extractor.log
            for msg in self.extractor:
                self.dispatch(msg)
        except exception.AuthenticationError as exc:
            msg = str(exc) or "Please provide a valid username/password pair."
            log.error("Authentication failed: %s", msg)
        except exception.AuthorizationError:
            log.error("You do not have permission to access the resource "
                      "at '%s'", self.url)
        except exception.NotFoundError as exc:
            res = str(exc) or "resource (gallery/image/user)"
            log.error("The %s at '%s' does not exist", res, self.url)
        except exception.HttpError as exc:
            err = exc.args[0]
            if isinstance(err, Exception):
                err = "{}: {}".format(err.__class__.__name__, err)
            log.error("HTTP request failed:  %s", err)
        except exception.FormatError as exc:
            err, obj = exc.args
            log.error("Applying %s format string failed:  %s: %s",
                      obj, err.__class__.__name__, err)
        except exception.FilterError as exc:
            err = exc.args[0]
            log.error("Evaluating filter expression failed:  %s: %s",
                      err.__class__.__name__, err)
        except exception.StopExtraction:
            pass
        except OSError as exc:
            log.error("Unable to download data:  %s: %s",
                      exc.__class__.__name__, exc)
            log.debug("", exc_info=True)
        except exception.UploadFail as exc:
            log.error("Unable to upload data:  %s: %s",
                      exc.__class__.__name__, exc)
            log.debug("", exc_info=True)
        except Exception as exc:
            log.error(("An unexpected error occurred: %s - %s. "
                       "Please run gallery-dl again with the --verbose flag, "
                       "copy its output and report this issue on "
                       "https://github.com/mikf/gallery-dl/issues ."),
                      exc.__class__.__name__, exc)
            log.debug("", exc_info=True)
        self.handle_finalize()

    def dispatch(self, msg):
        """Call the appropriate message handler"""
        if msg[0] == Message.Url:
            _, url, kwds = msg
            if self.pred_url(url, kwds):
                self.update_kwdict(kwds)
                self.handle_url(url, kwds)

        elif msg[0] == Message.Directory:
            self.update_kwdict(msg[1])
            self.handle_directory(msg[1])

        elif msg[0] == Message.Queue:
            _, url, kwds = msg
            if self.pred_queue(url, kwds):
                self.handle_queue(url, kwds)

        elif msg[0] == Message.Urllist:
            _, urls, kwds = msg
            if self.pred_url(urls[0], kwds):
                self.update_kwdict(kwds)
                self.handle_urllist(urls, kwds)

        elif msg[0] == Message.Version:
            if msg[1] != 1:
                raise "unsupported message-version ({}, {})".format(
                    self.extractor.category, msg[1]
                )
            # TODO: support for multiple message versions

    def handle_url(self, url, keywords):
        """Handle Message.Url"""
        self.kwds.update(keywords)

    def handle_urllist(self, urls, keywords):
        """Handle Message.Urllist"""
        self.handle_url(urls[0], keywords)

    def handle_directory(self, keywords):
        """Handle Message.Directory"""
        self.kwds.update(keywords)

    def handle_queue(self, url, keywords):
        """Handle Message.Queue"""
        self.kwds.update(keywords)

    def handle_finalize(self):
        """Handle job finalization"""

    def update_kwdict(self, kwdict):
        """Update 'kwdict' with additional metadata"""
        kwdict["category"] = self.extractor.category
        kwdict["subcategory"] = self.extractor.subcategory
        if self.userkwds:
            kwdict.update(self.userkwds)

    def _prepare_predicates(self, target, predicates, skip=True):
        pfilter = self.extractor.config(target + "-filter")
        if pfilter:
            try:
                pred = util.FilterPredicate(pfilter, target)
            except (SyntaxError, ValueError, TypeError) as exc:
                self.extractor.log.warning(exc)
            else:
                predicates.append(pred)

        prange = self.extractor.config(target + "-range")
        if prange:
            try:
                pred = util.RangePredicate(prange)
            except ValueError as exc:
                self.extractor.log.warning(
                    "invalid %s range: %s", target, exc)
            else:
                if skip and pred.lower > 1 and not pfilter:
                    pred.index += self.extractor.skip(pred.lower - 1)
                predicates.append(pred)

        return util.build_predicate(predicates)

    def _write_unsupported(self, url):
        if self.ulog:
            self.ulog.info(url)


class DownloadJob(Job):
    """Download images into appropriate directory/filename locations"""

    def __init__(self, url, parent=None):
        Job.__init__(self, url, parent)
        self.log = logging.getLogger("download")
        self.pathfmt = None
        self.archive = None
        self.sleep = None
        self.downloaders = {}
        self.postprocessors = None
        self.out = output.select()

    def handle_url(self, url, keywords, fallback=None):
        """Download the resource specified in 'url'"""
        super().handle_url(url=url, keywords=keywords)
        keywords = self.kwds
        # self.log.debug("DownloadJob:handle_url(url=%(url)s, keywords=%(keywords)s, fallback=%(fallback)s)" % {
        #    "url": url,
        #    "keywords": keywords,
        #    "fallback": fallback
        # })
        # prepare download
        self.pathfmt.set_keywords(keywords)

        if self.postprocessors:
            for pp in self.postprocessors:
                pp.prepare(self.pathfmt)

        if self.pathfmt.exists(self.archive):
            self.handle_skip()
            self.handle_postprocessors()
            return

        if self.sleep:
            self.log.debug("DownloadJob:Sleep a bit: %s", self.sleep)
            time.sleep(self.sleep)

        # download from URL
        if not self.download(url):

            # use fallback URLs if available
            for num, url in enumerate(fallback or (), 1):
                self.log.info("Trying fallback URL #%d", num)
                if self.download(url):
                    break
            else:
                # download failed
                self.log.error("Failed to download %s", self.pathfmt.filename or url)
                return

        if not self.pathfmt.temppath:
            self.handle_skip()
            return

        # download succeeded
        self.pathfmt.finalize()
        self.out.success(self.pathfmt.path, 0)

        self.handle_postprocessors()

        if self.archive:
            self.archive.add(keywords)
        self._skipcnt = 0

    def handle_postprocessors(self):
        # run post processors
        if self.postprocessors:
            for pp in self.postprocessors:
                pp.run(self.pathfmt)

    def handle_urllist(self, urls, keywords):
        """Download the resource specified in 'url'"""
        fallback = iter(urls)
        url = next(fallback)
        self.handle_url(url, keywords, fallback)

    def handle_directory(self, keywords):
        """Set and create the target directory for downloads"""
        super().handle_directory(keywords=keywords)
        keywords = self.kwds
        if not self.pathfmt:
            self.initialize(keywords)
        else:
            self.pathfmt.set_directory(keywords)

    def handle_queue(self, url, keywords):
        super().handle_queue(url=url, keywords=keywords)
        keywords = self.kwds
        try:
            self.__class__(url, self).run()
        except exception.NoExtractorError:
            self._write_unsupported(url)

    def handle_finalize(self):
        if self.postprocessors:
            for pp in self.postprocessors:
                pp.finalize()

    def handle_skip(self):
        self.out.skip(self.pathfmt.path)
        if self._skipexc:
            self._skipcnt += 1
            if self._skipcnt >= self._skipmax:
                raise self._skipexc()

    def download(self, url):
        """Download 'url'"""
        scheme = url.partition(":")[0]
        downloader = self.get_downloader(scheme)
        if downloader:
            return downloader.download(url, self.pathfmt)
        self._write_unsupported(url)
        return False

    def get_downloader(self, scheme):
        """Return a downloader suitable for 'scheme'"""
        if scheme == "https":
            scheme = "http"
        try:
            return self.downloaders[scheme]
        except KeyError:
            pass

        klass = downloader.find(scheme)
        if klass and config.get(("downloader", scheme, "enabled"), True):
            instance = klass(self.extractor, self.out)
        else:
            instance = None
            self.log.error("'%s:' URLs are not supported/enabled", scheme)
        self.downloaders[scheme] = instance
        return instance

    def initialize(self, keywords=None):
        """Delayed initialization of PathFormat, etc."""
        self.pathfmt = util.PathFormat(self.extractor)
        if keywords:
            self.pathfmt.set_directory(keywords)
        self.sleep = self.extractor.config("sleep")

        skip = self.extractor.config("skip", True)
        if skip:
            self._skipexc = None
            if isinstance(skip, str):
                skip, _, smax = skip.partition(":")
                if skip == "abort":
                    self._skipexc = exception.StopExtraction
                elif skip == "exit":
                    self._skipexc = sys.exit
                self._skipcnt = 0
                self._skipmax = text.parse_int(smax)
        else:
            self.pathfmt.exists = lambda x=None: False

        archive = self.extractor.config("archive")
        if archive:
            path = util.expand_path(archive)
            self.archive = util.DownloadArchive(path, self.extractor)

        postprocessors = self.extractor.config("postprocessors")
        if postprocessors:
            self.postprocessors = []
            for pp_dict in postprocessors:
                whitelist = pp_dict.get("whitelist")
                blacklist = pp_dict.get("blacklist")
                if (whitelist and self.extractor.category not in whitelist or
                        blacklist and self.extractor.category in blacklist):
                    continue
                name = pp_dict.get("name")
                pp_cls = postprocessor.find(name)
                if not pp_cls:
                    postprocessor.log.warning("module '%s' not found", name)
                    continue
                try:
                    pp_obj = pp_cls(self.pathfmt, pp_dict)
                except Exception as exc:
                    postprocessor.log.error(
                        "'%s' initialization failed:  %s: %s",
                        name, exc.__class__.__name__, exc)
                else:
                    self.postprocessors.append(pp_obj)
            self.extractor.log.debug(
                "Active postprocessor modules: %s", self.postprocessors)


class SimulationJob(DownloadJob):
    """Simulate the extraction process without downloading anything"""

    def handle_url(self, url, keywords, fallback=None):
        self.pathfmt.set_keywords(keywords)
        self.out.skip(self.pathfmt.path)
        if self.sleep:
            time.sleep(self.sleep)
        if self.archive:
            self.archive.add(keywords)

    def handle_directory(self, keywords):
        if not self.pathfmt:
            self.initialize()


class KeywordJob(Job):
    """Print available keywords"""

    def handle_url(self, url, keywords):
        super().handle_url(url=url, keywords=keywords)
        keywords = self.kwds
        print("\nKeywords for filenames and --filter:")
        print("------------------------------------")
        self.print_keywords(keywords)
        raise exception.StopExtraction()

    def handle_directory(self, keywords):
        super().handle_directory(keywords=keywords)
        keywords = self.kwds
        print("Keywords for directory names:")
        print("-----------------------------")
        self.print_keywords(keywords)

    def handle_queue(self, url, keywords):
        super().handle_queue(url=url, keywords=keywords)
        keywords = self.kwds
        if not keywords:
            self.extractor.log.info(
                "This extractor delegates work to other extractors "
                "and does not provide any keywords on its own. Try "
                "'gallery-dl -K \"%s\"' instead.", url)
        else:
            print("Keywords for --chapter-filter:")
            print("------------------------------")
            self.print_keywords(keywords)
            if self.extractor.categorytransfer:
                print()
                KeywordJob(url, self).run()
        raise exception.StopExtraction()

    @staticmethod
    def print_keywords(keywords, prefix=""):
        """Print key-value pairs with formatting"""
        suffix = "]" if prefix else ""
        for key, value in sorted(keywords.items()):
            key = prefix + key + suffix

            if isinstance(value, dict):
                KeywordJob.print_keywords(value, key + "[")

            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    KeywordJob.print_keywords(value[0], key + "[][")
                else:
                    print(key, "[]", sep="")
                    for val in value:
                        print("  -", val)

            else:
                # string or number
                print(key, "\n  ", value, sep="")


class UrlJob(Job):
    """Print download urls"""
    maxdepth = 1

    def __init__(self, url, parent=None, depth=1):
        Job.__init__(self, url, parent)
        self.depth = depth
        if depth >= self.maxdepth:
            self.handle_queue = self.handle_url

    @staticmethod
    def handle_url(url, _):
        print(url)

    @staticmethod
    def handle_urllist(urls, _):
        prefix = ""
        for url in urls:
            print(prefix, url, sep="")
            prefix = "| "

    def handle_queue(self, url, _):
        try:
            UrlJob(url, self, self.depth + 1).run()
        except exception.NoExtractorError:
            self._write_unsupported(url)


class TestJob(DownloadJob):
    """Generate test-results for extractor runs"""

    class HashIO():
        """Minimal file-like interface"""

        def __init__(self, hashobj):
            self.hashobj = hashobj
            self.path = ""
            self.size = 0
            self.has_extension = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def open(self, mode):
            self.size = 0
            return self

        def write(self, content):
            """Update SHA1 hash"""
            self.size += len(content)
            self.hashobj.update(content)

        def tell(self):
            return self.size

        def part_size(self):
            return 0

    def __init__(self, url, parent=None, content=False):
        DownloadJob.__init__(self, url, parent)
        self.content = content
        self.list_url = []
        self.list_keyword = []
        self.list_archive = []
        self.hash_url = hashlib.sha1()
        self.hash_keyword = hashlib.sha1()
        self.hash_archive = hashlib.sha1()
        self.hash_content = hashlib.sha1()
        if content:
            self.fileobj = self.HashIO(self.hash_content)
            self.get_downloader("http")._check_extension = lambda a, b: None

    def run(self):
        for msg in self.extractor:
            self.dispatch(msg)

    def handle_url(self, url, keywords):
        self.update_url(url)
        self.update_keyword(keywords)
        self.update_archive(keywords)
        self.update_content(url)

    def handle_urllist(self, urls, keywords):
        self.handle_url(urls[0], keywords)

    def handle_directory(self, keywords):
        self.update_keyword(keywords, False)

    def handle_queue(self, url, keywords):
        self.update_url(url)
        self.update_keyword(keywords)

    def update_url(self, url):
        """Update the URL hash"""
        self.list_url.append(url)
        self.hash_url.update(url.encode())

    def update_keyword(self, kwdict, to_list=True):
        """Update the keyword hash"""
        if to_list:
            self.list_keyword.append(kwdict.copy())
        self.hash_keyword.update(
            json.dumps(kwdict, sort_keys=True).encode())

    def update_archive(self, kwdict):
        """Update the archive-id hash"""
        archive_id = self.extractor.archive_fmt.format_map(kwdict)
        self.list_archive.append(archive_id)
        self.hash_archive.update(archive_id.encode())

    def update_content(self, url):
        """Update the content hash"""
        if self.content:
            scheme = url.partition(":")[0]
            self.get_downloader(scheme).download(url, self.fileobj)


class DataJob(Job):
    """Collect extractor results and dump them"""

    def __init__(self, url, parent=None, file=sys.stdout, ensure_ascii=True):
        Job.__init__(self, url, parent)
        self.file = file
        self.data = []
        self.ascii = config.get(("output", "ascii"), ensure_ascii)

    def run(self):
        # collect data
        try:
            for msg in self.extractor:
                self.dispatch(msg)
        except exception.StopExtraction:
            pass
        except Exception as exc:
            self.data.append((exc.__class__.__name__, str(exc)))
        except BaseException:
            pass

        if config.get(("output", "num-to-str"), False):
            for msg in self.data:
                util.transform_dict(msg[-1], util.number_to_string)

        # dump to 'file'
        json.dump(
            self.data, self.file,
            sort_keys=True, indent=2, ensure_ascii=self.ascii,
        )
        self.file.write("\n")

    def handle_url(self, url, keywords):
        self.data.append((Message.Url, url, keywords.copy()))

    def handle_urllist(self, urls, keywords):
        self.data.append((Message.Urllist, list(urls), keywords.copy()))

    def handle_directory(self, keywords):
        self.data.append((Message.Directory, keywords.copy()))

    def handle_queue(self, url, keywords):
        self.data.append((Message.Queue, url, keywords.copy()))

    def handle_finalize(self):
        self.file.close()
