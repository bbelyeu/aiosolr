"""AIOSolr module."""

import json
import re

import aiohttp
import bleach

from urllib.parse import urlparse


class SolrError(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message, trace=None):
        self.message = message
        self.trace = trace


class Response:
    """Response class."""

    def __init__(self, data, status):
        self.data = data
        self.doc = data.get("doc", {})
        self.docs = data.get("response", {}).get("docs", [])
        mlt_data = data.get("moreLikeThis", {})
        if mlt_data:
            mlt_data_key = mlt_data.keys()[0]
            self.more_like_this = mlt_data[mlt_data_key].get("docs", [])
        self.status = status
        self.suggestions = []

        spellcheck = data.get("spellcheck", {})
        # Collations returns a list of strings with the first element set to "collations"
        if (
            "collations" in spellcheck
            and isinstance(spellcheck["collations"], list)
            and len(spellcheck["collations"]) > 1
        ):
            self.suggestions.append(spellcheck["collations"][1])

        # First element is the original query, 2nd element should be a dict of suggestions
        for solr_suggs in spellcheck.get("suggestions", []):
            if isinstance(solr_suggs, dict) and "suggestion" in solr_suggs:
                for sugg in solr_suggs["suggestion"]:
                    if sugg not in self.suggestions:
                        self.suggestions.append(sugg)


# TODO Support something other than JSON
class Solr:
    """Class representing a connection to Solr."""

    def __init__(
        self,
        scheme="http",
        host="127.0.0.1",
        port="80",
        collection="",
        timeout=(1, 3),
        ttl_dns_cache=3600,
        trace_configs=[],
        connection_url=None,
    ):
        """Init to instantiate Solr class.

        If the core/collection is not provided it should be passed to the methods as required.
        timeout, ttl_dns_cache, and trace_configs arguments are setup and sent to the
        AIOHTTP ClientSession class.
        See: https://docs.aiohttp.org/en/stable/client_reference.html
        """
        if connection_url is None:
            self.base_url = f"{scheme}://{host}:{port}/solr"
            self.collection = collection or None
        else:
            url = urlparse(connection_url)
            base_path, collection = url.path.rsplit("/", 1)
            self.base_url = f"{url.scheme}://{url.netloc}{base_path}"
            self.collection = collection or None

        self.response_writer = "json"
        if isinstance(timeout, tuple):
            # In some cases you may want to set the
            # connection timeout to 4 b/c of the TCP packet retransmission window
            # http://docs.python-requests.org/en/master/user/advanced/#timeouts
            # But in many cases that will be too slow
            self.timeout = aiohttp.ClientTimeout(
                sock_connect=timeout[0], sock_read=timeout[1]
            )
        else:
            self.timeout = aiohttp.ClientTimeout(total=timeout)

        # How long to cache DNS lookups - defaulting to an hour
        tcp_conn = aiohttp.TCPConnector(ttl_dns_cache=ttl_dns_cache)
        self.session = aiohttp.ClientSession(
            connector=tcp_conn, timeout=self.timeout, trace_configs=trace_configs
        )

    def _deserialize(self, resp):
        """Deserialize Solr response to Python object."""
        # TODO Handle types other than json
        if self.response_writer == "json":
            data = json.loads(resp.body)
        else:
            data = resp.body
        return Response(data, resp.status)

    async def _get(self, url, headers={}):
        """Network request to get data from a server."""
        if "Content-Type" not in headers and self.response_writer == "json":
            headers["Content-Type"] = "application/json"

        async with self.session.get(url, headers=headers) as response:
            response.body = await response.text()

        return response

    async def _get_check_ok_deserialize(self, url, headers={}):
        """Get url, check status 200 and return deserialized data."""
        response = await self._get(url, headers)

        if response.status != 200:
            msg, trace = None, None
            try:
                error = self._deserialize(response)
                msg = error.get("error", {}).get("msg", error)
                trace = error.get("error", {}).get("trace")
            except BaseException:
                msg = str(response.body)

            raise SolrError(msg, trace)

        return self._deserialize(response)

    def _get_collection(self, kwargs):
        """Get the collection name from the kwargs or instance variable."""
        if not kwargs.get("collection") and not self.collection:
            raise SolrError("Collection name not provided.")
        return kwargs.get("collection") or self.collection

    def _kwarg_to_query_string(self, kwargs):
        """Convert kwarg arguments to Solr query string."""
        # TODO Think about if I should validate any query params in kwargs?
        query_string = ""

        # fq param accepted multiple times in URL query string
        # https://lucene.apache.org/solr/guide/8_6/common-query-parameters.html
        if "fq" in kwargs and isinstance(kwargs.get("fq"), list):
            fqs = kwargs.pop("fq")
            for _fq in fqs:
                query_string += f"&fq={_fq}"

        # facet.field param accepted multiple times in URL query string
        if "facet.field" in kwargs and isinstance(kwargs.get("facet.field"), list):
            ffields = kwargs.pop("facet.field")
            for _ff in ffields:
                query_string += f"&facet.field={_ff}"

        # boost param accepted multiple times in URL query string
        if "boost" in kwargs and isinstance(kwargs.get("boost"), list):
            boost_fields = kwargs.pop("boost")
            for _bf in boost_fields:
                query_string += f"&boost={_bf}"

        for param, value in kwargs.items():
            if isinstance(value, list):
                separator = "+" if param in ("qf",) else ","
                query_string += "&{}={}".format(param, separator.join(value))
            else:
                query_string += f"&{param}={value}"

        return query_string

    async def _post(self, url, data):
        """Network request to post data to a server."""
        async with self.session.post(url, json=data) as response:
            response.body = await response.text()
        return response

    @staticmethod
    def _truncate_utf8(query, length, preserve_words=True):
        """Truncate utf8 strings.

        If applicable, remove isolated high surrogate code points at the end of
        the string. If it's not already unicode we need to make it a unicode
        string, but if it already is don't decode b/c it will throw UnicodeEncodeErrors.
        """
        if isinstance(query, bytes):
            query = query.decode("utf-8")
        # strip any whitespace first, that may be enough to get us under length
        query = query.strip()
        # Now measure actual length
        original_len = len(query)
        # Truncate if necessary
        query = query[:length]
        query = re.sub("[\ud800-\udbff]$", "", query)
        # Now if we did truncate, and if we want to, preserve words
        if original_len > len(query) and preserve_words:
            query = query.rsplit(" ", 1)[0]
        # Strip a final time in case truncating left whitespace on the end
        return query.strip()

    @staticmethod
    def clean(
        query,  # end user query
        allow_html_tags=False,
        allow_http=False,
        allow_wildcard=False,
        escape_chars=(":", r"\:"),  # tuple of (replace_me, replace_with)
        max_len=200,
        # regex of chars to remove
        remove_chars=r'[\&\|\!\(\)\{\}\[\]\^"~\?\\;]',
    ):
        """Typical query cleaning."""
        if not allow_http:
            query = re.sub(r"http\S+", "", query)

        # Remove these chars
        query = re.sub(remove_chars, "", query)

        if not allow_wildcard:
            query = query.replace("*", "")
            # Also remove urlencoded wildcard (*)
            query = query.replace("%2a", "")

        if escape_chars:
            # Escape these chars
            query = re.sub(escape_chars[0], escape_chars[1], query)

        if not allow_html_tags:
            # bleach it to prevent JS injection or other unwanted html
            # when displaying the query back to the user in a web page
            query = bleach.clean(query, strip=True)

        if max_len:
            # Queries that are too long can cause performance issues
            query = Solr._truncate_utf8(query, max_len)

        return query

    async def close(self):
        """Close down Client Session."""
        if self.session:
            await self.session.close()

    async def commit(self, handler="update", soft=False, **kwargs):
        """Perform a commit on the collection."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?"
        url += "softCommit=true" if soft is True else "commit=true"
        return await self._get_check_ok_deserialize(url)

    async def get(self, _id, handler="get", **kwargs):
        """Use Solr's built-in get handler to retrieve a single document by id."""
        collection = self._get_collection(kwargs)
        url = (
            f"{self.base_url}/{collection}/{handler}?id={_id}&wt={self.response_writer}"
        )
        url += self._kwarg_to_query_string(kwargs)
        return await self._get_check_ok_deserialize(url)

    async def suggestions(self, handler, query=None, build=False, **kwargs):
        """Query a requestHandler of class SearchHandler using the SuggestComponent."""
        if not query and not build:
            return SolrError("query or build required for suggestions.")

        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        if query:
            url += f"&suggest.q={query}"
        if build:
            url += "&suggest.build=true"
        response = await self._get_check_ok_deserialize(url)

        if query:
            if "+" in query:
                query = query.replace("+", " ")
            suggestions = []
            for name in response.data["suggest"].keys():
                try:
                    suggestions += [
                        {"match": s["term"], "payload": s["payload"]}
                        for s in response.data["suggest"][name][query]["suggestions"]
                    ]
                except KeyError:
                    pass
            return suggestions
        return response.data

    async def query(
        self,
        handler="select",
        query="*",
        spellcheck=False,
        spellcheck_dicts=[],
        **kwargs,
    ):
        """Query a requestHandler of class SearchHandler."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?q={query}&wt={self.response_writer}"
        if spellcheck:
            url += "&spellcheck=true"

            # Docs state the default SpellingQueryConverter class only handles ASCII so we
            # need to specify spellcheck.q for Unicode support
            # https://lucene.apache.org/solr/guide/8_6/spell-checking.html
            if "spellcheck.q" not in kwargs:
                url += f"&spellcheck.q={query}"

            for spellcheck_dict in spellcheck_dicts:
                # Solr allows the same url query param multiple times... go figure?
                url += f"&spellcheck.dictionary={spellcheck_dict}"

        url += self._kwarg_to_query_string(kwargs)

        solr_response = await self._get(url)
        if solr_response.status != 200:
            msg, trace = None, None
            try:
                error = self._deserialize(solr_response)
                msg = error.get("error", {}).get("msg", error)
                trace = error.get("error", {}).get("trace")
            except BaseException:
                msg = str(solr_response.body)

            raise SolrError(msg, trace)

        return self._deserialize(solr_response)

    async def update(self, data, handler="update", **kwargs):
        """Update a document using Solr's update handler."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        url += self._kwarg_to_query_string(kwargs)

        response = await self._post(url, data)
        if response.status == 200:
            data = self._deserialize(response)
        else:
            msg, trace = None, None
            try:
                error = self._deserialize(response)
                msg = error.get("error", {}).get("msg", error)
                trace = error.get("error", {}).get("trace")
            except BaseException:
                msg = str(response.body)

            raise SolrError(msg, trace)

        return data
