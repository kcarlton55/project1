#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File initial creation on Sun Nov 18 2018

@author: Kenneth E. Carlton

This program compares two BOMs: one originating from SolidWorks (SW) and the
other from SyteLine (SL).  The structure of the BOMs (headings, structure,
etc.) are very unique to our company.  Therefore this program, unaltered, will
fail to function at another company.

Run this program from the command line like this: python bomcheck.py '*'

Without any arguments help info is shown: python bomcheck.py

Run from a python console terminal like this: bomcheck('*')

To see how to create an EXE file from this program, see the file named
howtocompile.md.
"""


__version__ = '1.7.3'
__author__ = 'Kenneth E. Carlton'
import glob, argparse, sys, warnings
import pandas as pd
import os.path
import os
import tempfile
import re
import datetime
import pytz
import fnmatch
warnings.filterwarnings('ignore')  # the program has its own error checking.
pd.set_option('display.max_rows', 150)
pd.set_option('display.max_columns', 10)
pd.set_option('display.max_colwidth', 100)
pd.set_option('display.width', 200)


def get_version():
    return __version__


def set_globals():
    ''' Create a global variables including the primary one named cfg.
    cfg is a dictionary containing settings used by this program.
    
    set_globals() is ran when bomcheck first starts up.
    
    set_globals() tries to derive settings from the file named bc_bomcheck.py
    if it can be located and if values have been established there.
    Otherwise set_globals() creates its on settings for cfg.
    '''
    global cfg, printStrs, excelTitle
    cfg = {}
    printStrs = ''
    excelTitle = []
    # try to import the file named bc_config.py.
    usrPrf = os.getenv('USERPROFILE')  # on my win computer, USERPROFILE = C:/Users/k_carlton
    if usrPrf:
        userDocDir = os.path.join(usrPrf, 'Documents')  # if usrPrf was not None
    else:
        userDocDir = "C:/"  
    paths = [userDocDir, "/home/ken/projects/project1/"]  # the 2nd value if testing at my home
    for p in paths:
        if os.path.exists(p) and not p in sys.path:
            sys.path.append(p)
            break
    else:
        printStr = ('At function "set_globals", a suitable path was not found to\n'
              'load bc_config.py from.')
        printStrs += printStr
        print(printStr)
    try:
        import bc_config
    except ModuleNotFoundError:
        def bc_config():  # do this so that doing "dir(bc_config)" below doesn't fail
            pass

    cfg = {}
    cfg['col'] = {}
    def insert_into_cfg(var, default, col=False):
        ''' Function to insert key/value pairs into the dictionary named cfg.
        Use values set in the file named bc_config.py if possible.'''
        if col: 
            value = bc_config.__dict__[var] if (var in dir(bc_config)) else default
            cfg['col'].update({var:value})
        else:                
           cfg[var] = bc_config.__dict__[var] if (var in dir(bc_config)) else default
    # default settings for bomcheck
    list1 = [('accuracy', 2),       ('discard_length', ['3086-*']), 
             ('drop', ['3*-025']),  ('exceptions', []), 
             ('from_um', 'inch'),   ('timezone', 'US/Central'),
             ('to_um', 'feet')]
    # Give to bomcheck names of columns that it can expect to see in BOMs.  If
    # one of the names in each group shown in brackets below is not found,
    # then bomcheck will fail.
    list2 = [('part_num_sw', ["PARTNUMBER", "PART NUMBER", "Part Number"]),
             ('part_num_sl', ["Item", "Material"]),
             ('qty_sw',      ["QTY", "QTY."]), 
             ('qty_sl',      ["Qty", "Quantity", "Qty Per"]),
             ('descrip_sw',  ["DESCRIPTION"]),
             ('descrip_sl',  ["Material Description", "Description"]),
             ('um_sl',       ["UM", "U/M"]),
             ('itm_num_sw',  ["ITEM NO."]),
             ('level_sl',    ["Level"])]
    for k, v in list1:
        insert_into_cfg(k, v)
    cfg['accuracy'] = int(cfg['accuracy'])    
    for k, v in list2:
        insert_into_cfg(k, v, col=True)
                             
    
def showSettings():
    return cfg


def main():
    '''This fuction allows this bomcheck.py program to be run from the command
    line.  It is started automatically (via the "if __name__=='__main__'"
    command at the bottom of this file) when bomecheck.py is run.

    calls: bomcheck

    Examples
    ========

    $ python bomcheck.py "078551*"

    $ python bomcheck.py "C:/pathtomyfile/6890-*"

    $ python bomcheck.py "*"

    $ python bomcheck.py --help

    '''
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                        description='Program compares SolidWorks BOMs to SyteLine BOMs.  ' +
                        'Output is sent to a Microsoft Excel spreadsheet.')
    parser.add_argument('filename', help='Name of file containing a BOM.  Name ' +
                        'must end with _sw.xlsx, _sl.xlsx. _sw.csv, or ' +
                        '_sl.csv.  Enclose filename in quotes!  An asterisk, *, ' +
                        'caputures multiple files.  Examples: "6890-*", "*".  ' +
                        'Or if filename is instead a directory, all _sw and _sl files ' +
                        'in that directory and subdirectories thereof will be ' +
                        'gathered.  BOMs gathered from _sl files without ' +
                        'corresponding SolidWorks BOMs found are ignored.')
    parser.add_argument('-d', '--drop', action='store_true', default=False,
                        help='Ignore 3*-025 pns, i.e. do not use in the bom check')
    parser.add_argument('-c', '--sheets', action='store_true', default=False,
                        help='Break up results across multiple sheets in the ' +
                        'Excel file')
    parser.add_argument('-v', '--version', action='version', version=__version__,
                        help="Show program's version number and exit")
    parser.add_argument('-f', '--followlinks', action='store_false', default=True,
                        help='Follow symbolic links when searching for files to process.  ' +
                        "  (MS Windows doesn't honor this option.)")
    parser.add_argument('--from_um',  default=cfg['from_um'], help='The unit of measure ' +
                        'to apply to lengths in a SolidWorks BOM unless otherwise ' +
                        'specified', metavar='value')
    parser.add_argument('--to_um', default=cfg['to_um'], help='The unit of measure ' +
                        'to convert SolidWorks lengths to', metavar='value')
    parser.add_argument('-a', '--accuracy', help='decimal place accuracy applied ' +
                        'to lengths in a SolidWorks BOM', default=cfg['accuracy'], metavar='value')
    
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    
    bomcheck(args.filename, vars(args))


def bomcheck(fn, dic={}, **kwargs):
    '''  
    This is the primary function of the bomcheck program and acts as a hub
    for other functions within the bomcheck program.  First to occur: Excel 
    and/or csv files that contain BOMs are opened.  Filenames containing BOMs 
    must end with _sw.xlsx,_sl.xlsx, _sw.csv, or _sl.csv; otherwise the files
    are ignored.  For a comparison between a SolidWorks (SW) BOM and a 
    SyteLine (SL) BOM to occur, filenames must be the same up until the 
    underscore (_) character of the filename.  E.g., 086677_sw.xlsx and 
    086677_sl.xlsx match.  By the way, an _sw.csv file will compare with a
    _sl.xlsx file, and vice versa.
    
    This function will also handle multilevel BOMs from SW and/or SL.  In which
    case subassembly BOMs will automatically be extracted to allow the BOM 
    check to occur.

    Any _sw files found for which no matching _sl file is found will be
    converted into a SyteLine like BOM format and output to an Excel file.
    If a _sl file is present for which no corresponding _sw file is found, 
    the _sl file is ignored; that is, no output... output is silent.

    After BOM merges occur, an Excel file is output containing the results. 
    The name of the Excel file is bomcheck.xlsx.  The results are the SW files
    for which no matching SL file was found, and also for the merged SW/SL 
    BOMs.  Finally this function will also return DataFrame objects of the 
    results.

    calls: gatherBOMs_from_fnames, collect_checked_boms, concat_boms, 
    export2excel, get_fnames

    Parmeters
    =========

    fn: string or list
        1.  Filename of Excel or csv files to do a BOM check on.  Default: "*"
            (i.e. all _sw & _sl files in the current working directory).
        2.  fn can be a directory name in which case all _sw and _sl files
            in that directory and subdirectories thereof are analyzed.
        3.  If a list is given, then it is a list of filenames and/or 
            directories.
        4.  An asterisk, *, matches any characters.  E.g. 6890-083544-* will
            match 6890-083544-1_sw.xlsx, 6890-083544-2_sw.xlsx, etc.
        
    dic: dictionary
        default: {}, i.e. an empty dictionary.  This variable is only used if
        the function "main" is used to run the bomcheck program; that is,
        the bomcheck program was inititiated from the command line.  If so,
        keys named "drop", "sheets", "from_um", and "to_um" and corresponding
        values thereof will have been put into dic.
        
    kwargs: dictionary
        Unlike dic, no values in kwargs are derived from the main function.
        This variable is used when bomcheck is run from a python console.  The
        dictionary key/value items that this function looks for are:

        c:  bool
            Break up results across multiple sheets within the bomcheck.xlsx
            file.  Default: False
    
        d: bool
            If True, employ the list named drop which will have been created by
            the function named "set_globals".  Default: False
            
        x: bool
            Export results to an Excel file named bomcheck.xlsx.  Default: True
    
        u: string
            Username.  This will be fed to the export2exel function so that a
            username will be placed into the footer of the bomcheck.xlsx file.
            Default: 'unknown'
            
        f: bool
            If True, follow symbolic links when searching for files to process.
            Default: False
    
    Returns
    =======

    out: tuple and an Excel file
        An Excel file is automatically created showing results of the bom 
        check.
    
        When c=False, returns a tuple containing two items:

            1.  One DataFrame object comprised of SW BOMs for which no
                matching SL BOMs were found.

            2.  One DataFrame object comprised of merged BOMs

        When c=True, no tuple is returned and the Excel file takes on a 
        different format as described above.

    Examples
    ========

    >>> bomcheck("078551*") # all file names beginning with characters: 078551

    >>> bomcheck("C:/folder/6890*")  # files names starting with 6890

    >>> bomcheck("*", d=True)   # all files in the current working directory

    >>> bomcheck("C:/folder") # all files in 'folder' and in subdirectories of
    
    >>> bomcheck("C:/folder/*") # all files, one level deep
    
    >>> bomcheck(["C:/folder1/*", "C:/folder2/*"], d=True, u="John Doe") 
    
    '''
    global printStrs, cfg
    # Set settings depending on 1. if input was derived from running this 
    # program from the command line (i.e. values from dic), 2. if from 
    # excecuting the bomcheck() function within a python console or called by
    # some other python function (i.e. from kwargs), or 3. if the settings were
    # imported from bc_config.py.  Many default values (e.g. cfg['from_um'])
    # were initially establisd by the set_globals() function.
    cfg['from_um'] = (dic.get('from_um') if dic.get('from_um')
                      else kwargs.get('from_um', cfg['from_um']))  
    cfg['to_um'] = (dic.get('to_um') if dic.get('to_um')
                    else kwargs.get('to_um', cfg['to_um']))
    cfg['accuracy'] = (dic.get('accuracy') if dic.get('accuracy')
                       else kwargs.get('a', cfg['accuracy']))
    cfg['drop'] = (dic.get('drop') if dic.get('drop') 
                   else kwargs.get('d', False))
    c = (dic.get('sheets') if dic.get('sheets') else kwargs.get('c', False))
    u =  kwargs.get('u', 'unknown')  
    x = kwargs.get('x', True)
    f = kwargs.get('f', False)

        
    if isinstance(fn, str) and fn.startswith('[') and fn.endswith(']'):
        fn = eval(fn)  # change a string to a list
    elif isinstance(fn, str):
        fn = [fn]

    fn = get_fnames(fn, followlinks=f)  # get filenames with any extension.   
        
    if cfg['drop']:
        printStr = '\ndrop = ' + str(cfg['drop']) + '\nexceptions = ' + str(cfg['exceptions']) + '\n'
        printStrs += printStr
        print(printStr)

    dirname, swfiles, slfiles = gatherBOMs_from_fnames(fn)

    # lone_sw is a dic; Keys are assy nos; Values are DataFrame objects (SW 
    # BOMs only).  merged_sw2sl is a dic; Keys are assys nos; Values are 
    # Dataframe objects (merged SW and SL BOMs).
    lone_sw, merged_sw2sl = collect_checked_boms(swfiles, slfiles)

    title_dfsw = []                # Create a list of tuples: [(title, swbom)... ]
    for k, v in lone_sw.items():   # where "title" is is the title of the BOM,
        title_dfsw.append((k, v))  # usually the part no. of the BOM.

    title_dfmerged = []            # Create a list of tuples: [(title, mergedbom)... ]
    for k, v in merged_sw2sl.items():
        title_dfmerged.append((k, v)) 

    if title_dfsw:
        printStr = '\nNo matching SyteLine BOMs found for these SolidWorks files:\n'
        printStr += '\n'.join(list(map(lambda x: '    ' + x[0], title_dfsw))) + '\n'
        printStrs += printStr
        print(printStr)

    if c == False:                 # concat_boms is a bomcheck function
    	title_dfsw, title_dfmerged = concat_boms(title_dfsw, title_dfmerged)

    if x:
        try:
            if title_dfsw or title_dfmerged:
                export2excel(dirname, 'bomcheck', title_dfsw + title_dfmerged, u)
            else:
                printStr = ('\nNo SolidWorks files found to process.  (Lone SyteLine\n' +
                            'BOMs will be ignored.)  Make sure file names end with\n' +
                            '_sw.xlsx, _sw.csv, _sl.xlsx, or _sl.csv.\n')
                printStrs += printStr
                print(printStr)
        except PermissionError:
            printStr = '\nError: unable to write to bomcheck.xlsx\n'
            printStrs += printStr
            print(printStr)

    if c == False:
        if title_dfsw and title_dfmerged:
            return title_dfsw[0][1], title_dfmerged[0][1]
        elif title_dfsw:
            return title_dfsw[0][1], None
        elif title_dfmerged:
            return None, title_dfmerged[0][1]
        else:
            return None, None


def get_fnames(fn, followlinks=False):
    ''' Interpret fn to get a list of filenames based on fn's value.  
    
    Parameters
    ----------
    fn: str or list
        fn is a filename or a list of filenames.  A filename can also be a
        directory name.  Example 1, strings: "C:/myfile_.xlsx", "C:/dirname", 
        "['filename1', 'filename2', 'dirname1' ...]". Example 2, list:
        ["filename1", "filename2", "dirname1", "dirname2"].  When a a directory
        name is given, filenames are gathered from that directory and from 
        subdirectories thereof.
    followlinks: Boolean, optional
        If True, follow symbolic links. If a link is to a direcory, then
        filenames are gathered from that directory and from subdirectories
        thereof.  The default is False.  

    Returns
    -------
    _fn: list
        A list of filenames, e.g. ["filename1", "filename2", ...].  Each value
        in the list is a string.  Each string is the name of a file.  The
        filename can be a pathname, e.g. "C:/dir1/dir2/filename".  The
        filenames can have any type of extension.
    '''
    if isinstance(fn, str) and fn.startswith('[') and fn.endswith(']'):
            fn = eval(fn)  # if fn a string like "['fname1', 'fname2', ...]", convert to a list
    elif isinstance(fn, str):
        fn = [fn]   # fn a string like "fname1", convert to a list like [fname1]
        
    _fn1 = [] 
    for f in fn:
        _fn1 += glob.glob(f)
        
    _fn2 = []    # temporary holder
    for f in _fn1:
        if followlinks==True and os.path.islink(f) and os.path.exists(f):
            _fn2 += get_fnames(os.readlink(f))              
        elif os.path.isdir(f):  # if a dir gather all filenames in dirs and subdirs thereof
            for root, dirs, files in os.walk(f, followlinks=followlinks):
                for filename in files:
                  _fn2.append(os.path.join(root, filename))  
        else:
            _fn2.append(f) 
            
    return _fn2


def make_csv_file_stable(filename):
    ''' Except for any commas in a parts DESCRIPTION, replace all commas
    in a csv file with a $ character.  Commas will sometimes exist in a
    DESCRIPTION field, e.g, "TANK, 60GAL".  But commas are intended to be field
    delimeters; commas in a DESCRIPTION field are not.  Excess commas in
    a line from a csv file will cause a program crash.  Remedy: change those 
    commas meant to be delimiters to a dollor sign character, $.
        
    Parmeters
    =========

    filename: string
        Name of SolidWorks csv file to process.

    Returns
    =======

    out: list
        A list of all the lines (rows) in filename is returned.  Commas in each
        line are changed to dollar signs except for any commas in the
        DESCRIPTION field.
    '''
    with open(filename, encoding="ISO-8859-1") as f:
        data1 = f.readlines()
    # n1 = number of commas in 2nd line of filename (i.e. where column header
    #      names located).  This is the no. of commas that should be in each row.
    n1 = data1[1].count(',')
    n2 = data1[1].upper().find('DESCRIPTION')  # locaton of the word DESCRIPTION within the row.
    n3 = data1[1][:n2].count(',')  # number of commas before the word DESCRIPTION
    data2 = list(map(lambda x: x.replace(',', '$') , data1)) # replace ALL commas with $
    data = []
    for row in data2:
        n4 = row.count('$')
        if n4 != n1:
            # n5 = location of 1st ; character within the DESCRIPTION field
            #      that should be a , character
            n5 = row.replace('$', '?', n3).find('$')
            # replace those ; chars that should be , chars in the DESCRIPTION field:
            data.append(row[:n5] + row[n5:].replace('$', ',', (n4-n1))) # n4-n1: no. commas needed
        else:
            data.append(row)
    return data


def gatherBOMs_from_fnames(filename):
    ''' Gather all SolidWorks and SyteLine BOMs derived from "filename".
    "filename" can be a string containing wildcards, e.g. 6890-085555-*, which
    allows the capture of multiple files; or "filename" can be a list of such
    strings.  These files (BOMs) will be converted to Pandas DataFrame objects.

    Only files prefixed with _sw.xlsx, _sw.csv, _sl.xlsx, or _sl.csv will be
    chosen; others are discarded.  These files will then be converted into two
    python dictionaries.  One dictionary will contain SolidWorks BOMs only, and
    the other will contain only SyteLine BOMs.

    If a filename has a BOM containing a multiple level BOM, then the 
    subassembly BOMs will be extracted from that BOM and be added to the 
    dictionaries.

    calls: make_csv_file_stable, deconstructMultilevelBOM, test_for_missing_columns

    Parmeters
    =========

    filename: list
        List of filenames to be analyzed.

    Returns
    =======

    out: tuple
        The output tuple contains three items.  The first is the directory
        corresponding to the first file in the filename list.  If this
        directory is an empty string, then it refers to the current working
        directory.  The remainder of the tuple items are two python 
        dictionaries. The first dictionary contains SolidWorks BOMs, and the 
        second contains SyteLine BOMs.  The keys for these two dictionaries 
        are part nos. of assemblies derived from the filenames (e.g. 085952 
        from 085953_sw.xlsx), or derived from subassembly part numbers of a
        file containing multilevel BOM.
    '''
    dirname = '.'  # to this will assign the name of 1st directory a _sw is found in 
    global printStrs
    swfilesdic = {}
    slfilesdic = {}
    for f in filename:  # from filename extract all _sw & _sl files and put into swfilesdic & slfilesdic
        i = f.rfind('_')
        if f[i:i+4].lower() == '_sw.' or f[i:i+4].lower() == '_sl.':
            dname, fname = os.path.split(f)
            k = fname.rfind('_')
            fntrunc = fname[:k]  # Name of the sw file, excluding path, and excluding _sw.xlsx
            if f[i:i+4].lower() == '_sw.' and fname[0] != '~': # Ignore names like ~$085637_sw.xlsx
                swfilesdic.update({fntrunc: f})
                if dirname == '.':
                    dirname = os.path.dirname(os.path.abspath(f)) # use 1st dir where a _sw file is found to put bomcheck.xlsx
            elif f[i:i+4].lower() == '_sl.' and fname[0] != '~':
                slfilesdic.update({fntrunc: f})    
    swdfsdic = {}  # for collecting SW BOMs to a dic
    for k, v in swfilesdic.items():
        try:
            _, file_extension = os.path.splitext(v)
            if file_extension.lower() == '.csv' or file_extension.lower() == '.txt':
                data = make_csv_file_stable(v)
                temp = tempfile.TemporaryFile(mode='w+t')
                for d in data:
                    temp.write(d)
                temp.seek(0)
                df = pd.read_csv(temp, na_values=[' '], skiprows=1, sep='$',
                                 encoding='iso8859_1', engine='python',
                                 dtype = {'ITEM NO.': 'str'})
                temp.close()
            elif file_extension.lower() == '.xlsx' or file_extension.lower() == '.xls':
                df = pd.read_excel(v, na_values=[' '], skiprows=1)
                colnames = []
                for colname in df.columns:  # rid colname of '\n' char if exists
                    colnames.append(colname.replace('\n', ''))
                df.columns = colnames
            if not test_for_missing_columns('sw', df, k):
                swdfsdic.update(deconstructMultilevelBOM(df, 'sw', k))
        except:
            printStr = '\nError processing file: ' + v + '\nIt has been excluded from the BOM check.\n'
            printStrs += printStr
            print(printStr)
    sldfsdic = {}  # for collecting SL BOMs to a dic
    for k, v in slfilesdic.items():
        try:
            _, file_extension = os.path.splitext(v)
            if file_extension.lower() == '.csv' or file_extension.lower() == '.txt':
                try:
                    df = pd.read_csv(v, na_values=[' '], engine='python',
                                     encoding='utf-16', sep='\t')
                except UnicodeError:
                    printStr = ("\nError. Probable cause: This program expects Unicode text encoding from\n"
                                "a csv file.  The file " + v + " does not have this.  The\n"
                                "correct way to achieve a functional csv file is:\n\n"
                                '    From Excel, save the file as type “Unicode Text (*.txt)”, and then\n'
                                '    change the file extension from txt to csv.\n\n'
                                "On the other hand you can use an Excel file (.xlsx) instead of a csv file.\n")
                    printStrs += printStr
                    print(printStr)
                    sys.exit(1)
            elif file_extension.lower() == '.xlsx' or file_extension.lower == '.xls':
                df = pd.read_excel(v, na_values=[' '])
            if not test_for_missing_columns('sl', df, k):
                sldfsdic.update(deconstructMultilevelBOM(df, 'sl', k))
        except:
            printStr = '\nError processing file: ' + v + '\nIt has been excluded from the BOM check.\n'
            printStrs += printStr
            print(printStr)
    try:
        df = pd.read_clipboard(engine='python', na_values=[' '])
        if not test_for_missing_columns('sl', df, 'BOMfromClipboard', printerror=False):
            sldfsdic.update(deconstructMultilevelBOM(df, 'sl', 'TOPLEVEL'))
    except:
        pass
    if os.path.islink(dirname):
        dirname = os.readlink(dirname)
    return dirname, swdfsdic, sldfsdic


def test_for_missing_columns(bomtype, df, pn, printerror=True):
    ''' SolidWorks and SyteLine BOMs require certain essential columns to be
    present.  This function looks at those BOMs that are within df to see if
    any required columns are missing.  If found, print to screen.

    calls: test_alternative_column_names

    Parameters
    ==========

    bomtype: string
        "sw" or "sl"

    df: Pandas DataFRame
        A SW or SL BOM

    pn: string
        Part number of the BOM

    Returns
    =======

    out: bool
        True if BOM afoul.  Otherwise False.
    '''
    global printStrs
    if bomtype == 'sw':
        required_columns = [('QTY', 'QTY.'), 'DESCRIPTION',
                            ('PART NUMBER', 'PARTNUMBER', 'Part Number')]
    else: # 'for sl bom'
        required_columns = [('Qty', 'Quantity', 'Qty Per'),
                            ('Material Description', 'Description'),
                            ('U/M', 'UM'), ('Item', 'Material')]
    missing = []
    for r in required_columns:
        if isinstance(r, str) and r not in df.columns:
            missing.append(r)
        elif isinstance(r, tuple) and test_alternative_column_names(r, df.columns):
            missing.append(' or '.join(test_alternative_column_names(r, df.columns)))
    if missing and bomtype=='sw' and printerror:
        printStr = ('\nEssential BOM columns missing.  SolidWorks requires a BOM header\n' +
              'to be in place.  This BOM will not be processed:\n\n' +
              '    missing: ' + ' ,'.join(missing) +  '\n' +
              '    missing in: ' + pn + '\n') 
        printStrs += printStr
        print(printStr)
        return True
    elif missing and printerror:
        printStr = ('\nEssential BOM columns missing.  This BOM will not be processed:\n' +
                    '    missing: ' + ' ,'.join(missing) +  '\n\n' +
                    '    missing in: ' + pn + '\n')
        printStrs += printStr
        print(printStr)
        return True
    elif missing:
        return True
    else:
        return False


def test_alternative_column_names(tpl, lst):
    ''' tpl contains alternative names for a required column in a bom.  If 
    none of the names in tpl match a name in lst, return tpl so that the
    user can be notified that one of those alternative names should have been
    present.  On the other hand, if a match was found, return None.
    
    Parameters
    ==========
    tpl: tuple
        Each item of tpl is a string.  Each item is an alternative column name,
        e.g. ("Qty", "Quantity")
       
    lst: list
        A list of the required columns that a bom must have in order for a bom
        check to be correctly completed.
        
    Returns
    =======
    out: tpl|None
        If no match found, return the same tuple, tpl, that was an input
        parameter.  Else return None
    '''
    flag = True
    for t in tpl:
        if t in lst:
            flag = False  # A required column name was found in the tuple, so good to proceed with bom check
    if flag:
        return tpl  # one of the tuple items is a required column.  Report that one or the other is missing


def deconstructMultilevelBOM(df, source, top='TOPLEVEL'):
    ''' If the BOM is a multilevel BOM, pull out the BOMs thereof; that is,
    pull out the main assembly and the subassemblies thereof.  These
    assys/subassys are placed in a python dictionary and returned.  If df is
    a single level BOM, a dictionary with one item is returned.

    For this function to pull out subassembly BOMs from a SyteLine BOM, the
    column named Level must exist in the SyteLine BOM.  It contains integers
    indicating the level of a subassemby within the BOM; e.g. 1, 2, 3, 2, 3,
    3, 3, 4, 4, 2.  Only multilevel SyteLine BOMs contain this column.
    On the other hand for this function to  pull out subassemblies from a
    SolidWorks BOM, the column ITEM NO. must exist and contain values that
    indicate which values are subassemblies; e.g, with item numbers like
    "1, 2, 2.1, 2.2, 3, 4, etc., items 2.1 and 2.2 are  members of the item 
    number 2 subassembly.

    Parmeters
    =========

    df: Pandas DataFrame
        The DataFrame is that of a SolidWorks or SyteLine BOM.
        
    source: string
        Choices for source are "sw" or "sl".  That is, is the BOM being
        deconstructed from SolidWorks or SyteLine.

    top: string
        Top level part number.  This number is automatically generated by the
        bomcheck program in two ways:  1. If df originated from a SolidWorks 
        BOM or from a single level SyteLine  BOM, then “top” is derived from 
        the filename; e.g. 091828 from the filename 091828_sw.xlsx.  2. If df
        originated from a multilevel BOM, then it has a column named “Level”
        (i.e. the level of subassemblies and parts within subassemblies
        relative to the main, top, assembly part number).  In this case the
        part number associated with level "0" is assigned to "top".

    Returns
    =======

    out: python dictionary
        The dictionary has the form {assypn1: BOM1, assypn2: BOM2, ...},
        where assypn1, assypn2, etc. are string objects and are the part
        numbers for BOMs; and BOM1, BOM2, etc. are pandas DataFrame objects
        that pertain to those part numbers.
    '''
    p = None
    # Find the column name that contains the pns.  This column name varies
    # depending on whether it came from SW or SL, and ,if from SL, from where
    # in SL the the BOM come from.
    for pncolname in ['Item', 'Material', 'PARTNUMBER', 'PART NUMBER', 'Part Number']:
        if pncolname in df.columns:
            ptno = pncolname
    df[ptno] = df[ptno].astype('str').str.strip() # make sure pt nos. are "clean"
    df[ptno].replace('', 'pn missing', inplace=True)
    values = {'QTY':0, 'QTY.':0, 'Qty':0, 'Quantity':0, 'LENGTH':0, 'L':0,
              'DESCRIPTION': 'description missing',
              'Material Description': 'description missing',
              'PART NUMBER': 'pn missing', 'PARTNUMBER': 'pn missing',
              'Part Number':'pn missing', 'Item': 'pn missing', 
              'Material':'pn missing'}
    df.fillna(value=values, inplace=True)
    if 'Level' in df.columns:  # if present, is a SL BOM.  Make sure top='TOPLEVEL'
        top = 'TOPLEVEL'
    # if BOM is from SW, generate a column named Level based on the column named
    # ITEM NO.  This column constains values like 1, 2, 3, 3.1, 3.1.1, 3.1.2,
    # 3.2, etc. where item 3.1 is a member of subassy 3.
    if 'ITEM NO.' in df.columns:  # is a sw bom
        df['ITEM NO.'] = df['ITEM NO.'].astype('str')
        df['ITEM NO.'] = df['ITEM NO.'].str.replace('.0', '') # stop 5.0 etc slipping through
        df['Level'] = df['ITEM NO.'].str.count('\.')
    elif 'Level' not in df.columns:  # is a single level sl bom
        df['Level'] = 0
    # Take the the column named "Level" and create a new column: "Level_pn".
    # Instead of the level at which a part exists within an assembly, like
    # "Level" which contains integers like [0, 1, 2, 2, 1], "Level_pn" contains
    # the parent part no. of the part at a particular level, e.g.
    # ['TOPLEVEL', '068278', '2648-0300-001', '2648-0300-001', '068278']
    lvl = 0
    level_pn = []  # storage of pns of parent assy/subassy of the part at rows 0, 1, 2, 3, ...
    assys = []  # storage of all assys/subassys found (stand alone parts ignored)
    for item, row in df.iterrows():
        if row['Level'] == 0:
            poplist = []
            level_pn.append(top)
            if top != "TOPLEVEL":
                assys.append(top)
            elif 'Description' in df.columns and lvl == 0:
                excelTitle.append((row[ptno], row['Description'])) # info for a global variable
        elif row['Level'] > lvl:
            if p in assys:
                poplist.append('repeat')
            else:
                assys.append(p)
                poplist.append(p)
            level_pn.append(poplist[-1])
        elif row['Level'] == lvl:
            level_pn.append(poplist[-1])
        elif row['Level'] < lvl:
            i = row['Level'] - lvl  # how much to pop.  i is a negative number.
            poplist = poplist[:i]   # remove, i.e. pop, i items from end of list
            level_pn.append(poplist[-1])
        p = row[ptno]
        lvl = row['Level']
    df['Level_pn'] = level_pn
    # collect all assys/subassys within df and return a dictionary.  keys
    # of the dictionary are pt. numbers of assys/subassys.  
    dic_assys = {}
    for k in assys:
        dic_assys[k.upper()] = df[df['Level_pn'] == k]  # "upper()" added 3/9/20
    return dic_assys


def create_um_factors(ser, from_um='inch', to_um='feet'):
    ''' From ser derive multiplication factors that will convert length values
    with a particular unit of measure (um) to to_um.  Some items of ser have a
    um values appended to it; for example 1105mm.  In this case the factor will
    be based on that um.  If no um is specified, it's derived from from_um. 

    Parmeters
    =========
    
    ser:  Pandas Series
        The data from the column that contains lengths from a SolidWorks BOM.

    from_um: str
        Use this unit of measure to convert from unless otherwised specified.  
        Valid units of measure: "inch", "feet", "yard", "millimeter", 
        "centimeter", "meter" (or abreviations thereof, e.g. mm).
        Default: "inch".

    to_um: str
        Convert to this unit of measure.  The same valid units of measure
        listed above apply.  Default: "feet"
    
    Returns
    =======

    out: list   
        multiplcation factors (list of floats)          
    '''
    factorpool = (('in', 1/12),      ('ft', 1.0),      ('mm', 1/(25.4*12)),
                  ('"', 1/12),       ("'", 1.0),       ('milli', 1/(25.4*12)),
                  (chr(8221), 1/12), (chr(8217), 1.0), ('cm', 10/(25.4*12)),
                  ('yard', 3.0),     ('foot', 1.0),    ('centi', 10/(25.4*12)),
                  ('yd', 3.0),       ('feet', 1.0),    ('m', 1000/(25.4*12)))
 
    # determine from_um_factor
    for k, v in factorpool:
        if k in from_um.lower():
            from_um_factor = v
            break
    else:
        from_um_factor = 1/12

    # determine to_um_factor
    for k, v in factorpool:
        if k in to_um.lower():
            to_um_factor = 1/v
            break
    else:
        to_um_factor = 1.0

    lengths = ser.fillna(0).tolist()
    factors = []
    for length in lengths:
        if isinstance(length, str):  # if UM explicitly stated, e.g. "34.3 MM"
           for k, v in factorpool:
                if k in length.lower():
                    from_factor = v
                    break
           else:
               from_factor = from_um_factor
        elif isinstance(length, float) or isinstance(length, int):
            from_factor = from_um_factor
        else:
            from_factor = 0
        factors.append(from_factor * to_um_factor)
        
    return factors


def is_in(find, xcept, series):   # except is a reserved python word so can't use it
    '''Argument "find" is a list of strings that are glob expressions.  The 
    Pandas Series "series" will be evaluated to see if any members of find
    exists as substrings within each member of series.  Glob expressions are
    strings like '3086-*-025' or *2020*.  '3086-*-025' for example will match 
    '3086-0050-025' and '3086-0215-025'.
    
    The output of the is_in function is a Pandas Series.  Each member of the
    Series is True or False depending on whether a substring has been found
    or not.
        
    xcept is a list of exceptions to those in the find list.  For example, if
    '3086-*-025' is in the find list and '3086-3*-025' is in the xcept list,
    then series members like '3086-0515-025' or '3086-0560-025' will return
    a True, and '3086-3050-025' or '3086-3060-025' will return a False.
    
    For reference, glob expressions are explained at:
    https://en.wikipedia.org/wiki/Glob_(programming)
    
    Parmeters
    =========
    
    find: string or list of strings
        Items to search for
        
    xcept: string or list of strings
        Exceptions to items to search for

    series:  Pandas Series
       Series to search

    Returns
    =======

    out: Pandas Series, dtype: bool
        Each item is True or False depending on whether a match was found or not
    '''
    if not isinstance(find, list):
        find = [find]
    if not isinstance(xcept, list) and xcept:
        xcept = [xcept]
    elif isinstance(xcept, list):
        pass
    else:
        xcept = []
    series = series.astype(str).str.strip()  # ensure that all elements are strings & strip whitespace from ends
    find2 = []
    for f in find:
        find2.append('^' + fnmatch.translate(str(f)) + '$')  # reinterpret user input with a regex expression
    xcept2 = []
    for x in xcept:  # exceptions is also a global variable
        xcept2.append('^' +  fnmatch.translate(str(x))  + '$')
    if find2 and xcept2:
        filtr = (series.str.contains('|'.join(find2)) &  ~series.str.contains('|'.join(xcept2)))
    elif find2:
        filtr = series.str.contains('|'.join(find2))
    else:
        filtr = pd.Series([False]*series.size)
    return filtr


def convert_sw_bom_to_sl_format(df):
    '''Take a SolidWorks BOM and restructure it to be like that of a SyteLine
    BOM.  That is, the following is done:

    - For parts with a length provided, the length is converted from from_um to 
      to_um (see the function main for a definition of these variables).
      Typically the unit of measure in a SolidWorks BOM is inches, and in 
      SyteLine, feet.
    - If the part is a pipe or beam and it is listed multiple times in the BOM,
      the BOM is updated so that only one listing is shown and the lengths
      of the removed listings are added to the remaining listing.
    - Similar to above, parts such as pipe nipples will show up more that
      once on a BOM.  Remove the excess listings and add the quantities of
      the removed listings to the remaining listing.
    - If global variable cfg['drop'] is set to True, off the shelf parts, which 
      are usually pipe fittings, are removed from the SolidWorks BOM.  (As a
      general rule, off-the-shelf parts are not shown on SyteLine BOMs.)  The 
      list that  governs this rule is in a file named drop.py.  Other part nos.
      may be added to this list as required.  (see the function set_globals
      for more information)
    - Column titles are changed to match those of SyteLine and thus will allow
      merging to a SyteLine BOM.
      
    calls: create_um_factors

    Parmeters
    =========

    df: Pandas DataFrame
        SolidWorks DataFrame object to process.

    Returns
    =======

    out: pandas DataFrame
        A SolidWorks BOM with a structure like that of SyteLine.

    \u2009
    '''
    df.rename(columns={'PARTNUMBER':'Item', 'PART NUMBER':'Item', 'Part Number':'Item',
                       'L': 'LENGTH', 'Length':'LENGTH',
                       'DESCRIPTION': 'Description', 'QTY': 'Q', 'QTY.': 'Q',}, inplace=True)

    if 'LENGTH' in df.columns:  # convert lengths to other unit of measure, i.e. to_um
        factors = create_um_factors(df['LENGTH'], from_um=cfg['from_um'], to_um=cfg['to_um'])
        qtys = df['Q']
        lengths = df['LENGTH'].replace('[^\d.]', '', regex=True).astype(float)               
        discard_length_filter = ~is_in(cfg['discard_length'], [], df['Item'])
        df['LENGTH'] = lengths * qtys * factors * discard_length_filter
        filtr2 = df['LENGTH'] >= 0.00001
        df['Q'] = df['Q']*(~filtr2) + df['LENGTH']  # move lengths to the Qty column
        df['U'] = filtr2.apply(lambda x: 'FT' if x else 'EA')  # set the unit of measure
    else:
        df['U'] = 'EA'  # if no length colunm exists then set all units of measure to EA
    
    df = df.reindex(['Op', 'WC','Item', 'Q', 'Description', 'U'], axis=1)  # rename and/or remove columns
    dd = {'Q': 'sum', 'Description': 'first', 'U': 'first'}   # funtions to apply to next line
    df = df.groupby('Item', as_index=False).aggregate(dd).reindex(columns=df.columns)
    df['Q'] = round(df['Q'], cfg['accuracy'])

    if cfg['drop']==True:
        filtr3 = is_in(cfg['drop'], cfg['exceptions'], df['Item'])
        df.drop(df[filtr3].index, inplace=True)

    df['WC'] = 'PICK'    # WC is a standard column shown in a SL BOM.
    df['Op'] = str(10)   # Op is a standard column shown in a SL BOM, usually set to 10  
    df.set_index('Op', inplace=True)

    return df


def check_a_sw_bom_to_a_sl_bom(dfsw, dfsl):
    '''This function takes in one SW BOM and one SL BOM and then merges them.
    This merged BOM shows the BOM check allowing differences between the
    SW and SL BOMs to be easily seen.

    A set of columns in the output are labeled i, q, d, and u.  Xs at a row in
    any of these columns indicate something didn't match up between the SW
    and SL BOMs.  An X in the i column means the SW and SL Items (i.e. pns)
    don't match.  q means quantity, d means description, u means unit of
    measure.

    Parmeters
    =========

    dfsw: Pandas DataFrame
        A DataFrame of a SolidWorks BOM

    dfsl: Pandas DataFrame
        A DataFrame of a SyteLine BOM

    Returns
    =======

    df_merged: Pandas DataFrame
        df_merged is a DataFrame that shows a side-by-side comparison of a
        SolidWorks BOM to a SyteLine BOM.

    \u2009
    '''
    global printStrs
    if not str(type(dfsw))[-11:-2] == 'DataFrame':
        printStr = '\nProgram halted.  A fault with SolidWorks DataFrame occurred.\n'
        printStrs += printStr
        print(printStr)
        sys.exit()

    # A BOM can be derived from different locations within SL.  From one location
    # the `Item` is the part number.  From another `Material` is the part number.
    # When `Material` is the part number, a useless 'Item' column is also present.
    # It causes the bomcheck program confusion and the program crashes.  Thus a fix:
    if 'Item' in dfsl.columns and 'Material' in dfsl.columns:
        dfsl.drop(['Item'], axis=1, inplace=True)  # the "drop" here is not that in the cfg dictionary
    if 'Description' in dfsl.columns and 'Material Description' in dfsl.columns:
        dfsl.drop(['Description'], axis=1, inplace=True)
    dfsl.rename(columns={'Material':'Item', 'Quantity':'Q',
                         'Material Description':'Description', 'Qty':'Q', 'Qty Per': 'Q',
                         'U/M':'U', 'UM':'U', 'Obsolete Date': 'Obsolete'}, inplace=True)

    if 'Obsolete' in dfsl.columns:  # Don't use any obsolete pns (even though shown in the SL BOM)
        filtr4 = dfsl['Obsolete'].notnull()
        dfsl.drop(dfsl[filtr4].index, inplace=True)    # https://stackoverflow.com/questions/13851535/how-to-delete-rows-from-a-pandas-dataframe-based-on-a-conditional-expression

    # When pns are input into SyteLine, all the characters of pns should
    # be upper case.  But on occasion people have mistakently used lower case.
    # Correct this and report what pns have been in error.
    x = dfsl['Item'].copy()
    dfsl['Item'] = dfsl['Item'].str.upper()  # make characters upper case
    x_bool =  x != dfsl['Item']
    x_lst = [i for i in list(x*x_bool) if i]
    if x_lst:
        printStr = ("\nLower case part nos. in SyteLine's BOM have been converted " +
                    "to upper case for \nthis BOM check:\n")
        printStrs += printStr
        print(printStr)
        for y in x_lst:
            printStr = '    ' + y + '  changed to  ' + y.upper() + '\n'
            printStrs += printStr
            print(printStr)

    dfmerged = pd.merge(dfsw, dfsl, on='Item', how='outer', suffixes=('_sw', '_sl') ,indicator=True)
    dfmerged.sort_values(by=['Item'], inplace=True)
    filtrI = dfmerged['_merge'].str.contains('both')  # this filter determines if pn in both SW and SL
    filtrQ = abs(dfmerged['Q_sw'] - dfmerged['Q_sl']) < .0051  # If diff in qty greater than this value, show X
    filtrM = dfmerged['Description_sw'].str.split() == dfmerged['Description_sl'].str.split()
    filtrU = dfmerged['U_sw'].astype('str').str.strip() == dfmerged['U_sl'].astype('str').str.strip()
    chkmark = '-'
    err = 'X'

    dfmerged['i'] = filtrI.apply(lambda x: chkmark if x else err)     # X = Item not in SW or SL
    dfmerged['q'] = filtrQ.apply(lambda x: chkmark if x else err)     # X = Qty differs btwn SW and SL
    dfmerged['d'] = filtrM.apply(lambda x: chkmark if x else err)     # X = Mtl differs btwn SW & SL
    dfmerged['u'] = filtrU.apply(lambda x: chkmark if x else err)     # X = U differs btwn SW & SL
    dfmerged['i'] = ~dfmerged['Item'].duplicated(keep=False) * dfmerged['i'] # duplicate in SL? i-> blank
    dfmerged['q'] = ~dfmerged['Item'].duplicated(keep=False) * dfmerged['q'] # duplicate in SL? q-> blank
    dfmerged['d'] = ~dfmerged['Item'].duplicated(keep=False) * dfmerged['d'] # duplicate in SL? d-> blank
    dfmerged['u'] = ~dfmerged['Item'].duplicated(keep=False) * dfmerged['u'] # duplicate in SL? u-> blank

    dfmerged = dfmerged[['Item', 'i', 'q', 'd', 'u', 'Q_sw', 'Q_sl',
                         'Description_sw', 'Description_sl', 'U_sw', 'U_sl']]
    dfmerged.fillna('', inplace=True)
    dfmerged.set_index('Item', inplace=True)
    return dfmerged


def collect_checked_boms(swdic, sldic):
    ''' Match SolidWorks assembly nos. to those from SyteLine and then merge
    their BOMs to create a BOM check.  For any SolidWorks BOMs for which no
    SyteLine BOM was found, put those in a separate dictionary for output.

    calls: convert_sw_bom_to_sl_format, check_a_sw_bom_to_a_sl_bom

    Parameters
    ==========

    swdic: dictionary
        Dictinary of SolidWorks BOMs.  Dictionary keys are strings and they
        are of assembly part numbers.  Dictionary values are pandas DataFrame
        objects which are BOMs for those assembly pns.

    sldic: dictionary
        Dictinary of SyteLine BOMs.  Dictionary keys are strings and they
        are of assembly part numbers.  Dictionary values are pandas DataFrame
        objects which are BOMs for those assembly pns.

    Returns
    =======

    out: tuple
        The output tuple contains two values: 1.  Dictionary containing SolidWorks
        BOMs for which no matching SyteLine BOM was found.  The BOMs have been
        converted to a SyteLine like format.  Keys of the dictionary are assembly
        part numbers.  2.  Dictionary of merged SolidWorks and SyteLine BOMs, thus
        creating a BOM check.  Keys for the dictionary are assembly part numbers.
    '''
    lone_sw_dic = {}  # sw boms with no matching sl bom found
    combined_dic = {}   # sl bom found for given sw bom.  Then merged
    for key, dfsw in swdic.items():
        if key in sldic:
            combined_dic[key] = check_a_sw_bom_to_a_sl_bom(convert_sw_bom_to_sl_format(dfsw), sldic[key])
        else:
            lone_sw_dic[key + '_sw'] = convert_sw_bom_to_sl_format(dfsw)
    return lone_sw_dic, combined_dic


def concat_boms(title_dfsw, title_dfmerged):
    ''' Concatenate all the SW BOMs into one long list (if there are any SW
    BOMs without a matching SL BOM being found), and concatenate all the merged
    SW/SL BOMs into another long list.

    Each BOM, before concatenation, will get a new column added: assy.  Values
    for assy will all be the same for a given BOM: the pn (a string) of the BOM.
    BOMs are then concatenated.  Finally Pandas set_index function will applied
    to the assy column resulting in the ouput being categorized by the assy pn.


    Parameters
    ==========

    title_dfsw: list
        A list of tuples, each tuple has two items: a string and a DataFrame.
        The string is the assy pn for the DataFrame.  The DataFrame is that
        derived from a SW BOM.

    title_dfmerged: list
        A list of tuples, each tuple has two items: a string and a DataFrame.
        The string is the assy pn for the DataFrame.  The DataFrame is that
        derived from a merged SW/SL BOM.

    Returns
    =======

    out: tuple
        The output is a tuple comprised of two items.  Each item is a list.
        Each list contains one item: a tuple.  The structure has the form:

            ``out = ([("SW BOMS", DataFrame1)], [("BOM Check", DataFrame2)])``

    Where...    
        "SW BOMS" is the title. (when c=True in the bomcheck function, the
        title will be an assembly part no.).  
        DataFrame1 = SW BOMs that have been concatenated together.

        "BOM Check" is another title.  
        DataFrame2 = Merged SW/SL BOMs that have been concatenated together.
    '''
    dfswDFrames = []
    dfmergedDFrames = []
    swresults = []
    mrgresults = []
    for t in title_dfsw:
        t[1]['assy'] = t[0]
        dfswDFrames.append(t[1])
    for t in title_dfmerged:
        t[1]['assy'] = t[0]
        dfmergedDFrames.append(t[1])
    if dfswDFrames:
        dfswCCat = pd.concat(dfswDFrames).reset_index()
        swresults.append(('SW BOMs', dfswCCat.set_index(['assy', 'Op']).sort_index(axis=0)))
    if dfmergedDFrames:
        dfmergedCCat = pd.concat(dfmergedDFrames).reset_index()
        mrgresults.append(('BOM Check', dfmergedCCat.set_index(['assy', 'Item']).sort_index(axis=0)))
    return swresults, mrgresults


def export2excel(dirname, filename, results2export, uname):
    '''Export to an Excel file the results of all the BOM checks.

    calls: len2, autosize_excel_columns, autosize_excel_column_df, definefn...
    (these functions are defined internally within the export2exel function)

    Parmeters
    =========

    dirname: string
        The directory to which the Excel file that this function generates
        will be sent.

    filename: string
        The name of the Excel file.

    results2export: list
        List of tuples.  The number of tuples in the list varies according to
        the number of BOMs analyzed, and if bomcheck's c (sheets) option was
        invoked or not.  Each tuple has two items.  The  first item of a tuple
        is a string and is the name to be assigned to the tab of the Excel
        worksheet.  It is typically an assembly part number.  The second  item
        is a BOM (a DataFrame object).  The list of tuples consists of:

        *1* SolidWorks BOMs that have been converted to SyteLine format.  SW
        BOMs will only occur if no corresponding SL BOM was found.

        *2* Merged SW/SL BOMs.

        That is, if c=1, the form will be:

        - [('2730-2019-544_sw', df1), ('080955', df2),
          ('6890-080955-1', df3), ('0300-2019-533', df4), ...]

        and if c=0, the form will be:

        - [('SW BOMs', dfForSWboms), ('BOM Check', dfForMergedBoms)]


    uname : string
        Username to attach to the footer of the Excel file.

    Returns
    =======

    out: None
        An Excel file will result named bomcheck.xlsx.

     \u2009
    '''
    global printStrs
    
    def len2(s):
        ''' Extract from within a string either a decimal number truncated to two
        decimal places, or an int value; then return the length of that substring.
        Why used?  Q_sw, Q_sl, Q, converted to string, are on ocasion something
        like 3.1799999999999997.  This leads to wrong length calc using len.'''
        match = re.search(r"\d*\.\d\d|\d+", s)
        if match:
            return len(match.group())
        else:
            return 0

    def autosize_excel_columns(worksheet, df):
        ''' Adjust column width of an Excel worksheet (ref.: https://stackoverflow.com/questions/
            17326973/is-there-a-way-to-auto-adjust-excel-column-widths-with-pandas-excelwriter)'''
        autosize_excel_columns_df(worksheet, df.index.to_frame())
        autosize_excel_columns_df(worksheet, df, offset=df.index.nlevels)

    def autosize_excel_columns_df(worksheet, df, offset=0):
        for idx, col in enumerate(df):
            x = 1 # add a little extra width to the Excel column
            if df.columns[idx] in ['i', 'q', 'd', 'u']:
                x = 0
            series = df[col]
            if df.columns[idx][0] == 'Q':
                max_len = max((
                    series.astype(str).map(len2).max(),
                    len(str(series.name))
                )) + x
            else:
                max_len = max((
                    series.astype(str).map(len).max(),
                    len(str(series.name))
                )) + x
            worksheet.set_column(idx+offset, idx+offset, max_len)

    def definefn(dirname, filename, i=0):
        ''' If bomcheck.xlsx slready exists, return bomcheck(1).xlsx.  If that
        exists, return bomcheck(2).xlsx...  and so forth.'''
        global printStrs
        d, f = os.path.split(filename)
        f, e = os.path.splitext(f)
        if d:
            dirname = d   # if user specified a directory, use it instead
        if e and not e.lower()=='.xlsx':
            printStr = '\n(Output filename extension needs to be .xlsx' + '\nProgram aborted.\n'
            printStrs += printStr
            print(printStr)
            sys.exit(0)
        else:
            e = '.xlsx'
        if i == 0:
            fn = os.path.join(dirname, f+e)
        else:
            fn = os.path.join(dirname, f+ '(' + str(i) + ')'+e)
        if os.path.exists(fn):
            return definefn(dirname, filename, i+1)
        else:
            return fn

    fn = definefn(dirname, filename)

    if uname != 'unknown':
        username = uname
    elif os.getenv('USERNAME'):
        username = os.getenv('USERNAME')  # Works only on MS Windows
    else:
        username = 'unknown'

    # ref: https://howchoo.com/g/ywi5m2vkodk/working-with-datetime-objects-and-timezones-in-python
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
    localtime_now = utc_now.astimezone(pytz.timezone(cfg['timezone']))
    time = localtime_now.strftime("%m-%d-%Y %I:%M %p")

    comment1 = 'This workbook created ' + time + ' by ' + username + '.  '
    comment2 = 'The drop list was not employed for this BOM check.  '
    bomfooter = '&LCreated ' + time + ' by ' + username + '&CPage &P of &N'
    if cfg['drop']:
        comment2 = ('The drop list was employed for this BOM check:  '
                    + 'drop = ' + str(cfg['drop']) +  ', exceptions = ' + str(cfg['exceptions']))
        bomfooter = bomfooter + '&Rdrop: yes'

    if excelTitle and len(excelTitle) == 1:
        bomheader = '&C&A: ' + excelTitle[0][0] + ', ' + excelTitle[0][1]
    else:
        bomheader = '&C&A'
        
    with pd.ExcelWriter(fn) as writer:
        for r in results2export:
            sheetname = r[0]
            df = r[1]
            if not df.empty:                        #TODO: some test code
                df.to_excel(writer, sheet_name=sheetname)
                worksheet = writer.sheets[sheetname]  # pull worksheet object
                autosize_excel_columns(worksheet, df)
                worksheet.set_header(bomheader)  # see: https://xlsxwriter.readthedocs.io/page_setup.html
                worksheet.set_footer(bomfooter)
                worksheet.set_landscape()
                worksheet.fit_to_pages(1, 0)
                worksheet.hide_gridlines(2)
                worksheet.write_comment('A1', comment1 + comment2, {'x_scale': 3})
        workbook = writer.book
        workbook.set_properties({'title': 'BOM Check', 'author': username,
                'subject': 'Compares a SolidWorks BOM to a SyteLine BOM',
                'company': 'Dekker Vacuum Technologies, Inc.',
                'comments': comment1 + comment2})
        writer.save()
    printStr = "\nCreated file: " + fn + '\n'
    printStrs += printStr
    print(printStr)

    if sys.platform[:3] == 'win':  # Open bomcheck.xlsx in Excel when on Windows platform
        try:
            os.startfile(os.path.abspath(fn))
        except:
            printStr = '\nAttempt to open bomcheck.xlsx in Excel failed.\n'
            printStrs += printStr
            print(printStr)

# before program begins, create global variables
set_globals()

if __name__=='__main__':
    main()                   # comment out this line for testing
    #bomcheck('*')   # use for testing #



