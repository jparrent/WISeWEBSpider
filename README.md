## WISeREP-Spider version 0.1
Original Author: Jerod Parrent

###Description
`wiserep-spider.py` is a simple program built to scrape and download all publicly available supernova spectra from the [Weizmann Interactive Supernova data REPository (WISeREP)](http://wiserep.weizmann.ac.il); a bulk download option is not available through WISeREP and the number of supernova spectra to download are in the 10,000s. The script creates two main directories, `sne-external-WISEREP/` and `sne-internal/`. Within `sne-external-WISEREP/`, spectra are stored in individual subdirectories alongside `README.txt` files. The README files detail event metadata for each spectrum collected. Stored in `sne-internal/` are log files and pickles to keep track of the scripts progress, as well as non-supernova events to save time. 

The script guards against spectra already collected, duplicate files found on WISeREP, and events that are not supernovae. However, no effort has been made to collate spectra for objects with multiple aliases (e.g., SN2011fe and PTF11kly, both the same event, have separate directories).

Without excluding by event type and/or survey program (UCB, CfA, SuSpect, etc), the full runtime for scraping everything is about 18.7 hours. Fortunately this need only be done once.

###Usage
```
python wiserep-spider.py
```

###Future Versions
* refactor code to be object-oriented and modular via items.py, pipelines.py, settings.py, wiserep-spider.py
* add ``update'' feature to update a directory when either new spectra have been uploaded to WISeREP, or private spectra have been made public 

### Dependencies and Credits

* [Mechanize](http://wwwsearch.sourceforge.net/mechanize/)
* [Beautiful Soup 4](https://www.crummy.com/software/BeautifulSoup/)
* Thank you to Ryan Mitchell, author of [Web Scraping with Python](http://pythonscraping.com/node/5)
