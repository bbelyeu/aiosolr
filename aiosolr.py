"""AIOSolr module."""
import asyncio
import json

import aiohttp


class SolrError(Exception):
    pass


# TODO Support something other than JSON
class Solr():
    """Class representing a connection to Solr."""

    def __init__(self, scheme="http", host="127.0.0.1", port="80", collection="", timeout=(1, 3)):
        """Init to instantiate Solr class.

        If the core/collection is not provided it should be passed to the methods as required.
        """
        self.base_url = f"{scheme}://{host}:{port}/solr"
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
        self.session = aiohttp.ClientSession(timeout=self.timeout)

    def __del__(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.session.close())

    def _get_collection(self, kwargs):
        """Get the collection name from the kwargs or instance variable."""
        if not kwargs.get("collection") and not self.collection:
            raise SolrError("Collection name not provided.")
        return kwargs.get("collection") or self.collection

    async def get(self, url):
        """Network request to get data from a server."""
        async with self.session.get(url) as response:
            response.body = await response.text()
        return response

    async def suggestions(self, handler, query, **kwargs):
        """Query a requestHandler of class SearchHandler using the SuggestComponent."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?suggest.q={query}&wt={self.response_writer}"
        response = await self.get(url)

        if response.status == 200:
            data = json.loads(response.body)
            terms = []
            for name in data["suggest"].keys():
                terms += [s["term"] for s in data["suggest"][name][query]["suggestions"]]
            return terms
        else:
            raise SolrError("%s", response.body)

    async def query(self, handler, query='*', **kwargs):
        """Query a requestHandler of class SearchHandler."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?q={query}&wt={self.response_writer}"
        # TODO Think about if I should validate any query params in kwargs?
        for param, value in kwargs.items():
            if isinstance(value, list):
                url += "&{}={}".format(param, ','.join(value))
            else:
                url += f"&{param}={value}"
        response = await self.get(url)
        if response.status == 200:
            data = json.loads(response.body)
            return data["response"]["docs"]
        else:
            raise SolrError("%s", response.body)
