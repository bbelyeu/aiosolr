"""AIOSolr module."""

import json

import aiohttp


class SolrError(Exception):
    pass


# TODO Support something other than JSON
class Solr():
    """Class representing a connection to Solr."""

    def __init__(self, scheme="http", host="127.0.0.1", port="80", collection=""):
        """Init to instantiate Solr class.

        If the core/collection is not provided it should be passed to the methods as required.
        """
        self.base_url = f"{scheme}://{host}:{port}/solr/{collection}"
        if self.base_url[-1:] != "/":
            self.base_url += "/"

    async def get(self, url):
        """Network request to get data from a server."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.body = await response.text()
                return response

    async def suggestions(self, handler, query, collection="", **kwargs):
        """Query a requestHandler of class SearchHandler using the SuggestComponent."""
        url = f"{self.base_url}{collection}/{handler}?suggest.q={query}&wt=json"
        response = await self.get(url)
        if response.status == 200:
            data = json.loads(response.body)
            terms = []
            for name in data["suggest"].keys():
                terms += [s["term"] for s in data["suggest"][name][query]["suggestions"]]
            return terms
        else:
            raise SolrError("%s", response.body)

    async def query(self, handler, query, collection="", **kwargs):
        """Query a requestHandler of class SearchHandler."""
        url = f"{self.base_url}{collection}/{handler}?q={query}&wt=json"
        # TODO Think about if I should validate any query params in kwargs?
        for param, value in kwargs.items():
            url += f"&{param}={value}"
        response = await self.get(url)
        if response.status == 200:
            data = json.loads(response.body)
            return data["response"]["docs"]
        else:
            raise SolrError("%s", response.body)
