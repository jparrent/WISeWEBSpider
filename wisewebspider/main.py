#!/usr/bin/python3
"""
===============================================================================
title           :main.py for wisewebspider package
description     :Scrapes and downloads all publicly availabe spectra from
                 WISeREP.
authors          :Jerod Parrent, James Guillochon
date            :2016-08-25
version         :0.4
usage           :python3.5 -m wiserepspider (--update --daysago 30)
notes           :runtime with pages saved and no exlusions = 18.7 hours
                :runtime after initial scrape and update =< minutes
python_version  :3.5.2
===============================================================================
"""

import argparse
import json
import os
import re
import shutil
import time
import unicodedata
from collections import OrderedDict
from copy import deepcopy
from urllib.parse import quote
from urllib.request import Request, urlopen

from robobrowser import RoboBrowser

_DIR_WISEREP = "/../sne-external-WISEREP/"

# set path for new directories
_PATH = os.path.dirname(os.path.abspath(__file__))

# used for locating filenames with only these extensions (no fits files)
_ASCII_URL = "\.(flm|dat|asc|asci|ascii|txt|sp|spec|[0-9])$"

# WISeREP Objects Home
_WISEREP_OBJECTS_URL = 'http://wiserep.weizmann.ac.il/objects/list'
_WISEREP_SPECTRA_URL = 'http://wiserep.weizmann.ac.il/spectra/list'

# list of non-supernovae to exclude
exclude_type = [
    'Afterglow', 'LBV', 'ILRT', 'Nova', 'CV', 'Varstar', 'AGN', 'Galaxy',
    'QSO', 'Std-spec', 'Gap', 'Gap I', 'Gap II', 'SN impostor', 'WR',
    'WR-WN', 'WR-WC', 'WR-WO', 'Other', 'TDE'
]

# list of SN survey programs to exclude, assuming they have already been
# collected
exclude_program = [
    'HIRES', 'SUSPECT', 'BSNIP', 'CSP', 'UCB-SNDB', 'CfA-Ia', 'CfA-Ibc',
    'CfA-Stripped', 'SNfactory', 'HIRES'
]

wiserep_spectrum_ignore = []

with open(os.path.join(os.path.dirname(_PATH), 'wiserep_spectrum_ignore.txt'), 'r') as f:
    for line in f:
        line = line.rstrip()
        wiserep_spectrum_ignore.append(line)


def mkSNdir(SNname, path):
    if not os.path.exists(_PATH + path + SNname):
        os.mkdir(_PATH + path + SNname)


def rmSNdir(SNname, path):
    if os.path.exists(_PATH + path + SNname):
        print('\tRemoving', SNname, 'directory tree to update files')
        shutil.rmtree(_PATH + path + SNname)


# update lists.json
def updateListsJson(SNname, dict_list, list_dict, path):
    dict_list.append(SNname)
    with open(_PATH + path + 'lists.json', 'w') as fp:
        json.dump(list_dict, fp, indent=4)


def main():
    parser = argparse.ArgumentParser(
        prog='wisewebspider', description='WISeWEBspider')
    parser.add_argument(
        '--update',
        '-u',
        dest='update',
        help='Run spider in update mode',
        default=False,
        action='store_true')
    parser.add_argument(
        '--daysago',
        '-d',
        dest='daysago',
        help='Number of days since last update.' +
        'Set to 1, 2, 7, 14, 30, 180, or 365.',
        default=False,
        action='store')
    parser.add_argument(
        '--path',
        '-p',
        dest='path',
        help='Path to sne-external-WISEREP directory. ' +
        'Default: Within main WISeWEBSpider directory.',
        default=_DIR_WISEREP,
        type=str,
        action='store')
    parser.add_argument(
        '--name',
        '-n',
        dest='name',
        help='Name of specific event to pull',
        default=None,
        type=str,
        action='store')
    parser.add_argument(
        '--included-types',
        '-i',
        dest='include_type',
        help='Include only these object types. ' +
        'Default: Include all types not set in exclude_type.',
        default=[],
        nargs='+',
        action='store')
    args = parser.parse_args()

    spider(update=args.update, daysago=args.daysago, name=args.name,
           path=args.path, include_type=args.include_type)

    # for debugging
    # spider(update=True, daysago=30, path=_DIR_WISEREP)


def spider(update=False, daysago=30, name=None, path=_DIR_WISEREP, include_type=[]):
    start_time = time.time()

    incl_type_str = 'supernovae' if not include_type else '-'.join(
        include_type)

    if not os.path.exists(_PATH + path):
        os.mkdir(_PATH + path)

    # dig up lists of known non-supernovae and completed events, or create if
    # it does not exist
    if os.path.exists(_PATH + path + 'lists.json'):
        with open(_PATH + path + 'lists.json', 'r') as json_in:
            list_dict = json.load(json_in)
    else:
        list_dict = {'non_SN': [], 'completed': []}

        with open(_PATH + path + 'lists.json', 'w') as fp:
            json.dump(list_dict, fp, indent=4)

    # collect metadata for the few available host spectra and
    # build a dictionary that will be used below to
    # remove by SNname and "Spectrum Type"
    obj_host_dict = {}
    if daysago:
        browser = RoboBrowser(history=False, parser='lxml')
        browser.open(_WISEREP_SPECTRA_URL)
        form = browser.get_form(action='/spectra/list')
        form['spectypeid'] = "2"  # 2 for Host spectrum
        form['rowslimit'] = "10000"
        browser.submit_form(form)
        print('\tHost page received')

        obj_host_headers = (browser.find("tr", {"style": "font-weight:bold"})
                            .findChildren("td"))

        for i, header in enumerate(obj_host_headers):
            # if header.text == 'Obj. Name':
            #     host_obj_name_idx = i
            if header.text == 'Spec.Program':
                host_program_idx = i
            if header.text == 'Instrument':
                host_instrument_idx = i
            if header.text == 'Observer':
                host_observer_idx = i
            if header.text == 'Obs. Date':
                host_obsdate_idx = i
            if header.text == 'Reducer':
                host_reducer_idx = i
            if header.text == 'Ascii FileFits  File':
                host_filename_idx = i

        obj_host_list = browser.find_all(
            "a", {"title": "Click to show/update object"})

        for i, obj in enumerate(obj_host_list):
            print('\tParsing', i + 1, 'of', len(obj_host_list), 'host spectra')
            obj_name = obj.text
            host_children = obj.parent.parent.findChildren("td")
            host_program = host_children[host_program_idx].text
            host_instrument = host_children[host_instrument_idx].text
            host_observer = host_children[host_observer_idx].text
            host_obsdate = host_children[host_obsdate_idx].text
            host_reducer = host_children[host_reducer_idx].text
            host_filename = host_children[host_filename_idx].text
            host_filename = host_filename.strip().split('\n')[0]

            obj_host_dict[obj_name] = OrderedDict([
                ("Type", "Host spectrum"),
                ("Filename", host_filename),
                ("Obs. Date", host_obsdate),
                ("Program", host_program),
                ("Instrument", host_instrument),
                ("Observer", host_observer),
                ("Reducer", host_reducer),
            ])

    # begin scraping WISeREP OBJECTS page for supernovae
    browser = RoboBrowser(history=False, parser='lxml')
    browser.open(_WISEREP_OBJECTS_URL)
    form = browser.get_form(action='/objects/list')

    # ready search form with field entries to submit, depending on --update
    if browser and update:
        if daysago:
            daysstr = str(daysago)
            # set "Added within the last args.daysago days"
            print('Collecting new spectra from the last', daysstr, 'days')

            form['daysago'] = daysstr
        if name:
            form['name'] = name
        browser.submit_form(form)

        try:
            new_objs = (browser.find("tr", {"style": "font-weight:bold"})
                        .parent.findChildren("tr", {"valign": "top"}))
        except AttributeError:
            if daysago:
                print('Nothing to collect since ' + daysstr + ' days ago')
            else:
                print('Nothing to collect!')
            return

        new_objs = (browser.find("tr", {"style": "font-weight:bold"})
                    .parent.findChildren("tr", {"valign": "top"}))

        SN_list_tags = []

        for obj in new_objs:
            obj_name_tag = obj.find("a", {"title": "Click to show/update"})
            SN_list_tags.append(obj_name_tag)

        SN_list_tags = [i for i in SN_list_tags if i is not None]

    elif browser and not update:
        # grab object name list, and remove `Select Option' from list [1:]
        print('Grabbing list of events from WISeREP')
        SN_list_tags = browser.find("select",
                                    {"name": "objid"}).find_all("option")[1:]

    # Begin by selecting event, visiting page, and scraping.
    # SN_list = ['SN2009ip']
    # for item in SN_list:
    for item in SN_list_tags:
        SNname = item.get_text()
        # SNname = item

        if SNname in list_dict['non_SN']:
            print(SNname, 'is not a ' + incl_type_str + ' -- Skipping')
            continue
        elif SNname in list_dict['completed']:
            print(SNname, 'already done')
            continue

        print('Searching for', SNname, '...')

        # reset for every event -- change if needed
        SN_dict = {}

        # if in update mode and SNname directory exists, remove it
        if update:
            rmSNdir(SNname, path)

        # set Obj Name to SNname and retrieve results page
        form['name'] = SNname
        browser.submit_form(form)
        print('\tPage received')

        # locate object header indecies (_idx)
        try:
            headers = browser.find(
                "tr", {"style": "font-weight:bold"}).findChildren("td")
        except AttributeError:
            if update:
                updateListsJson(SNname, list_dict['completed'], list_dict,
                                path)
                print('\t', 'No spectra to collect')
                break
            else:
                updateListsJson(SNname, list_dict['completed'], list_dict,
                                path)
                print('\t', SNname, 'has no available spectra')
                with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                    f.write('From statement 1: ' + SNname +
                            ' has no spectra to collect' + '\n')
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
            if header.text == 'No. of publicSpectra':  # publicSpectra not a typo
                num_total_spec_idx = i

        # locate objects returned -- it's not always one
        obj_list = browser.find_all("form", {"target": "new"})
        num_objs = len(obj_list)

        if num_objs >= 1 and update:
            print('\tNew data available for', num_objs, 'objects.')
        if num_objs != 1:
            with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                f.write(
                    str(num_objs) + ' objects returned for ' + SNname + '\n')

        # locate darkred text ``Potential matching IAU-Name'' if it exists
        # the location of html table rows (tr) changes if it exists
        darkred = browser.find(
            "span",
            text=" Potential matching IAU-Name/s:",
            attrs={"style": "color:darkred; font-size:small"})

        # parse obj_list, match to SNname, and find its spectra
        target = ''
        for obj in obj_list:
            obj_header = obj.parent.findChildren("td")
            obj_name = obj_header[obj_name_idx].text

            if SNname == obj_name:
                target = obj_header

                # this checks for spurious page element that changes layout
                if darkred:
                    try:
                        target_spectra = (
                            obj.parent.nextSibling.nextSibling.findChildren(
                                "tr", {"valign": "top"}))
                    except AttributeError:
                        print('\t', SNname, 'has no spectra to collect')
                        with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                            f.write('From statement 2: ' + SNname +
                                    ' has no spectra to collect' + '\n')
                        continue

                elif darkred is None:
                    try:
                        target_spectra = obj.parent.nextSibling.findChildren(
                            "tr", {"valign": "top"})
                    except AttributeError:
                        print('\t', SNname, 'has no spectra to collect')
                        with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                            f.write('From statement 3: ' + SNname +
                                    ' has no spectra to collect' + '\n')
                        continue
        # No match found, skip this event
        if not target:
            continue

        # exclude non-SN
        SNtype = target[type_idx].text
        if ((include_type and SNtype not in include_type) or
                (not include_type and SNtype in exclude_type)):
            updateListsJson(SNname, list_dict['non_SN'], list_dict, path)
            updateListsJson(SNname, list_dict['completed'], list_dict, path)
            print('\t', SNname, 'is a', SNtype)
            with open(_PATH + path + 'non-' + incl_type_str + '.txt', 'a') as f:
                f.write(SNname + ' is a ' + SNtype + '\n')
            continue

        elif SNtype == '':
            # SNtype = 'Unspecified by WISeREP'
            print('\tType not specified by WISeREP.',
                  'Check the Open Supernova Catalog for type.')
            with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                f.write('Type not specified by WISeREP.' +
                        'Check the Open Supernova Catalog for type.')

        # create a directory even if the SN event has no spectra.
        # find other instances of mkSNdir to revert this.
        mkSNdir(SNname, path)

        # second chance to exclude events without spectra
        num_total_spec = target[num_total_spec_idx].text
        num_total_spec = unicodedata.normalize("NFKD", num_total_spec)
        if num_total_spec == u'  ' or num_total_spec == u' 0 ':
            updateListsJson(SNname, list_dict['completed'], list_dict, path)
            print('\t', SNname, 'has no spectra to collect')
            with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                f.write('From statement 4: ' + SNname +
                        ' has no spectra to collect' + '\n')
            continue

        redshift = target[redshift_idx].text

        SN_dict[SNname] = OrderedDict()

        # number of publicly available spectra
        num_pub_spectra = 0

        spec_header = browser.find(
            "tr",
            {"style": "color:black; font-size:x-small"}).findChildren("td")
        for i, header in enumerate(spec_header):
            if header.text == 'Spec. Prog.':
                program_idx = i
            if header.text == 'Instrument':
                instrument_idx = i
            if header.text == 'Observer':
                observer_idx = i
            if header.text == 'Obs.date':
                obsdate_idx = i
            if header.text == 'Reducer':
                reducer_idx = i
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

        # build SN_dict and locate ascii files on search results page
        # associated with SNname
        spectrum_haul = OrderedDict()

        for spec in target_spectra:

            spec_link = spec.find("a", href=re.compile(_ASCII_URL))
            try:
                dat_url = quote(spec_link.attrs['href'], "http://")
            except AttributeError:  # handles a return of 'None'
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
                't' + SNname, 'tPSN', 'tPS', 'tLSQ', 'tGaia', 'tATLAS',
                'tASASSN', 'tSMT', 'tCATA', 'tSNhunt', 'tSNHunt', 'fSNhunt',
                'tSNHiTS', 'tCSS', 'tSSS', 'tCHASE', 'tSN', 'tAT', 'fPSN',
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
            reducer = children[reducer_idx].text
            last_modified = children[last_mod_idx].text
            modified_by = children[modified_by_idx].text

            contrib = children[contrib_idx].text
            bibcode = children[publish_idx].text
            bibcode = unicodedata.normalize("NFKD", bibcode)
            if (contrib == ('Ruiz-Lapuente, et al. 1997, Thermonuclear '
                            'Supernovae. Dordrecht: Kluwer')):
                bibcode = '1997Obs...117..312R'
                contrib = 'Ruiz-Lapuente et al. 1997'
            elif '%26' in bibcode:
                bibcode = bibcode.replace('%26', '&')

            SN_dict[SNname][filename] = OrderedDict([
                ("Type", SNtype), ("Redshift", redshift),
                ("Obs. Date", obsdate), ("Program", program),
                ("Contributor", contrib), ("Bibcode", bibcode),
                ("Instrument", instrument), ("Observer", observer),
                ("Reducer", reducer), ("Reduction Status", status),
                ("Last Modified", last_modified), ("Modified By", modified_by)
            ])

            spectrum_haul[filename] = dat_url
            num_pub_spectra += 1

        # Metadata for SNname is now available.
        # The following filters cases by the number of
        # spectra that appear on the WISeREP page.

        if len(spectrum_haul) == 0:
            print('\tNot collecting spectra at this time')
            with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                f.write('Not collecting spectra of ' + SNname + ' at this time'
                        + '\n')

            with open(_PATH + path + SNname + '/README.json', 'w') as fp:
                json.dump(SN_dict[SNname], fp, indent=4)

            updateListsJson(SNname, list_dict['completed'], list_dict, path)
            continue

        elif len(spectrum_haul) == 1:

            # remove host spectrum if it exists
            if SNname in obj_host_dict.keys():
                if obj_host_dict[SNname]['Filename'] in SN_dict[SNname].keys():
                    filename = obj_host_dict[SNname]['Filename']
                    del SN_dict[SNname][filename]

                    print('\tPurging host galaxy spectrum --', filename)

                print('\tNot collecting spectra at this time')
                with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                    f.write('Not collecting spectra of ' + SNname +
                            ' at this time' + '\n')

                updateListsJson(SNname, list_dict['completed'], list_dict,
                                path)
                continue

            print('\tDownloading 1 public spectrum')

            # make SNname subdirectory
            # os.mkdir(_PATH+path+SNname)
            # mkSNdir(SNname, path)

            for filename, url in spectrum_haul.items():
                if filename in wiserep_spectrum_ignore:
                    print('\tIgnoring spectrum for', SNname,
                          '-- see sne-external-spectra/donations')
                    continue
                else:
                    rq = Request(url)
                    res = urlopen(rq)
                    dat = open(_PATH + path + SNname + "/" + filename, 'wb')
                    dat.write(res.read())
                    dat.close()

            # add README for basic metadata to SNname subdirectory
            print('\tWriting README')
            with open(_PATH + path + SNname + '/README.json', 'w') as fp:
                json.dump(SN_dict[SNname], fp, indent=4)

            updateListsJson(SNname, list_dict['completed'], list_dict, path)

        elif len(spectrum_haul) > 1:

            # make SNname subdirectory
            # os.mkdir(_PATH+path+SNname)
            # mkSNdir(SNname, path)

            SN_files = deepcopy(SN_dict[SNname])
            for filename, metadata in SN_files.items():
                if metadata['Reduction Status'] == 'rapid':
                    del SN_dict[SNname][filename]
                    del spectrum_haul[filename]

                    print('\tRemoving duplicate spectrum for', SNname, '--',
                          filename)
                    with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                        f.write('Removing duplicate spectrum for ' + SNname +
                                ' -- ' + filename + '\n')

            # remove host spectrum if it exists
            if SNname in obj_host_dict.keys():
                if obj_host_dict[SNname]['Filename'] in SN_dict[SNname].keys():
                    filename = obj_host_dict[SNname]['Filename']
                    del SN_dict[SNname][filename]

                    print('\tPurging host galaxy spectrum --', filename)

            # need to continue to next supernova if host spectrum was only one
            if len(SN_dict[SNname].keys()) == 0:
                print('\tNot collecting spectra at this time')
                with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                    f.write('Not collecting spectra of ' + SNname +
                            ' at this time' + '\n')
                updateListsJson(SNname, list_dict['completed'], list_dict,
                                path)
                continue

            last_modified = {}
            SN_files = deepcopy(SN_dict[SNname])
            for k, d in SN_files.items():
                for l, e in SN_files.items():
                    aa = d['Obs. Date'] == e['Obs. Date']
                    bb = d['Instrument'] == e['Instrument']
                    cc = d['Observer'] == e['Observer']
                    dd = d['Modified By'] == 'ofer-UploadSet'
                    ee = d['Modified By'] == e['Modified By']
                    if aa and bb and cc and dd and ee and k != l:  # see 2012fs
                        date = SN_dict[SNname][k]['Last Modified']
                        newdate = time.strptime(date, '%Y-%m-%d')
                        last_modified[k] = newdate

                    elif aa and bb and cc and k != l:  # see 2016bau
                        date = SN_dict[SNname][k]['Last Modified']
                        newdate = time.strptime(date, '%Y-%m-%d')
                        last_modified[k] = newdate

            if len(last_modified) <= 1:
                print('\tPresumably no other duplicate files found for',
                      SNname)
                with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                    f.write('Presumably no other duplicate files found for ' +
                            SNname + '\n')

            elif len(last_modified) == 2:
                duplicate = min(last_modified, key=last_modified.get)
                del SN_dict[SNname][duplicate]
                del spectrum_haul[duplicate]

                print('\tRemoving duplicate spectrum for', SNname, '--',
                      duplicate)
                with open(_PATH + path + 'scraper-log.txt', 'a') as f:
                    f.write('Removing duplicate spectrum for ' + SNname +
                            ' -- ' + duplicate + '\n')

            count = 1
            for filename, url in spectrum_haul.items():
                print('\tDownloading', count, 'of', len(SN_dict[SNname]),
                      'public spectra')

                if filename in wiserep_spectrum_ignore:
                    print('\tIgnoring spectrum for', SNname,
                          '-- see sne-external-spectra/donations')
                    continue
                else:
                    rq = Request(url)
                    res = urlopen(rq)
                    dat = open(_PATH + path + SNname + "/" + filename, 'wb')
                    dat.write(res.read())
                    dat.close()

                count += 1

            # add README for basic metadata to SNname subdirectory
            print('\tWriting README')
            with open(_PATH + path + SNname + '/README.json', 'w') as fp:
                json.dump(SN_dict[SNname], fp, indent=4)

            updateListsJson(SNname, list_dict['completed'], list_dict, path)

    # reset completed to 0 once all done
    list_dict['completed'] = []
    with open(_PATH + path + 'lists.json', 'w') as fp:
        json.dump(list_dict, fp, indent=4)

    # execution time in minutes
    minutes = (time.time() - start_time) / 60.0
    print("Runtime: %s minutes" % minutes)
    with open(_PATH + path + 'scraper-log.txt', 'a') as f:
        f.write('Runtime: ' + str(minutes) + ' minutes')
