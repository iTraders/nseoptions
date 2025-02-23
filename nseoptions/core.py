# -*- encoding: utf-8 -*-

"""
Main File to Fetch NSE India Options Chain Data
"""

import requests
import datetime as dt

import pandas as pd

URI_HEADER = {
    "accept-language" : "en-US,en;q=0.9,en-IN;q=0.8",
    "accept-encoding" : "gzip, deflate, br, zstd",
    "user-agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
}

NSE_OPTION_CHAIN_URI = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"


def fetchdoc(symbol : str, expiry : str | dt.date, nstrikes : int = 20, **kwargs) -> pd.DataFrame:
    """
    Fetch the Option Chain Data for a Symbol and Expiry

    The response from the public API is filtered to only select and
    return the data for the selected symbol (can be either an index or
    a stock symbol) and for a given expiry date.

    :type  symbol: str
    :param symbol: Symbol to fetch the data from NSE India website.
        The symbol should be upper case (or converted internally), as
        available in https://www.nseindia.com/option-chain data.

    :type  expiry: str or dt.date
    :param expiry: A valid expiration date of the given symbol. If the
        date is an instance of string the it must be of the date style
        :attr:`%d-%b-%Y` or can be a date.

    :type  nstrikes: int
    :param nstrikes: Number of strike prices above and below the ATM
        to be fetched from the data. Default is 20.
    
    Keyword Arguments
    -----------------

    The keyword arguments are defined for additional controls, and it
    is recommended to use the default settings (since the module is
    currently under development and the keyword arguments aren't yet
    fully tested).

        * **verbose** (*bool*) - Print the debug and/or other relevant
            information while fetching the data. Default is True.
    """

    expiry = expiry if isinstance(expiry, str) else expiry.strftime("%d-%b-%Y")

    # define session object, and try to fetch the JSON data
    session = requests.Session().get(
        NSE_OPTION_CHAIN_URI.format(symbol = symbol),
        headers = URI_HEADER
    )

    # ? default multiple may change over time, but for now it is fixed
    default_multiple = dict(
        NIFTY = 50,
        BANKNIFTY = 100,
        FINNIFTY = 50,
        NIFTYNXT50 = 100,
        MIDCPNIFTY = 25
    )

    # ? keyword arguments defination and default control settings
    verbose = kwargs.get("verbose", True)
    multiple = kwargs.get(
        "multiple", default_multiple.get(symbol, 50)
    )

    try:
        response = session.json()
        data = response["records"]["data"]
        
        # ..versionadded:: 0.0.1.dev0 - response is stored for debug
        timestamp = response["records"]["timestamp"]
        underlying = response["records"]["underlyingValue"]

        # ? calculate atm strike price, and return smaller dataframe
        atm = round(underlying / multiple) * multiple
        s, f = atm - nstrikes * multiple, atm + nstrikes * multiple

        if verbose:
            print(f"{dt.datetime.now()} : Data Fetched for `{symbol}`")
            print(f"  >> Underlying Value   : ₹ {underlying:,.2f}")
            print(f"  >> Response Timestamp : {timestamp}")
            print(f"  >> ATM Strike Price   : ₹ {atm:,.2f}")
            print(f"  >> Strike Price Range : ₹ {s:,.2f} - ₹ {f:,.2f}")

    except Exception as e:
        print(f"{dt.datetime.now()} : Failed to Fetch Data::\n\t{e}")

    ocdata = []
    for item in data:
        for instrument, info in item.items():
            if instrument in ["CE", "PE"]:
                dump = info # current line item dump
                dump["instrumentType"] = instrument # CE/PE tag level
                ocdata.append(dump)
            else:
                pass
    
    frame = pd.DataFrame(ocdata) # all the data are in the dataframe
    frame = frame[
        (frame["expiryDate"] == expiry) &
        (frame["strikePrice"].between(s, f))
    ]

    # since we already know the expiry and symbol, we can delete them
    # also identifier is not required as we will not be placing order
    frame.drop(columns = ["expiryDate", "underlying", "identifier", "underlyingValue"], inplace = True)

    # now we can safely return the option chain data like in nse
    ce = frame[frame["instrumentType"] == "CE"]
    pe = frame[frame["instrumentType"] == "PE"]

    opchain = pd.merge(
        ce, pe, how = "inner", on = "strikePrice", suffixes = ("_ce", "_pe")
    )

    opchain.drop(columns = ["instrumentType_ce", "instrumentType_pe"], inplace = True)

    # mimic and return the columns as in the nse option chain
    columns = [
        "openInterest", "changeinOpenInterest", "pchangeinOpenInterest",
        "totalTradedVolume", "impliedVolatility", "lastPrice", "change", "pChange",
        "totalBuyQuantity", "totalSellQuantity", "bidQty", "bidprice", "askQty", "askPrice"
    ]

    cecols_ = [f"{col}_ce" for col in columns]
    pecols_ = [f"{col}_pe" for col in columns][::-1]
    opchain = opchain[cecols_ + ["strikePrice"] + pecols_]

    return response, frame, opchain, timestamp, underlying, atm
