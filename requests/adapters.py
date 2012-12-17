# -*- coding: utf-8 -*-

"""
requests.adapters
~~~~~~~~~~~~~~~~~

This module contains the transport adapters that Requests uses to define
and maintain connections.
"""
import os
from .models import Response
from .packages.urllib3.poolmanager import PoolManager
from .utils import DEFAULT_CA_BUNDLE_PATH, get_encoding_from_headers

import socket
from .structures import CaseInsensitiveDict
from .packages.urllib3.exceptions import MaxRetryError, LocationParseError
from .packages.urllib3.exceptions import TimeoutError
from .packages.urllib3.exceptions import SSLError as _SSLError
from .packages.urllib3.exceptions import HTTPError as _HTTPError
from .packages.urllib3 import connectionpool, poolmanager
from .packages.urllib3.filepost import encode_multipart_formdata
from .exceptions import (
ConnectionError, HTTPError, RequestException, Timeout, TooManyRedirects,
URLRequired, SSLError, MissingSchema, InvalidSchema, InvalidURL)

DEFAULT_POOLSIZE = 10
DEFAULT_RETRIES = 0


class BaseAdapter(object):
    """The Base Transport Adapter"""

    def __init__(self):
        super(BaseAdapter, self).__init__()

    def send(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class HTTPAdapter(BaseAdapter):
    """Built-In HTTP Adapter for Urllib3."""
    def __init__(self, pool_connections=DEFAULT_POOLSIZE, pool_maxsize=DEFAULT_POOLSIZE):
        self.max_retries = DEFAULT_RETRIES
        self.config = {}

        super(HTTPAdapter, self).__init__()

        self.init_poolmanager(pool_connections, pool_maxsize)

    def init_poolmanager(self, connections, maxsize):
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize)

    def cert_verify(self, conn, url, verify, cert):
        if url.startswith('https') and verify:

            cert_loc = None

            # Allow self-specified cert location.
            if verify is not True:
                cert_loc = self.verify

            # Look for configuration.
            if not cert_loc and self.config.get('trust_env'):
                cert_loc = os.environ.get('REQUESTS_CA_BUNDLE')

            # Curl compatibility.
            if not cert_loc and self.config.get('trust_env'):
                cert_loc = os.environ.get('CURL_CA_BUNDLE')

            if not cert_loc:
                cert_loc = DEFAULT_CA_BUNDLE_PATH

            if not cert_loc:
                raise Exception("Could not find a suitable SSL CA certificate bundle.")

            conn.cert_reqs = 'CERT_REQUIRED'
            conn.ca_certs = cert_loc
        else:
            conn.cert_reqs = 'CERT_NONE'
            conn.ca_certs = None

        if cert:
            if len(cert) == 2:
                conn.cert_file = cert[0]
                conn.key_file = cert[1]
            else:
                conn.cert_file = cert

    @staticmethod
    def build_response(req, resp):
        response = Response()

        # Fallback to None if there's no status_code, for whatever reason.
        response.status_code = getattr(resp, 'status', None)

        # Make headers case-insensitive.
        response.headers = CaseInsensitiveDict(getattr(resp, 'headers', {}))

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        return response
        # Add new cookies from the server.
        # extract_cookies_to_jar(self.cookies, self, resp)



    def close(self):
        """Dispose of any internal state.

        Currently, this just closes the PoolManager, which closes pooled
        connections.
        """
        self.poolmanager.clear()

    def send(self, request, prefetch=True, timeout=None, verify=True, cert=None):
        """Sends PreparedRequest object. Returns Response object."""

        conn = self.poolmanager.connection_from_url(request.url)
        self.cert_verify(conn, request.url, verify, cert)

        try:
            # Send the request.
            resp = conn.urlopen(
                method=request.method,
                url=request.path_url,
                body=request.body,
                headers=request.headers,
                redirect=False,
                assert_same_host=False,
                preload_content=False,
                decode_content=False,
                retries=self.max_retries,
                timeout=timeout,
            )

        except socket.error as sockerr:
            raise ConnectionError(sockerr)

        except MaxRetryError as e:
            raise ConnectionError(e)

        except (_SSLError, _HTTPError) as e:
            if isinstance(e, _SSLError):
                raise SSLError(e)
            elif isinstance(e, TimeoutError):
                raise Timeout(e)
            else:
                raise Timeout('Request timed out.')

        r = self.build_response(request, resp)

        if prefetch:
            r.content

        return r






