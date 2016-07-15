#!/usr/bin/python

"""
===============================================================================
title           :wiseweb-spider.py
description     :Scrapes and downloads all publicly availabe spectra from
                 WISeREP.
author          :Jerod Parrent
date            :2016-07-06
version         :0.1
usage           :python wiserep-spider.py
notes           :runtime with pages saved and no exlusions = 18.7 hours
python_version  :2.7.12
===============================================================================

TO-DO, refactor to:
items.py
pipelines.py
settings.py
wiseweb-spider.py

and functions:
getObjHeader(), etc

and Python3
"""

import argparse
import json  # pickle
import os
import re
import time
import unicodedata
from collections import OrderedDict
from copy import deepcopy
from http.cookiejar import CookieJar
from urllib.parse import quote
from urllib.request import Request, urlopen

import mechanicalsoup
import requests
from bs4 import BeautifulSoup

# reload(sys) #uncouth
# not needed for python 3
# sys.setdefaultencoding('utf8') #uncouth

# set path for new directories
_PATH = os.path.dirname(os.path.abspath(__file__))
_DIR_WISEREP = "/../sne-external-WISEREP/"
_DIR_INTERNAL = "/../sne-internal/"

# used for locating filenames with only these extensions (no fits files)
_ASCII_URL = "\.(flm|dat|asc|asci|ascii|txt|sp|spec)$"

if not os.path.exists(_PATH + _DIR_WISEREP):
    os.mkdir(_PATH + _DIR_WISEREP)

if not os.path.exists(_PATH + _DIR_INTERNAL):
    os.mkdir(_PATH + _DIR_INTERNAL)

# WISeREP Objects Home
_WISEREP_OBJECTS_URL = 'http://wiserep.weizmann.ac.il/objects/list'

# list of non-supernovae to exclude
exclude_type = [
    'Afterglow',
    'LBV',
    'ILRT',
    'Nova',
    'CV',
    'Varstar',
    'AGN',
    'Galaxy',
    'QSO',
    'Std-spec',
    'Gap',
    'Gap I',
    'Gap II',
    'SN impostor',
    'TDE',
    'WR',
    'WR-WN',
    'WR-WC',
    'WR-WO',
    'Other'
]

# list of SN survey programs to exclude, assuming they have already been
# collected
exclude_program = [
    'HIRES',
    'SUSPECT',
    'BSNIP',
    'CSP',
    'UCB-SNDB',
    'CfA-Ia',
    'CfA-Ibc',
    'CfA-Stripped',
    'SNfactory',
    'HIRES'
]

# exclude_program = ['HIRES']

# dig up lists of known non-supernovae and completed events, or create if
# it does not exist
if os.path.exists(_PATH + _DIR_INTERNAL + 'lists.json'):
    with open(_PATH + _DIR_INTERNAL + 'lists.json', 'r') as json_in:
        list_dict = json.load(json_in)
else:
    list_dict = {
        'non_SN': [],
        'completed': []
    }

# #uncomment to re-initialize
# list_dict['completed'] = []
# list_dict['non_SN'] = []

# locate objects search form


def select_obj_form(form):
    return form.attrs.get('action', None) == '/objects/list'


def mkSNdir(SNname):
    if not os.path.exists(_PATH + _DIR_WISEREP + SNname):
        os.mkdir(_PATH + _DIR_WISEREP + SNname)

# update lists.json


def updateListsJson(SNname, dict):
    dict.append(SNname)
    with open(_PATH + _DIR_INTERNAL + 'lists.json', 'w') as fp:
        json.dump(list_dict, fp, indent=4)


def savePage(name, page):
    with open(_PATH + _DIR_INTERNAL + 'WISEREP-' + name + '.html', 'w') as f:
        f.write(page)
        f.close()


def main():
    parser = argparse.ArgumentParser(prog='wisewebspider',
                                     description='WISeWEB-spider')
    parser.add_argument('--update', '-u', dest='update',
                        help='Run spider in update mode',
                        default=False, action='store_true')
    args = parser.parse_args()

    # begin scraping
    start_time = time.time()

    r = requests.get(_WISEREP_OBJECTS_URL)
    soup = BeautifulSoup(r.content, "lxml")
    if r:
        print('Grabbing list of events from WISeREP')

    # grab object name list
    SN_list_tags = soup.find("select", {"name": "objid"}).find_all("option")[
        1:]  # remove `Select Option' from list

    # Begin by selecting event, visiting page, and scraping.
    # SNname_list = ['SN2012fr', 'SN2016com']
    # for SNname in SNname_list:

    # Browser
    br = mechanicalsoup.Browser(soup_config={"features": "lxml"})

    search_page = br.get(_WISEREP_OBJECTS_URL)

    # ready search form with field entries and submit
    search_form = search_page.soup.find("form", {"action": "/objects/list"})
    search_form.find("input", {"name": "rowslimit"})["value"] = '1000'

    for item in SN_list_tags:
        SNname = item.get_text()

        if args.update:
            if os.path.exists(_PATH + _DIR_WISEREP + SNname):
                print('Skipping ' + SNname +
                      ', in update mode and folder already exists.')
                continue

        if SNname in list_dict['non_SN']:
            print(SNname, 'is not a supernova -- Skipping')
            continue
        elif SNname in list_dict['completed']:
            print(SNname, 'already done')
            continue

        print('Searching for', SNname, '...')

        # reset for every event -- change if needed
        SN_dict = {}

        search_form.find("input", {"name": "name"})["value"] = SNname

        # results page
        results_response = br.submit(search_form, _WISEREP_OBJECTS_URL)
        results_soup = results_response.soup
        results_page = results_soup.get_text()
        print('\tPage received')

        # locate object header indecies (_idx)
        try:
            headers = results_soup.find(
                "tr", {"style": "font-weight:bold"}).findChildren("td")
        except AttributeError:
            updateListsJson(SNname, list_dict['completed'])
            print('\t', SNname, 'has no available spectra')
            with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                f.write('From statement 1: ' + SNname +
                        ' has no spectra to collect' + '\n')
                f.close()
            continue

        for i, header in enumerate(headers):
            if header.text == 'Obj. Name':
                obj_name_idx = i
            if header.text == 'IAUName':
                iau_name_idx = i
            if header.text == 'Redshift':
                redshift_idx = i
            if header.text == 'Type':
                type_idx = i
            if header.text == 'No. ofSpectra':  # ofSpectra not a typo
                num_total_spec_idx = i

        # locate objects returned -- it's not always one
        obj_list = results_soup.findAll("form", {"target": "new"})
        num_objs = len(obj_list)
        if num_objs != 1:
            with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                f.write(str(num_objs) + ' objects returned for ' + SNname + '\n')
                f.close()

        # locate darkred text ``Potential matching IAU-Name'' if it exists
        # the location of html table rows (tr) changes if it exists
        darkred = results_soup.find("span", text=" Potential matching IAU-Name/s:",
                                    attrs={"style": "color:darkred; font-size:small"})

        # parse obj_list, match to SNname, and find its spectra
        for obj in obj_list:
            obj_header = obj.parent.findChildren("td")
            obj_name = obj_header[obj_name_idx].text

            if SNname == obj_name:
                target = obj_header

                if darkred:
                    try:
                        target_spectra = (obj.parent.nextSibling.nextSibling
                                          .findChildren("tr", {"valign": "top"}))
                    except AttributeError:
                        print('\t', SNname, 'has no spectra to collect')
                        with open(_PATH + _DIR_WISEREP +
                                  'scraper-log.txt', 'a') as f:
                            f.write('From statement 2: ' + SNname +
                                    ' has no spectra to collect' + '\n')
                            f.close()
                        continue

                elif darkred is None:
                    try:
                        target_spectra = obj.parent.nextSibling.findChildren(
                            "tr", {"valign": "top"})
                    except AttributeError:
                        print('\t', SNname, 'has no spectra to collect')
                        with open(_PATH + _DIR_WISEREP +
                                  'scraper-log.txt', 'a') as f:
                            f.write('From statement 2: ' + SNname +
                                    ' has no spectra to collect' + '\n')
                            f.close()
                        continue

        # exclude non-SN
        SNtype = target[type_idx].text
        if SNtype in exclude_type:
            updateListsJson(SNname, list_dict['non_SN'])
            updateListsJson(SNname, list_dict['completed'])
            print('\t', SNname, 'is a', SNtype)
            with open(_PATH + _DIR_WISEREP + 'non-supernovae.txt', 'a') as f:
                f.write(SNname + ' is a ' + SNtype + '\n')
                f.close()
            continue

        elif SNtype == '':
            # SNtype = 'Unspecified by WISeREP'
            print(
                '\tType not specified by WISeREP -- check the Open Supernova Catalog for type')
            with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                f.write(
                    'Type not specified by WISeREP -- check the Open Supernova Catalog for type')
                f.close()

        # second chance to exclude events without spectra
        num_total_spec = target[num_total_spec_idx].text
        num_total_spec = unicodedata.normalize("NFKD", num_total_spec)
        if num_total_spec == u'  ' or num_total_spec == u' 0 ':
            updateListsJson(SNname, list_dict['completed'])
            print('\t', SNname, 'has no spectra to collect')
            with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                f.write('From statement 3: ' + SNname +
                        ' has no spectra to collect' + '\n')
                f.close()
            continue

        redshift = target[redshift_idx].text
        # z = target[redshift_idx].text
        # redshift = 'Unavailable' if z==u'' else z

        SN_dict[SNname] = OrderedDict()
        # number of private spectra
        num_private_spectra = 0
        # number of publicly available spectra
        num_pub_spectra = 0

        spec_header = results_soup.find(
            "tr", {"style": "color:black; font-size:x-small"}).findChildren("td")
        for i, header in enumerate(spec_header):
            if header.text == 'Spec. Prog.':
                program_idx = i
            if header.text == 'Instrument':
                instrument_idx = i
            if header.text == 'Observer':
                observer_idx = i
            if header.text == 'Obs.date':
                obsdate_idx = i
            if header.text == 'Ascii/Fits Files':
                filename_idx = i
            if header.text == 'Publish':
                publish_idx = i
            if header.text == 'Contrib':
                contrib_idx = i
            if header.text == 'Last-modified':
                last_mod_idx = i
            if header.text == 'Modified-by':
                modified_by_idx = i

        # build SN_dict and locate ascii files on search results page associated
        # with SNname
        spectrum_haul = OrderedDict()

        for spec in target_spectra:

            spec_link = spec.find("a", href=re.compile(_ASCII_URL))

            try:
                dat_url = quote(spec_link.attrs['href'], "http://")
            except AttributeError:
                # found private spectrum
                num_private_spectra += 1
                continue

            children = spec.findChildren("td")
            filename = spec_link.text
            program = children[program_idx].text
            if program in exclude_program:
                print('\tSkipping', program, 'spectrum')
                # but still count it as public
                num_pub_spectra += 1
                continue

            # list of duplicate file prefixes to be excluded
            # list not shorted to ['t', 'f', 'PHASE'] for sanity
            regexes = [
                't' + SNname,
                'tPSN',
                'tPS',
                'tLSQ',
                'tGaia',
                'tATLAS',
                'tASASSN',
                'tSMT',
                'tCATA',
                'tSNhunt',
                'tSNHunt',
                'fSNhunt',
                'tSNHiTS',
                'tCSS',
                'tSSS',
                'tCHASE',
                'tSN',
                'tAT',
                'fPSN',
                'PHASE'
            ]

            regexes = "(" + ")|(".join(regexes) + ")"
            if re.match(regexes, filename):
                status = 'rapid'
            else:
                status = 'final'

            instrument = children[instrument_idx].text
            observer = children[observer_idx].text
            obsdate = children[obsdate_idx].text
            last_modified = children[last_mod_idx].text
            modified_by = children[modified_by_idx].text

            contrib = children[contrib_idx].text
            bibcode = children[publish_idx].text
            bibcode = unicodedata.normalize("NFKD", bibcode)
            if contrib == 'Ruiz-Lapuente, et al. 1997, Thermonuclear Supernovae. Dordrecht: Kluwer':
                bibcode = '1997Obs...117..312R'
                contrib = 'Ruiz-Lapuente et al. 1997'
            elif '%26' in bibcode:
                bibcode = bibcode.replace('%26', '&')

            SN_dict[SNname][filename] = OrderedDict([
                ("Type", SNtype),
                ("Redshift", redshift),
                ("Obs. Date", obsdate),
                ("Program", program),
                ("Contributor", contrib),
                ("Bibcode", bibcode),
                ("Instrument", instrument),
                ("Observer", observer),
                ("Reduction Status", status),
                ("Last Modified", last_modified),
                ("Modified By", modified_by)
            ])

            spectrum_haul[filename] = dat_url
            num_pub_spectra += 1

        if num_private_spectra > 0 and num_pub_spectra != 0:
            print('\tHit', num_private_spectra, 'private spectra for', SNname)
            with open(_PATH + _DIR_WISEREP + 'private-spectra-log.txt', 'a') as f:
                f.write(SNname + ' has ' + str(num_private_spectra) +
                        ' private spectra\n')
                f.close()

        elif num_pub_spectra == 0:
            updateListsJson(SNname, list_dict['completed'])
            savePage(SNname, results_page)
            print('\tAll spectra for', SNname, 'are still private')
            with open(_PATH + _DIR_WISEREP + 'private-spectra-log.txt', 'a') as f:
                f.write('All spectra for ' + SNname + ' are still private\n')
                f.close()
            continue

        if len(spectrum_haul) == 0:
            print('\tNot collecting spectra at this time')
            with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                f.write('Not collecting spectra of ' +
                        SNname + ' at this time' + '\n')
                f.close()
            updateListsJson(SNname, list_dict['completed'])
            savePage(SNname, results_page)

        elif len(spectrum_haul) == 1:

            print('\tDownloading 1 public spectrum')

            # make SNname subdirectory
            # os.mkdir(_PATH+_DIR_WISEREP+SNname)
            mkSNdir(SNname)

            for filename, url in spectrum_haul.items():
                rq = Request(url)
                res = urlopen(rq)
                dat = open(_PATH + _DIR_WISEREP +
                           SNname + "/" + filename, 'wb')
                dat.write(res.read())
                dat.close()

            # add README for basic metadata to SNname subdirectory
            print('\tWriting README')

            # f = open(_PATH+_DIR_WISEREP+SNname+'/README.txt','wb')
            # for file in SN_dict[SNname].keys():
            #     f.write(file+'\n')
            #     for key in SN_dict[SNname][file].keys():
            #         f.write('\t' + '%-*s  %s' % (20, key + ':', SN_dict[SNname][file][key]) + '\n')
            # f.close()

            with open(_PATH + _DIR_WISEREP + SNname + '/README.json', 'w') as fp:
                json.dump(SN_dict[SNname], fp, indent=4)

            updateListsJson(SNname, list_dict['completed'])
            savePage(SNname, results_page)

        elif len(spectrum_haul) > 1:

            # make SNname subdirectory
            # os.mkdir(_PATH+_DIR_WISEREP+SNname)
            mkSNdir(SNname)

            SN_files = deepcopy(SN_dict[SNname]).items()
            for filename, metadata in SN_files:
                if metadata['Reduction Status'] == 'rapid':
                    del SN_dict[SNname][filename]
                    del spectrum_haul[filename]

                    print('\tRemoving duplicate spectrum for',
                          SNname, '--', filename)
                    with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                        f.write('Removing duplicate spectrum for ' +
                                SNname + ' -- ' + filename + '\n')
                        f.close()

            last_modified = {}
            SN_files = SN_dict[SNname].items()
            for k, d in SN_files:
                for l, e in SN_files:
                    aa = d['Obs. Date'] == e['Obs. Date']
                    bb = d['Instrument'] == e['Instrument']
                    cc = d['Observer'] == e['Observer']
                    dd = d['Modified By'] == 'ofer-UploadSet'
                    ee = d['Modified By'] == e['Modified By']
                    if aa and bb and cc and dd and ee and k != l:  # 2012fs case
                        date = SN_dict[SNname][k]['Last Modified']
                        newdate = time.strptime(date, '%Y-%m-%d')
                        last_modified[k] = newdate

                    elif aa and bb and cc and k != l:  # 2016bau case
                        date = SN_dict[SNname][k]['Last Modified']
                        newdate = time.strptime(date, '%Y-%m-%d')
                        last_modified[k] = newdate

            if len(last_modified) <= 1:
                print('\tPresumably no other duplicate files found for', SNname)
                with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                    f.write(
                        'Presumably no other duplicate files found for ' + SNname + '\n')
                    f.close()

            elif len(last_modified) == 2:
                duplicate = min(last_modified, key=last_modified.get)
                del SN_dict[SNname][duplicate]
                del spectrum_haul[duplicate]

                print('\tRemoving duplicate spectrum for',
                      SNname, '--', duplicate)
                with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
                    f.write('Removing duplicate spectrum for ' +
                            SNname + ' -- ' + duplicate + '\n')
                    f.close()

            count = 1
            for filename, url in spectrum_haul.items():
                print('\tDownloading', count, 'of', len(
                    SN_dict[SNname]), 'public spectra')

                rq = Request(url)
                res = urlopen(rq)
                dat = open(_PATH + _DIR_WISEREP +
                           SNname + "/" + filename, 'wb')
                dat.write(res.read())
                dat.close()

                count += 1

            # add README for basic metadata to SNname subdirectory
            print('\tWriting README')

            # f = open(_PATH+_DIR_WISEREP+SNname+'/README.txt','wb')
            # for file in SN_dict[SNname].keys():
            #     f.write(file+'\n')
            #     for key in SN_dict[SNname][file].keys():
            #         f.write('\t' + '%-*s  %s' % (20, key + ':', SN_dict[SNname][file][key]) + '\n')
            # f.close()

            with open(_PATH + _DIR_WISEREP + SNname + '/README.json', 'w') as fp:
                json.dump(SN_dict[SNname], fp, indent=4)

            updateListsJson(SNname, list_dict['completed'])
            savePage(SNname, results_page)

    # execution time in minutes
    minutes = (time.time() - start_time) / 60.0
    print("Runtime: %s minutes" % minutes)
    with open(_PATH + _DIR_WISEREP + 'scraper-log.txt', 'a') as f:
        f.write('Runtime: ' + str(minutes) + ' minutes')
        f.close()

    # reset completed to 0 once all done
    list_dict['completed'] = []
    updateListsJson(SNname, list_dict['completed'])
