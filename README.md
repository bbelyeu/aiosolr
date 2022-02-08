# aiosolr

AsyncIO Python client for Apache Solr

## Requirements

This project requires Python 3.6+

## Installation

To install with pip

    pip install aiosolr

## Usage

The connection to the Solr backend is defined during object initialization. The accepted kwargs
to init are *scheme*, *host*, *port*, *collection*, and *timeout*.

*Note: collection may also be passed at query time*

    import aiosolr

    client = aiosolr.Client(host=localhost, collection="example", port=8983)

Alternatively you may instantiate via passing a connection URL like:

    import aiosolr

    client = aiosolr.Client(connection_url="http://host:1234/path/to/solr/collection")

Once you have your *Solr* instance, you need to setup the session like:

    client.setup()

Then there are methods available for querying.
You can use Solr's built-in get handler with the *get* method like:

    client.get(document_id)

to retrieve a single document.

You can use a pre-defined suggestions handler by using the *suggestions* method like:

    client.suggestions("suggest_handler", query="asdf")

You can also use the suggestions method to build your suggestions like:

    client.suggestions("suggest_handler", build=True)

*Note: handler is a required argument for suggestions unlike for get or query*

You can use the *query* method to query your search handler. The default handler used is "select".
If you would like spellcheck suggestion turned on, pass *spellcheck=True* (default is False).

    client.query(handler="my_handler", query="asdf", spellcheck=True)

If *spellcheck* is *True* the query method returns a tuple with the first element being
an array of documents and the 2nd element being an array of spellcheck suggestions.
Otherwise, the query method returns a simple array of documents.

You can use the *update* method to access Solr's built-in update handler like:

    client.update(my_data)

At any point that you need to commit data to your collection you can use the *commit* method.
Arguments should be the "handler" ("update" by default) and "soft" as a boolean indicating
whether it should be a hard or soft commit (defaults to False).

There is one more method you might want to use before querying Solr especially
if the query is coming from an untrusted end user. There is a *clean_query* method which can be
used to strip out unwanted characters. The function signature allows the following arguments:

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
        urlencode=True,
    ):

Use it like:

    trusted_query = aiosolr.clean_query(users_query)

Once you are finished with the Solr instance, you should call the method *close* to cleanup
sessions like:

    await client.close()

## Debugging

To get more information from the Client you can initialize with `debug=True` like:

    import aiosolr

    client = aiosolr.Client(host=localhost, collection="example", port=8983, debug=True)

This sets the `aiosolr` logger to debug level, and also sets the internally used HTTP session
(provied by [AIOHTTP](https://docs.aiohttp.org/en/stable/logging.html)) to a debug level.

This makes it easier to see the actual network request going to Solr.
