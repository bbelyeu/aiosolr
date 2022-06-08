"""
AsyncIO Python client for Apache Solr

The idea behind this module is to provide easy access to Solr in an efficient manner.
This is achieved through using AIOHTTP client sessions with shared connection pooling.
Ease of use is provided by mapping Solr Handlers to methods making it RPC like.
"""

import asyncio
import json
import logging
import re
import urllib.parse

import aiohttp
import bleach

LOGGER = logging.getLogger("aiosolr")


class SolrError(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message, *args, trace=None, **kwargs):
        self.message = message
        self.trace = trace
        super().__init__(message, *args, **kwargs)

    def __str__(self):
        return self.message


class Response:
    """Response class."""

    def __init__(self, data, status):
        self.data = data
        self.doc = {}
        self.docs = []
        self.more_like_this = []
        self.status = status
        self.spelling_suggestions = []

        if isinstance(data, dict):
            self.doc = data.get("doc", {})
            response = data.get("response", {})
            if response:
                self.docs = response.get("docs", [])
            mlt_data = data.get("moreLikeThis", {})

            if mlt_data:
                mlt_data_key = list(mlt_data.keys())[0]
                self.more_like_this = mlt_data[mlt_data_key].get("docs", [])

            spellcheck = data.get("spellcheck", {})
            # Collations returns a list of strings with the first element set to "collations"
            if (
                "collations" in spellcheck
                and isinstance(spellcheck["collations"], list)
                and len(spellcheck["collations"]) > 1
            ):
                self.spelling_suggestions.append(spellcheck["collations"][1])

            # First element is the original query, 2nd element should be a dict of suggestions
            for solr_suggs in spellcheck.get("suggestions", []):
                if isinstance(solr_suggs, dict) and "suggestion" in solr_suggs:
                    for sugg in solr_suggs["suggestion"]:
                        if sugg not in self.spelling_suggestions:
                            self.spelling_suggestions.append(sugg)

    def get(self, name, default=None):
        """Get an attribute or return default value."""
        return getattr(self, name, default)


# TODO Support something other than JSON
class Client:
    """Class representing a client connection to Solr."""

    def __init__(  # pylint: disable=dangerous-default-value
        self,
        *,
        collection="",
        connection_url=None,
        debug=False,
        host="127.0.0.1",
        port="80",
        scheme="http",
        timeout=(1, 3),
        trace_configs=[],
        ttl_dns_cache=3600,
    ):
        """Init to instantiate Solr class.

        If the core/collection is not provided it should be passed to the methods as required.
        timeout, ttl_dns_cache, and trace_configs arguments are stored to be used when setting up
        the AIOHTTP ClientSession class.
        See: https://docs.aiohttp.org/en/stable/client_reference.html
        """
        if connection_url is None:
            self.base_url = f"{scheme}://{host}:{port}/solr"
            self.collection = collection or None
        else:
            url = urllib.parse.urlparse(connection_url)
            base_path, collection = url.path.rsplit("/", 1)
            self.base_url = f"{url.scheme}://{url.netloc}{base_path}"
            self.collection = collection or None

        self.response_writer = "json"
        if isinstance(timeout, tuple):
            # In some cases you may want to set the
            # connection timeout to 4 b/c of the TCP packet retransmission window
            # http://docs.python-requests.org/en/master/user/advanced/#timeouts
            # But in many cases that will be too slow
            self.timeout = aiohttp.ClientTimeout(sock_connect=timeout[0], sock_read=timeout[1])
        else:
            self.timeout = aiohttp.ClientTimeout(total=timeout)

        self.session = None
        # How long to cache DNS lookups - defaulting to an hour
        self.tcp_conn = aiohttp.TCPConnector(ttl_dns_cache=ttl_dns_cache)
        self.trace_configs = trace_configs

        if debug:
            LOGGER.setLevel(logging.DEBUG)
            logging.getLogger("aiohttp.client").setLevel(logging.DEBUG)

    def _deserialize(self, resp):
        """Deserialize Solr response to Python object."""
        # TODO Handle types other than json
        if self.response_writer == "json":
            data = json.loads(resp.body)
        else:
            data = resp.body
        return Response(data, resp.status)

    # TODO Make headers something other than a dictionary
    # pylint: disable=dangerous-default-value
    async def _get(self, url, *, body={}, headers={}):
        """Network request to get data from a server."""
        if "Accept" not in headers and self.response_writer == "json":
            headers["Accept"] = "application/json"

        if not self.session:
            await self.setup()

        LOGGER.debug(url)
        LOGGER.debug(headers)
        if body:
            LOGGER.debug(body)
            headers["Content-Type"] = "application/json"
            async with self.session.request("GET", url, headers=headers, json=body) as response:
                response.body = await response.text()
        else:
            async with self.session.get(url, headers=headers) as response:
                response.body = await response.text()

        return response

    # TODO Make headers something other than a dictionary
    # pylint: disable=dangerous-default-value
    async def _get_check_ok_deserialize(self, url, *, body={}, headers={}):
        """Get url, check status 200 and return deserialized data."""
        response = await self._get(url, body=body, headers=headers)

        if response.status != 200:
            msg, trace = None, None
            try:
                error = self._deserialize(response)
                msg = error.data.get("error", {}).get("msg", error)
                trace = error.data.get("error", {}).get("trace")
            except BaseException:  # pylint: disable=broad-except
                # TODO Figure out all the possible exceptions and catch them instead of BaseExcept
                msg = str(response.body)

            raise SolrError(msg, trace)

        return self._deserialize(response)

    def _get_collection(self, kwargs):
        """Get the collection name from the kwargs or instance variable."""
        if "collection" in kwargs:
            return kwargs.pop("collection")
        if self.collection:
            return self.collection
        raise SolrError("Collection name not provided.")

    @staticmethod
    def _kwargs_to_json_body(kwargs):
        """Convert kwarg arguments to GET body for JSON Request API."""
        return {"params": kwargs}

    @staticmethod
    def _kwargs_to_query_string(kwargs):
        """Convert kwarg arguments to Solr query string."""
        # TODO Think about if I should validate any query params in kwargs?
        query_string = ""

        # fq param accepted multiple times in URL query string
        # https://lucene.apache.org/solr/guide/8_6/common-query-parameters.html
        if "fq" in kwargs and isinstance(kwargs.get("fq"), list):
            fqs = kwargs.pop("fq")
            for _fq in fqs:
                _fq = urllib.parse.quote_plus(str(_fq), encoding="utf8")
                query_string += f"&fq={_fq}"

        # facet.field param accepted multiple times in URL query string
        if "facet.field" in kwargs and isinstance(kwargs.get("facet.field"), list):
            ffields = kwargs.pop("facet.field")
            for _ff in ffields:
                _ff = urllib.parse.quote_plus(str(_ff), encoding="utf8")
                query_string += f"&facet.field={_ff}"

        # boost param accepted multiple times in URL query string
        if "boost" in kwargs and isinstance(kwargs.get("boost"), list):
            boost_fields = kwargs.pop("boost")
            for _bf in boost_fields:
                _bf = urllib.parse.quote_plus(str(_bf), encoding="utf8")
                query_string += f"&boost={_bf}"

        for param, value in kwargs.items():
            if isinstance(value, list):
                separator = "+" if param in ("qf",) else ","
                clean_vals = [urllib.parse.quote_plus(str(i), encoding="utf8") for i in value]
                query_string += "&{}={}".format(param, separator.join(clean_vals))
            elif isinstance(value, bool):
                # using title cased bools results in the following error in Solr logs
                # org.apache.solr.common.SolrException: invalid boolean value: False
                query_string += f"&{param}=true" if value else f"&{param}=false"
            else:
                clean_val = urllib.parse.quote_plus(str(value), encoding="utf8")
                query_string += f"&{param}={clean_val}"

        return query_string

    async def _post(self, url, data, headers=None):
        """Network request to post data to a server."""
        if not self.session:
            await self.setup()

        if isinstance(data, (dict, list)):
            if headers:
                headers["Content-Type"] = "application/json"
            else:
                headers = {"Content-Type": "application/json"}

            LOGGER.debug(url)
            async with self.session.post(url, headers=headers, json=data) as response:
                response.body = await response.text()

        else:
            if headers:
                headers["Content-Type"] = "text/xml"
            else:
                headers = {"Content-Type": "text/xml"}

            async with self.session.post(url, data=data, headers=headers) as response:
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

    async def check_dataimport_status(
        self, handler="dataimport", max_retries=5, sleep_interval=60, **kwargs
    ):
        """Loop and check dataimport status until it is successful."""
        LOGGER.debug("Checking status of indexing...")

        status = False
        response_body = None
        retries = 0

        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?command=status&wt={self.response_writer}"
        while status is False and retries < max_retries:
            try:
                solr_response = await self._get(url)
                response_body = self._deserialize(solr_response)
                if response_body.data["status"] == "idle":
                    LOGGER.debug("Indexing completed!")
                    status = response_body.data["statusMessages"]
                    break
            except BaseException:  # pylint: disable=broad-except
                # TODO Figure out all the possible exceptions and catch them instead of BaseExcept
                LOGGER.debug("Status not ready yet, sleeping...")

            retries += 1
            await asyncio.sleep(sleep_interval)

        if (
            response_body
            and response_body.status == 200
            and status is not False
            and retries < max_retries
        ):
            LOGGER.debug(status)
        else:
            msg = (
                "Unable to verify dataimport success on %s after %s seconds and %s retries and "
                "status message %s!",
                collection,
                sleep_interval * retries,
                retries,
                status,
            )
            # LOGGER.error(msg)
            raise SolrError(msg)

    @staticmethod
    def clean(
        query,  # end user query
        allow_html_tags=False,
        allow_http=False,
        allow_wildcard=False,
        escape_chars=(":", r"\:"),  # tuple of (replace_me, replace_with)
        max_len=0,
        # regex of chars to remove
        remove_chars=r'[\&\|\!\(\)\{\}\[\]\^"~\?\\;]',
        urlencode=False,
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
            query = Client._truncate_utf8(query, max_len)

        if urlencode:
            query = urllib.parse.quote_plus(str(query), encoding="utf8")

        return query

    async def close(self):
        """Close down Client Session."""
        LOGGER.debug("Closing Solr session connection...")
        if self.session:
            await self.session.close()

    async def commit(self, handler="update", soft=False, **kwargs):
        """Perform a commit on the collection."""
        collection = self._get_collection(kwargs)
        LOGGER.debug(
            "Performing commit to Solr %s collection via %s handler...", collection, handler
        )
        url = f"{self.base_url}/{collection}/{handler}?"
        url += "softCommit=true" if soft is True else "commit=true"
        return await self._get_check_ok_deserialize(url)

    async def dataimport(self, handler="dataimport", **kwargs):
        """Call a DIH (data import handler)."""
        LOGGER.debug("Calling dataimport handler /%s...", handler)
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        url += self._kwargs_to_query_string(kwargs)
        solr_response = await self._get(url)
        return self._deserialize(solr_response)

    async def get(self, _id, handler="get", **kwargs):
        """Use Solr's built-in get handler to retrieve a single document by id."""
        collection = self._get_collection(kwargs)
        LOGGER.debug(
            "Getting document from Solr collection %s via handler %s...", collection, handler
        )
        url = f"{self.base_url}/{collection}/{handler}?id={_id}&wt={self.response_writer}"
        url += self._kwargs_to_query_string(kwargs)
        return await self._get_check_ok_deserialize(url)

    async def ping(self, handler="ping", action="status", **kwargs):
        """Use Solr's ping handler to check status of, enable, or disable a node."""
        assert action.lower() in ("status", "enable", "disable")
        LOGGER.debug("Pinging Solr...")
        collection = self._get_collection(kwargs)
        url = (
            f"{self.base_url}/{collection}/{handler}"
            f"?distrib=false&action={action}&wt={self.response_writer}"
        )
        return await self._get_check_ok_deserialize(url)

    async def setup(self):
        """Setup the ClientSession for use."""
        LOGGER.debug("Creating Solr session connection...")
        self.session = aiohttp.ClientSession(
            connector=self.tcp_conn,
            # connector_owner=False,
            timeout=self.timeout,
            trace_configs=self.trace_configs,
        )

    async def suggestions(self, handler, query=None, build=False, **kwargs):
        """
        Query a RequestHandler of class SearchHandler using the SuggestComponent.

        Returns a tuple of response object and useful data or None if failure.
        """
        if not query and not build:
            return SolrError("query or build required for suggestions.")

        collection = self._get_collection(kwargs)
        LOGGER.debug("Querying Solr collection %s suggestions handler /%s...", collection, handler)

        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        if query:
            url += f"&suggest.q={query}"
        if build:
            url += "&suggest.build=true"

        response = await self._get_check_ok_deserialize(url)
        suggestions = []

        if query:
            if "+" in query:
                query = query.replace("+", " ")

            for name in response.data["suggest"].keys():

                try:
                    suggestions += [
                        {"match": s["term"], "payload": s["payload"]}
                        for s in response.data["suggest"][name][query]["suggestions"]
                    ]
                except KeyError:
                    pass

        return response, suggestions

    async def query(self, *, handler="select", **kwargs):
        """Query a requestHandler of class SearchHandler."""
        LOGGER.debug("Querying Solr %s handler...", handler)
        collection = self._get_collection(kwargs)

        if "q" not in kwargs:
            if "query" not in kwargs:
                kwargs["q"] = "*"
            else:
                kwargs["q"] = kwargs.pop("query")

        if self.response_writer == "json":
            url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"

            if kwargs.get("spellcheck"):
                # Docs state the default SpellingQueryConverter class only handles ASCII so we
                # need to specify spellcheck.q for Unicode support
                # https://lucene.apache.org/solr/guide/8_6/spell-checking.html
                kwargs["spellcheck.q"] = kwargs["q"]
                if "spellcheck_dicts" in kwargs and "spellcheck.dictionary" not in kwargs:
                    kwargs["spellcheck.dictionary"] = kwargs.pop("spellcheck_dicts", [])

            if "prefer_local" in kwargs:
                kwargs.pop("prefer_local")
                url += "&shards.preference=replica.location:local"

            body = self._kwargs_to_json_body(kwargs)

            solr_response = await self._get(url, body=body)
            if solr_response.status != 200:
                msg, trace = None, None
                try:
                    error = self._deserialize(solr_response)
                    msg = error.data.get("error", {}).get("msg", error)
                    trace = error.data.get("error", {}).get("trace")
                except BaseException:  # pylint: disable=broad-except
                    # TODO Figure out all the possible exceptions and catch them instead of Base
                    msg = str(solr_response.body)

                raise SolrError(msg, trace)
        else:
            raise SolrError("Non json responses not yet supported.")

        return self._deserialize(solr_response)

    async def update(self, data, handler="update", **kwargs):
        """Update a document using Solr's update handler."""
        collection = self._get_collection(kwargs)
        LOGGER.debug("Updating %s data in Solr via %s handler...", collection, handler)
        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        url += self._kwargs_to_query_string(kwargs)

        response = await self._post(url, data)
        if response.status == 200:
            data = self._deserialize(response)
        else:
            msg, trace = None, None
            try:
                error = self._deserialize(response)
                msg = error.data.get("error", {}).get("msg", error)
                trace = error.data.get("error", {}).get("trace")
            except BaseException:  # pylint: disable=broad-except
                # TODO Figure out all the possible exceptions and catch them instead of BaseExcept
                msg = str(response.body)

            raise SolrError(msg, trace)

        return data


# Convenience shortcut to clean method
clean_query = Client.clean
