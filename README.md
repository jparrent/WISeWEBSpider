## WISeWEBSpider version 0.3
Original Authors: Jerod Parrent, James Guillochon

###Description
`wisewebspider` is a simple program built to scrape and download all publicly available supernova spectra from the [Weizmann Interactive Supernova data REPository (WISeREP)](http://wiserep.weizmann.ac.il); a bulk download option is not available through WISeREP and the number of supernova spectra to download are in the 10,000s. The script creates two main directories, `sne-external-WISEREP/` and `sne-internal/`. Within `sne-external-WISEREP/`, spectra are stored in individual subdirectories alongside `README.json` files. The README files detail event metadata for each spectrum collected. Stored in `sne-internal/` are log files and pickles to keep track of the scripts progress, as well as non-supernova events to save time. 

The script guards against spectra already collected, duplicate files found on WISeREP, and events that are not supernovae. However, no effort has been made to collate spectra for objects with multiple aliases (e.g., SN2011fe and PTF11kly, both the same event, have separate directories), nor does the script determine supernova types for objects that are unspecified on WISeREP.

Without excluding by event type and/or survey program (UCB, CfA, SuSpect, etc), the full runtime for scraping everything is about 18.7 hours. Fortunately this need only be done once. After an initial scrape, the script can be run in update mode, which at most takes a few minutes.

###Usage
For the initial scrape, check/edit exlcluded lists in main.py, then run:
```
python3.5 -m wisewebspider
```

To run in update mode:
```
python3.5 -m wisewebspider --update --daysago 30
```
where the value after `daysago` can be 1, 2, 7, 14, 30, 180, or 365, i.e., how many days since last you scraped.

### Dependencies and Credits

* [RoboBrowser](https://github.com/jmcarp/robobrowser)
* Thank you to Ryan Mitchell, author of [Web Scraping with Python](http://pythonscraping.com/node/5)
