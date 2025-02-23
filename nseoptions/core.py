# -*- encoding: utf-8 -*-

"""
Main File to Fetch NSE India Options Chain Data
"""

import yaml

import requests
import datetime as dt

import pandas as pd

from nseoptions import CONFIG

URI_HEADER = {
    "accept-language" : "en-US,en;q=0.9,en-IN;q=0.8",
    "accept-encoding" : "gzip, deflate, br, zstd",
    "user-agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
}

NSE_OPTION_CHAIN_URI = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"


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

        * **multiple** (*int*) - The multiple of the strike price for
            a symbol or an index value. The default value is set for
            the indexes like NIFTY, BANKNIFTY, etc. To set the multiple
            for other symbols set the value, defaults to 50.
    """

    def __init__(self, symbol : str, expiry : str | dt.date, nstrikes : int = 20, **kwargs):
        self.symbol = symbol


    def setconfig(self, file : str = CONFIG, type : str = "index", **kwargs) -> dict:
        """
        Configuration Data for the NSE Option Chain Module

        The default configuration is stored under the `config` folder
        at the base of the module. However, the user can set and update
        any part of the configuration by passing the file path or
        passing the individual values.

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

            * **apiuri** (*str*) - The API URI to fetch the data from
                the NSE India website. The default is set to None.
        """

        header = kwargs.get("header", None)
        apiuri = kwargs.get("apiuri", None)

        # todo: check if file exists, and file is not None
        config = yaml.load(open(file, "r"), Loader = yaml.FullLoader)

        # ? update any part of the configuration if passed by enduser
        config["config"]["header"] = header if header else config["config"]["header"]

        # ! set the global header for the model, will not change on run
        self.URI_HEADER = config["config"]["header"]

        # ! the global url for the model is two part, either use the
        # default or set the new one as given by the end user argument
        configuri = config["config"]["uri"]
        self.NSE_API_URI = apiuri if apiuri else \
            configuri["base"] + configuri["type"][type]

        self.NSE_API_URI = self.NSE_API_URI.format(symbol = self.symbol)

        return config # return everything for debugging, developer usage


def fetchdoc(symbol : str, expiry : str | dt.date, nstrikes : int = 20, **kwargs) -> pd.DataFrame:
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

    # first we filter for the required expiry date, and then
    # we get the total put call ratio for the given expiry, then filter date
    frame = frame[frame["expiryDate"] == expiry]
    tot_oi_ce = frame[frame["instrumentType"] == "CE"]["openInterest"].sum()
    tot_oi_pe = frame[frame["instrumentType"] == "PE"]["openInterest"].sum()
    global_pcr = tot_oi_pe / tot_oi_ce # better to get for the overall

    # also find the total volume traded for the given expiry for ce/pe
    tot_vol_ce = frame[frame["instrumentType"] == "CE"]["totalTradedVolume"].sum()
    tot_vol_pe = frame[frame["instrumentType"] == "PE"]["totalTradedVolume"].sum()

    frame = frame[frame["strikePrice"].between(s, f)]

    # since we already know the expiry and symbol, we can delete them
    # also identifier is not required as we will not be placing order
    frame.drop(columns = ["expiryDate", "underlying", "identifier", "underlyingValue"], inplace = True)

    # now we can safely return the option chain data like in nse
    ce = frame[frame["instrumentType"] == "CE"]
    pe = frame[frame["instrumentType"] == "PE"]

    # near atm strike is also a option for pcr calculation, better avoid
    near_oi_ce = ce["openInterest"].sum()
    near_oi_pe = pe["openInterest"].sum()

    # near atm volume may also be a good indicator for tracking
    near_vol_ce = ce["totalTradedVolume"].sum()
    near_vol_pe = pe["totalTradedVolume"].sum()

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

    # return other important response as a dictionary data
    # this can be written as a value where required in the future
    essentials = dict(
        symbol = symbol, expiry = expiry, timestamp = timestamp,
        underlying = underlying, atm = atm,

        # return for pcr related calculation
        global_pcr = global_pcr, tot_oi_ce = tot_oi_ce, tot_oi_pe = tot_oi_pe,
        near_pcr = near_oi_pe / near_oi_ce, near_oi_ce = near_oi_ce, near_oi_pe = near_oi_pe,

        # return for volume related calculation
        tot_vol_ce = tot_vol_ce, tot_vol_pe = tot_vol_pe,
        near_vol_ce = near_vol_ce, near_vol_pe = near_vol_pe
    )

    return response, frame, opchain, essentials
