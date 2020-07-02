"""AIOSolr module."""
import json

import aiohttp


class SolrError(Exception):
    pass


# TODO Support something other than JSON
class Solr:
    """Class representing a connection to Solr."""

    def __init__(
        self, scheme="http", host="127.0.0.1", port="80", collection="", timeout=(1, 3)
    ):
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
            self.timeout = aiohttp.ClientTimeout(
                sock_connect=timeout[0], sock_read=timeout[1]
            )
        else:
            self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = aiohttp.ClientSession(timeout=self.timeout)

    def _deserialize(self, response_body):
        """Deserialize Solr response to Python object."""
        # TODO Handle types other than json
        if self.response_writer == "json":
            data = json.loads(response_body)
        else:
            data = response_body
        return data

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
            raise SolrError("%s", response.body)

        return self._deserialize(response.body)

    def _get_collection(self, kwargs):
        """Get the collection name from the kwargs or instance variable."""
        if not kwargs.get("collection") and not self.collection:
            raise SolrError("Collection name not provided.")
        return kwargs.get("collection") or self.collection

    def _kwarg_to_query_string(self, kwargs):
        """Convert kwarg arguments to Solr query string."""
        # TODO Think about if I should validate any query params in kwargs?
        query_string = ""
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
            url += "&suggest.q={query}"
        if build:
            url += "&suggest.build=true"
        data = await self._get_check_ok_deserialize(url)

        if query:
            suggestions = []
            for name in data["suggest"].keys():
                suggestions += [
                    {"match": s["term"], "payload": s["payload"]}
                    for s in data["suggest"][name][query]["suggestions"]
                ]
            return suggestions
        return data

    async def query(self, handler="select", query="*", **kwargs):
        """Query a requestHandler of class SearchHandler."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?q={query}&wt={self.response_writer}"
        url += self._kwarg_to_query_string(kwargs)

        response = await self._get(url)
        if response.status == 200:
            data = self._deserialize(response.body)
        else:
            raise SolrError("%s", response.body)

        return data["response"]["docs"]

    async def update(self, data, handler="update", **kwargs):
        """Update a document using Solr's update handler."""
        collection = self._get_collection(kwargs)
        url = f"{self.base_url}/{collection}/{handler}?wt={self.response_writer}"
        url += self._kwarg_to_query_string(kwargs)

        response = await self._post(url, data)
        if response.status == 200:
            data = self._deserialize(response.body)
        else:
            raise SolrError("%s", response.body)

        return data
