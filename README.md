# aiosolr

AsyncIO Python client for Apache Solr

## Requirements

This project requires Python 3.7+

## Installation

To install with pip

    pip install aiosolr

## Usage

The connection to the Solr backend is defined during object initialization. The accepted kwargs to
init are `scheme`, `host`, `port`, and `collection`.

> `collection` may optionally be passed at query time

```python
import aiosolr

client = aiosolr.Client(host=localhost, collection="example", port=8983)
```

Alternatively you may instantiate via passing `connection_url` like:

```python
import aiosolr

client = aiosolr.Client(connection_url="http://host:1234/path/to/solr/collection")
```

Once you have your `aiosolr.Client` instance, set up the session:

```python
await client.setup()
```

There are methods available for querying. You can use Solr's built-in get handler with the `get`
method to retrieve a single document:

```python
await client.get(document_id)
```

You can use a pre-defined suggestions handler by using the `suggestions` method:

```python
await client.suggestions("suggest_handler", query="asdf")
```

You can also use the `suggestions` method to build your suggestions:

```python
await client.suggestions("suggest_handler", build=True)
```

> `handler` is a required argument for suggestions unlike for get or query

You can use the `query` method to query your search handler. The default `handler` used is `select`.
If you would like spellcheck suggestion turned on, pass `spellcheck=True` (default is `False`).

```python
await client.query(handler="my_handler", query="asdf", spellcheck=True)
```

If `spellcheck` is `True` the query method returns a tuple with the first element being an array of
documents and the 2nd element being an array of spellcheck suggestions. Otherwise, the query method
returns a simple array of documents.

You can use the `update` method to access Solr's built-in update handler like:

```python
await client.update(my_data)
```

At any point that you need to commit data to your collection you can use the `commit` method.
Arguments should be the `handler` (`update` by default) and `soft` as a boolean indicating whether
it should be a hard or soft commit (defaults to `False`).

There is one more method you might want to use before querying Solr especially if the query is
coming from an untrusted end user. There is a `clean_query` method which can be used to strip out
unwanted characters. Use it like:

```python
trusted_query = aiosolr.clean_query(users_query)
```

Once you are finished with the Solr instance, you should call the method `close` to cleanup sessions
like:

```python
await client.close()
```

### Timeouts

You can initialize the client with `read_timeout` and `write_timeout` to limit how long to wait for
requests to complete. `read_timeout` applies to `get` and `query` whereas `write_timeout` applies to
`update`:

```python
import aiosolr

client = aiosolr.Client(connection_url=connection_url, read_timeout=5, write_timeout=30)
```

You can override the timeouts for a specific request:

```python
await client.get(document_id, read_timeout=1)  # I'm in a hurry
await client.update(doc, write_timeout=60)  # this is a large request so we expect it to take a long time
```

> `aiosolr` uses
> [`asyncio.wait_for`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for)
> internally, so if a timeout occurs the exception raised is `asyncio.TimeoutError`.

## Debugging

To get more information from the Client you can initialize with `debug=True`:

```python
    import aiosolr

    client = aiosolr.Client(host=localhost, collection="example", port=8983, debug=True)
```

This sets the `aiosolr` logger to `DEBUG` level, and also sets the internally used HTTP session
(provided by [aiohttp](https://docs.aiohttp.org/en/stable/logging.html)) to the `DEBUG` level. This
makes it easier to see the actual network requests going to Solr.
