# -*- encoding: utf-8 -*-

"""
Main File to Fetch NSE India Options Chain Data
"""

import yaml

import requests
import datetime as dt

import pandas as pd

from nseoptions import CONFIG


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

        * **nstrikes** (*int*) - The number of strike prices above and
            below the ATM to be fetched from the data. Default is 20.
    """

    def __init__(self, symbol : str, expiry : str | dt.date, **kwargs):
        self.symbol = symbol
        self.expiry = self.__set_expiry__(expiry)

        # ? set the keyword arguments as class attributes
        self.multiple = kwargs.get("multiple", self._multiples.get(symbol, 50))


    @property
    def _multiples(self) -> dict:
        """
        Multiple of the Strike Price for the Given Symbol

        The function returns the multiple of the strike price for the
        given symbol. The multiple is used to calculate the ATM strike
        price and the range of strike prices to be fetched from the
        NSE India website.

        The default multiple is set for the indexes like NIFTY, BANKNIFTY,
        etc. The user can set the multiple for other symbols using the
        `multiple` keyword argument while initializing the class.
        """

        return dict(NIFTYNXT50 = 100, BANKNIFTY = 100, MIDCPNIFTY = 25)


    @property
    def session(self) -> requests.Session:
        """
        Session Object for the NSE Option Chain Data

        The function returns a session object to fetch the data from the
        NSE India website. The session object is used to fetch the data
        from the website using the API URI.

        The session object is created using the `requests` module and
        the headers are set to mimic a browser request to the website.
        """

        return requests.Session().get(
            self.NSE_API_URI, headers = self.URI_HEADER
        )


    @property
    def response(self) -> dict:
        return self.session.json()


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


    def __set_expiry__(self, expiry : str | dt.date) -> str:
        """
        Set the Expiry Date for the Option Chain Data

        The function is used to set the expiry date for the option chain
        data. The expiry date can be a string or a date object. The date
        is converted to a string in the format :attr:`%d-%b-%Y` for the
        NSE India API.

        :type  expiry: str or dt.date
        :param expiry: A valid expiration date of the given symbol. If the
            date is an instance of string the it must be of the date style
            :attr:`%d-%b-%Y` or can be a date.
        """

        return expiry if isinstance(expiry, str) else expiry.strftime("%d-%b-%Y")
    

    def strikerange(self, underlying : float, nstrikes : int = 20) -> tuple:
        """
        Calculate the Range of Strike Prices for the Option Chain

        The option chain consists of a range of strike prices for the
        given symbol. The function calculates the ATM strike price and
        returns relevant strike prices for the analysis, which is often
        the prices nearer to the ATM.

        :type  underlying: float
        :param underlying: The underlying value of the symbol or the
            index for which the option chain data is fetched.
        
        :type  nstrikes: int
        :param nstrikes: The number of strike prices above and below the
            ATM to be fetched from the data. Default is 20.
        """

        # ? calculate atm strike price, and return smaller dataframe
        atm = round(underlying / self.multiple) * self.multiple
        l_strike = atm - nstrikes * self.multiple # lower strike price
        h_strike = atm + nstrikes * self.multiple # higher strike price

        return atm, l_strike, h_strike
    

    def get(self, nstrikes : int = 20, verbose : bool = True) -> pd.DataFrame:
        """
        Get the Option Chain Data Frame for the Given Symbol for Expiry

        The default response from the website is a response consisting
        of details of all the expiry for till far future. The function
        filters the data and returns only the data for the given expiry
        date and the near ATM strike prices.

        :type  nstrikes: int
        :param nstrikes: The number of strike prices above and below the
            ATM to be fetched from the data. Default is 20.

        :type  verbose: bool
        :param verbose: Print the debug and/or other relevant information
            while fetching the data. Default is True.
        """

        self.timestamp = self.response["records"]["timestamp"]
        self.underlying = self.response["records"]["underlyingValue"]

        # expose essential value as class attribute, and
        # also make them available as self.essential dictionary
        self.atm, self.l_strike, self.h_strike = self.strikerange(self.underlying, nstrikes)

        if verbose:
            print(f"{dt.datetime.now()} : Data Fetched for `{self.symbol}`")
            print(f"  >> Underlying Value   : ₹ {self.underlying:,.2f}")
            print(f"  >> Response Timestamp : {self.timestamp}")
            print(f"  >> ATM Strike Price   : ₹ {self.atm:,.2f}")
            print(f"  >> Strike Price Range : ₹ {self.l_strike:,.2f} - ₹ {self.h_strike:,.2f}")
        

        # aggregated values are already available in the API call
        self.tot_oi_ce = self.response["filtered"]["CE"]["totOI"]
        self.tot_oi_pe = self.response["filtered"]["PE"]["totOI"]
        self.global_pcr = self.tot_oi_pe / self.tot_oi_ce

        self.tot_vol_ce = self.response["filtered"]["CE"]["totVol"]
        self.tot_vol_pe = self.response["filtered"]["PE"]["totVol"]

        return self.makeframe()


    @property
    def essentials(self) -> dict:
        """
        Return Important Ratio/Values for the Option Chain Data
        """

        return dict(
            symbol = self.symbol, expiry = self.expiry,
            timestamp = self.response["records"]["timestamp"],
            underlying = self.response["records"]["underlyingValue"],

            # return for atm, strike price range
            atm = self.atm, l_strike = self.l_strike, h_strike = self.h_strike,

            # return for pcr related calculation
            global_pcr = self.global_pcr, tot_oi_ce = self.tot_oi_ce, tot_oi_pe = self.tot_oi_pe,

            # near atm total oi is a quick tool for market analysis, better avoid
            near_oi_ce = self.ce["openInterest"].sum(),
            near_oi_pe = self.pe["openInterest"].sum(),
            near_oi_pcr = self.pe["openInterest"].sum() / self.ce["openInterest"].sum(),

            # return for volume related calculation
            tot_vol_ce = self.tot_vol_ce, tot_vol_pe = self.tot_vol_pe,

            # also return total volume for near atm strike prices
            near_vol_ce = self.ce["totalTradedVolume"].sum(),
            near_vol_pe = self.pe["totalTradedVolume"].sum()
        )


    def makeframe(self) -> pd.DataFrame:
        """
        Make and Process the Data Frame for the Option Chain Data

        :type  nstrikes: int
        :param nstrikes: The number of strike prices above and below the
            ATM to be fetched from the data. Default is 20.
        """

        data = self.response["records"]["data"]

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

        # we will just filter the required data, and then make clean frame
        frame = frame[
            (frame["expiryDate"] == self.expiry)
            & (frame["strikePrice"].between(self.l_strike, self.h_strike))
        ]

        # since we already know the expiry and symbol, we can delete them
        # also identifier is not required as we will not be placing order
        _dropcols = ["expiryDate", "underlying", "identifier", "underlyingValue"]
        frame.drop(columns = _dropcols, inplace = True)

        # also set the raw dataframe as a class attribute, dev usage
        self.frame = frame # chain data as in the raw format

        # now we can safely return the option chain data like in nse
        self.ce = frame[frame["instrumentType"] == "CE"]
        self.pe = frame[frame["instrumentType"] == "PE"]

        opchain = pd.merge(
            self.ce, self.pe, how = "inner", on = "strikePrice",
            suffixes = ("_ce", "_pe")
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

        return opchain[cecols_ + ["strikePrice"] + pecols_]
