<h1 align = "center">NSE Option Chain</h1>

<div align = "center">

![GitHub Stars](https://img.shields.io/github/stars/iTraders/nseoptions?style=plastic)
![GitHub Forks](https://img.shields.io/github/forks/iTraders/nseoptions?style=plastic)
![GitHub Issues](https://img.shields.io/github/issues/iTraders/nseoptions?style=plastic)
![UNLICENSE File](https://img.shields.io/github/license/iTraders/nseoptions?style=plastic)

</div>

<div align = "justify">

The python library is designed to fetch the Option Chain data available in the [NSE India](https://www.nseindia.com/option-chain)
website. Please refer to the Terms and Conditions and Usages Policies of NSE India.

## Getting Started

[NSE India Option Chain](https://www.nseindia.com/option-chain) is a free to use data that tracks prices for the expiry of any
boarder index (like `NIFTY`, `BANKNIFTY`, etc.) and also option chain information of any stock available for trading in the
exchanges (NSE/BSE). The module uses the NSE India API that returns the data as a JSON object and transforms (cleaning, analysis)
the data to be represented as a table (dataframe) or dump the data into an MS Excel file.

```python
pip install nseoptions # yet to be published

import nseoptions
import datetime as dt

response, data, metrics = nseoptions.core.NSEOptionChain(symbol = "NIFTY", expiry = dt.date(2027, 2, 27))
data.sample(3)
```

We recommend that you store the JSON response as is in a MongoDB like NoSQL database, and you can also store the parsed
dataframe into a simple SQL database.

</div>

> [!NOTE]
> MS Excel associated with the project is a premium version [more details](#). Please request for the MS Excel file [here](#).

---

<div align = "center">

![UNLICENSE File](https://img.shields.io/github/license/iTraders/nseoptions?style=plastic)
[![DISCLAIMER File](https://img.shields.io/badge/⚠-DISCLAIMER-yellow?style=plastic)](https://github.com/iTraders/nseoptions/blob/master/DISCLAIMER.md)

</div>

<div align = "justify">

The code is provided 'as is' and is intended solely for informational purposes. The developers of this project disclaim any
responsibility for any profit or loss incurred as a result of using this code.

</div>
