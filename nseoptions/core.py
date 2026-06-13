# -*- encoding: utf-8 -*-

"""
Main File to Fetch NSE India Options Chain Data

The core module exposes :class:`NSEOptionChain` which discovers the
valid contract expiry dates and fetches the option chain payload for
a traded symbol (index/stock) from the NSE India public API.

:NOTE: As on 2026-06-12 the NSE decommissioned the legacy
    ``option-chain-indices``/``option-chain-equities`` endpoints (now
    HTTP 404) and the module is migrated to the ``option-chain-v3``
    API which mandates an expiry date per request. Valid expiries are
    discovered via :meth:`NSEOptionChain.expiries` and set using
    :meth:`NSEOptionChain.setexpiry` before fetching the chain.
"""

import json
import time
import datetime as dt

import yaml
import requests

from tqdm import tqdm as TQ

from nseoptions import CONFIG
from nseoptions.processing import normalizeexpiry

# ! hard cap on the (decompressed) response body the client will buffer -
# option chain payloads are well under a few MB; this bounds the memory and
# disk damage from a hostile or oversized response (e.g. a decompression bomb)
MAX_RESPONSE_BYTES = 25 * 1024 * 1024


class NSEOptionChain:
    """
    National Stock Exchange (NSE) Option Chain Data Extraction Module

    The NSE Option Chain is a free to use data source to analyze the
    Indian option chain for various symbols. The details of usage and
    terms and condition are available at the NSE India website.

    The core function aims to fetch the data for a particular symbol
    or an index for a said expiration date. In addition, the module
    returns only relevant (near ATM) strike prices for the analysis.

    :type  symbol: str
    :param symbol: Symbol to fetch the data from NSE India website.
        The symbol should be upper case (or converted internally), as
        available in https://www.nseindia.com/option-chain data.

    :type  expiry: str or dt.date
    :param expiry: A valid expiration date of the given symbol. If the
        date is an instance of string the it must be of the date style
        :attr:`%d-%b-%Y` or can be a date. The value is optional at
        initialization and can be set (or rolled over) at any time
        using :meth:`setexpiry`, while the valid dates for the symbol
        are discovered using :meth:`expiries`. Defaults to None.

    Keyword Arguments
    -----------------

    The keyword arguments are defined for additional controls, and it
    is recommended to use the default settings (since the module is
    currently under development and the keyword arguments aren't yet
    fully tested).

        * **verbose** (*bool*) - Print the debug and/or other relevant
          information while fetching the data. Default is True.

        * **multiple** (*int*) - The multiple of the strike price for
          a symbol or an index value. The default value is set for the
          indexes like NIFTY, BANKNIFTY, etc. To set the multiple for
          other symbols set the value, defaults to 50.

        * **nstrikes** (*int*) - The number of strike prices above and
          below the ATM to be fetched from the data. Default is 20.

        * **verify** (*bool*) - SSL certificate validation to get the
          data from the internet. Always recommended to be True, but
          in case of legacy/restricted systems this option comes in
          handy. Defaults to True (verification on); pass ``verify =
          False`` only on a trusted or SSL-intercepting network.

        * **timeout** (*int*) - Per-request timeout (in seconds) for
          every GET call to the NSE India website, since the website
          may hang indefinitely on blocked requests. Defaults to 15.
    """

    # ..versionchanged:: 2026-06-12 Migrate to NSE v3 Option Chain API
    def __init__(
        self, symbol : str, expiry : str | dt.date | None = None, **kwargs
    ) -> None:
        self.symbol = symbol.upper()

        # ? expiry is optional at init, can be set later via `setexpiry()`
        self.expiry = normalizeexpiry(expiry) if expiry else None

        # keyword arguments parsed from cli/object initialization
        self.verify = kwargs.get("verify", True)
        self.timeout = kwargs.get("timeout", 15)

        # ? session is created lazily by `__newsession__()` on first fetch
        self.session = None


    # ..versionchanged:: 2026-06-12 Warmed Session, Timeout and Capped Retries
    def response(self, waittime : int = 10, maxretries : int = 30) -> dict:
        """
        Fetch the Option Chain JSON Payload from the NSE v3 API

        The function fetches the option chain data for the configured
        symbol and expiry from the NSE India website using a warmed-up
        persistent session (see :meth:`__newsession__`). On any failure
        the session is discarded (to force a fresh cookie warm-up) and
        the request is retried after a countdown of ``waittime``
        seconds, for a maximum of ``maxretries`` attempts. With the
        defaults of :mod:`main` (``waittime = 20``) the retry budget
        tolerates roughly a 10 minute NSE outage before giving up.

        :type  waittime: int
        :param waittime: Number of seconds to sleep (with a visual
            ``tqdm`` countdown) between two consecutive retries when
            the fetch fails. Defaults to 10.

        :type  maxretries: int
        :param maxretries: Maximum number of fetch attempts before the
            function gives up and raises an error. Defaults to 30.

        :raises ValueError: If the expiry is not yet set for the
            object, i.e., :meth:`setexpiry` was never called and no
            expiry was passed during initialization.
        :raises ConnectionError: If the data could not be fetched even
            after ``maxretries`` attempts.

        :rtype:  dict
        :return: The raw v3 option chain payload, with the top level
            keys ``records`` and ``filtered`` as returned by the API.
        """

        if self.expiry is None or not hasattr(self, "NSE_API_URI"):
            raise ValueError("expiry not set - call setexpiry() before response()")

        for count in range(1, maxretries + 1):
            try:
                if self.session is None:
                    self.__newsession__()

                # ? verify/timeout are passed per request, not on the session
                session_response = self.session.get(
                    self.NSE_API_URI,
                    headers = self.URI_HEADER,
                    timeout = self.timeout,
                    verify = self.verify,
                    allow_redirects = False,
                    stream = True
                )
                session_response.raise_for_status()
                response = self.__readcapped__(session_response)

                # ? validate the shape, not merely key presence - under a
                # bypassed-TLS MITM the payload is otherwise trusted as-is
                valid = (
                    isinstance(response, dict)
                    and isinstance(response.get("records"), dict)
                    and isinstance(response.get("filtered"), dict)
                )
                if not valid:
                    raise ValueError("malformed v3 response, missing records/filtered")

                return response
            except KeyboardInterrupt:
                raise # ? allow a clean ctrl+c exit mid-fetch, no retry
            except Exception as e:
                self.session = None # ! forces cookie re-warm on next attempt
                print(f"{time.ctime()} : Failed to Fetch Data - {e}")

                # ! on the last attempt, chain the cause and skip the wait
                if count == maxretries:
                    raise ConnectionError(
                        f"NSE v3 fetch failed after {maxretries} attempts"
                    ) from e

                _ = [
                    time.sleep(1)
                    for _ in TQ(range(waittime), desc = f"#{count} Retrying...")
                ]

        raise ConnectionError(f"NSE v3 fetch failed after {maxretries} attempts")


    # ..versionchanged:: 2026-06-12 Migrate to NSE v3 Option Chain API
    def setconfig(self, file : str = CONFIG, type : str = "index", **kwargs) -> dict:
        """
        Configuration Data for the NSE Option Chain Module

        The default configuration is stored under the `config` folder
        at the base of the module. However, the user can set and update
        any part of the configuration by passing the file path or
        passing the individual values.

        The chain endpoint is the NSE v3 template which carries both a
        ``{symbol}`` and an ``{expiry}`` placeholder - the template is
        stored unformatted and is resolved into the final API URI by
        :meth:`setexpiry` (or immediately, if the expiry is already
        known at the time of configuration).

        :type  file: str
        :param file: The file path to the configuration file. The file
            should be a YAML file with the required configuration.

        :type  type: str
        :param type: The type of the configuration to be fetched. The
            default is `index` for the index options chain data. The
            other option is `stock` for the stock options chain data.

        Keyword Arguments
        -----------------

        The keyword arguments are defined to update a part of the
        configuration value. For example, if an end user wants to only
        change the header value, then the user can pass the header which
        will overwrite the default header section with the new value.

            * **header** (*dict*) - The header information to be passed
                while fetching the data from the NSE India website.

            * **apiuri** (*str*) - The API URI template to fetch the
                data from the NSE India website, with the ``{symbol}``
                and ``{expiry}`` placeholders. The default is set to
                None, i.e., use the template from the configuration.

        :rtype:  dict
        :return: The full parsed configuration, for debugging and
            developer usage.
        """

        # ? `type` shadows the builtin but is kept for backward compatibility
        header = kwargs.get("header", None)
        apiuri = kwargs.get("apiuri", None)

        # todo: check if file exists, and file is not None
        with open(file, "r") as f:
            config = yaml.safe_load(f)

        # ? update any part of the configuration if passed by enduser
        config["config"]["header"] = header if header else config["config"]["header"]

        # ! set the global header for the model, will not change on run
        self.URI_HEADER = config["config"]["header"]

        configuri = config["config"]["uri"]

        # ? cookie warm-up page and expiry discovery endpoint for symbol
        self.NSE_WARMUP_URI = configuri.get(
            "warmup", "https://www.nseindia.com/option-chain"
        )
        self.NSE_CONTRACT_URI = (configuri["base"] + configuri["contract"]).format(
            symbol = self.symbol
        )

        # ! the chain template is stored unformatted since the v3 api
        # mandates an expiry per request, resolved via `setexpiry()`
        self._apiuri = apiuri if apiuri else \
            configuri["base"] + configuri["type"][type]

        if self.expiry:
            self.NSE_API_URI = self._apiuri.format(
                symbol = self.symbol, expiry = self.expiry
            )

        return config # return everything for debugging, developer usage


    def setexpiry(self, expiry : str | dt.date) -> str:
        """
        Set or Update the Contract Expiry Date for the Option Chain

        The NSE v3 option chain API mandates an expiry date for each
        request, hence the expiry can be set (or updated, for example
        to roll over to the next contract) any time after the object
        creation. Valid dates for the symbol can be discovered using
        :meth:`expiries`, and the final API URI is (re)built from the
        unformatted template stored by :meth:`setconfig`.

        :type  expiry: str or dt.date
        :param expiry: A valid expiration date of the given symbol. If
            the date is an instance of string then it must be of the
            date style :attr:`%d-%b-%Y` (example ``16-Jun-2026``), or
            can be a date or datetime instance.

        :raises ValueError: If the expiry string does not conform to
            the expected :attr:`%d-%b-%Y` format, as raised by the
            :func:`nseoptions.processing.normalizeexpiry` function.

        :rtype:  str
        :return: The canonical expiry string, i.e., zero-padded day
            and title-case month, exactly as reported by the NSE API.
        """

        self.expiry = normalizeexpiry(expiry)

        # ? lazily load the default configuration if not already set
        if not hasattr(self, "_apiuri"):
            self.setconfig()

        self.NSE_API_URI = self._apiuri.format(
            symbol = self.symbol, expiry = self.expiry
        )

        return self.expiry


    def expiries(self) -> list[str]:
        """
        Discover the Available Contract Expiry Dates for the Symbol

        The list of valid expiry dates for the configured symbol is
        fetched from the NSE ``option-chain-contract-info`` endpoint,
        which exposes the top level keys ``expiryDates`` and
        ``strikePrice``. On the first failure the session is discarded
        and re-warmed (see :meth:`__newsession__`) and the request is
        retried once, while a second consecutive failure is propagated
        to the caller.

        :raises Exception: The underlying :mod:`requests` exception,
            HTTP error, or JSON decoding error is propagated if the
            discovery fails even after a retry with a fresh session.

        :rtype:  list
        :return: List of expiry date strings (:attr:`%d-%b-%Y` format,
            example ``16-Jun-2026``) as reported by the NSE India API.
        """

        # ? lazily load the default configuration if not already set
        if not hasattr(self, "NSE_CONTRACT_URI"):
            self.setconfig()

        for attempt in range(2):
            try:
                if self.session is None:
                    self.__newsession__()

                # ? verify/timeout are passed per request, not on the session
                response = self.session.get(
                    self.NSE_CONTRACT_URI,
                    timeout = self.timeout,
                    verify = self.verify,
                    allow_redirects = False,
                    stream = True
                )
                response.raise_for_status()
                return self.__readcapped__(response)["expiryDates"]
            except Exception:
                if attempt: # ? second consecutive failure is propagated
                    raise

                # ! discard the stale/blocked session so the next iteration
                # re-warms it inside the try, retrying a warm-up failure too
                self.session = None


    def __readcapped__(self, session_response : requests.Response) -> dict:
        """
        Stream and JSON-Decode a Response Body Under a Hard Size Cap

        The response is consumed incrementally (with transfer/content
        decoding applied) and the running total is checked against
        :data:`MAX_RESPONSE_BYTES`, so an oversized or maliciously
        compressed payload is rejected before it is fully buffered,
        parsed, or persisted by a caller.

        :type  session_response: requests.Response
        :param session_response: A streaming response (``stream = True``)
            whose body is to be read and JSON-decoded.

        :raises ValueError: If the decoded body exceeds
            :data:`MAX_RESPONSE_BYTES`.

        :rtype:  dict
        :return: The JSON-decoded response body.
        """

        chunks, total = [], 0
        for chunk in session_response.iter_content(chunk_size = 65536):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError(
                    f"response body exceeds the {MAX_RESPONSE_BYTES} byte cap"
                )

            chunks.append(chunk)

        return json.loads(b"".join(chunks))


    def __newsession__(self) -> None:
        """
        Create a New Warmed-Up Session for the NSE India Website

        The NSE India website is protected by akamai bot protection and
        the API endpoints respond only when the request carries cookies
        (``_abck``, ``bm_sz``, ``nsit``, etc.) set by a regular page
        visit. The method creates a fresh :class:`requests.Session`
        with the configured browser-like headers and performs a warm-up
        GET on the option chain page to collect the cookies. Exceptions
        are deliberately not handled here and bubble up to the retry
        handler of the calling method.
        """

        session = requests.Session()
        session.headers.update(self.URI_HEADER)

        # ? verify/timeout are passed per request, not on the session
        session.get(
            self.NSE_WARMUP_URI, timeout = self.timeout, verify = self.verify
        )

        self.session = session
