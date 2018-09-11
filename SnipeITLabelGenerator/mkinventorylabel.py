"""
    NAME
        mklabel -- SnipeITLabelGenerator

    SYNOPSIS
        mklabel -h
        mklabel -s
        mklabel [-t type] [-n item_number] [-i input_file_path] [-o output_file_path]
        mklabel -r

    DESCRIPTION
        This Snipe IT Inventory Label Generator script takes a template odt file
        containing a placeholder image, fills in information in the
        template, replaces the image with a QR code, and produces a completed
        odt file for you to view and print

    COMMAND LINE OPTIONS
        -h, --help
            Print this help message and exit
        -r, --reset
            Delete stored application data and exit
        -t, --type
            The item type to look up. Must be one of the following keywords:
                assets, accessories, consumables, components
        -n, --item-num _number_
            The unique number id of the item you are looking to make a
            label for. When you navigate to an item
            (asset/comsumable/accessory/etc), this id can be found at the end
            of the url path. ie: For an asset found at
            https://snipe.company.com/hardware/428 the item number is 428
            For an accessory found at https://snipe.company.com/accessories/35
            the item number is 35
        -i, --input-file _filepath_
            The path to the odt template file you want to use to generate a
            label
        -o, --output-file _filepath_
            The path to the location you would like to save the completed label
            file to
        -s, --show-available-fields
            Use this flag to retrieve a list of all data fields in Snipe IT
            for a given item, along with tag names for each

    TEMPLATE FILE
        The template file you wish you use must have one and ONLY one image in
        it. This image can be anything and will be used as a placeholder for the
        placement of the auto-generated QR code.

        The template file can also optionally include "Template Tags" for data
        to be retrieved from the inventory management system and inserted into
        the template. For a list of available template tags for a given
        asset/accessory/etc, run this command with the -s flag. The tags must
        by entered into the template in the following format:
            {{tag_name}}

    AUTHOR
        Alex Tremblay

"""
# Local imports
from . import config

# Std Lib imports
import sys
import argparse
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from shutil import rmtree
from pathlib import Path
from subprocess import run
from dataclasses import dataclass
from logging import getLogger

# External library imports
import pystache
import pystache.parser
from requests import get
import qrcode
from PIL import Image

# Constants
DEFAULT_IN_FILE_PATH = Path.home() / 'Asset-Template.odt'
DEFAULT_OUT_FILE_PATH = Path.home() / 'Asset-Label.odt'
LOG = getLogger(__name__)

@dataclass
class Args:
    type: str = None
    item_num: str = None
    input_file: str = DEFAULT_IN_FILE_PATH
    output_file: str = DEFAULT_OUT_FILE_PATH
    show_available_fields: bool = False

    def process_inputs(self):
        """

        prompts user to fill in any values that haven't been provided

        """
        input_file_prompt = '''
Please provide the filepath where your template odt file can be found 
(ie. "~/Downloads/Asset-Template.odt")
Template File path [{}]> '''.format(str(DEFAULT_IN_FILE_PATH))
        if not self.input_file:
            if not sys.stdout.isatty():
                sys.stderr.write("When piping this application's output, "
                                "template file path must be specified as a "
                                "command argument (the '-i' flag)")
                sys.exit(1)
            choice = input(input_file_prompt)
            if not choice:  # User pressed enter to select default file path
                if DEFAULT_IN_FILE_PATH.exists():
                    self.input_file = str(DEFAULT_IN_FILE_PATH)
                else:
                    raise Exception(
                        'There is no template file at {}. Please check and try '
                        'again'.format(str(DEFAULT_IN_FILE_PATH)))
            else:  # User supplied file path
                self.input_file = choice

        item_type_prompt = '''
Please specify the type of item you would like to generate a label for. 
The avaiable options are: 
    * assets
    * accessories
    * consumables
    * components
Item Type [assets]> '''
        if not self.type:
            if not sys.stdout.isatty():
                sys.stderr.write("When piping this application's output, "
                                "item type must be specified as a "
                                "command argument (the '-t' flag)")
                sys.exit(1)
            choice = input(item_type_prompt)
            if not choice:  # User pressed enter to select default file path
                self.type = 'assets'
            else:  # User supplied file path
                self.type = choice
        try:
            assert self.type in \
                   ['assets', 'accessories', 'consumables', 'components']
        except AssertionError:
            msg = 'Sorry, {} is not a valid selection. Please try again'
            print(msg.format(self.type))
            sys.exit(1)
        if self.type == 'assets':
            # Snipe-IT API entry point for assets is actually hardware
            self.type = 'hardware'

        item_number_prompt = '''
Please provide the asset numer you would like to generate a label for 
Asset Number> '''
        if not self.item_num:
            if not sys.stdout.isatty():
                sys.stderr.write("When piping this application's output, "
                                "item number must be specified as a "
                                "command argument (the '-n' flag)")
                sys.exit(1)
            self.item_num = input(item_number_prompt)
        if not self.output_file:
            _, name = tempfile.mkstemp(suffix='.odt')
            self.output_file = name


@dataclass
class AppData:
    url: str
    api_key: str


def notify(*args):
    '''prints message to console if console is interactive.
    otherwise logs message'''
    if sys.stdout.isatty():
        print(*args)
    else:
        LOG.warning(*args)

def main():
    appdata = AppData(**config.get('SnipeITLabelGenerator', [
        {
            'value': 'url',
            'prompt': "Please enter the full URL of your "
                      "Snipe-IT installation \n"
                      "ex. https://snipe.mycompanyserver.com/ \n"
                      "URL> ",
            'optional': False,
            'sensitive': False
        },
        {
            'value': 'api_key',
            'prompt': "Please enter your API key. if you don't have one, a new "
                      "API key can be generated for your account. Log in to "
                      "Snipe-IT, click on your account on the top-right of the "
                      "screen, go to 'Manage API Keys', and click "
                      "'Create New Token' \n"
                      "Token> ",
            'optional': False,
            'sensitive': False
        },
    ]))

    def get_program_arguments():
        """

        Returns:
            Dict(
                asset_number=400,
                input_file='some/file/path.odt',
                output_file='some/other/path.odt',
                password='yourpassword'
            )
        """

        # Print help if no arguments given, otherwise run the script
        if '-h' in sys.argv or '--help' in sys.argv:
            print(__doc__)
            sys.exit()
        elif '-r' in sys.argv or '--reset' in sys.argv:
            config.reset()
            sys.exit()
        else:
            parser = argparse.ArgumentParser()
            parser.add_argument('-t', '--type')
            parser.add_argument('-n', '--item-num')
            parser.add_argument('-i', '--input-file')
            parser.add_argument('-o', '--output-file')
            parser.add_argument('-s', '--show-available-fields',
                                action='store_true')
            # Generate Argparse Namespace, convert it to a dict
            result = vars(parser.parse_args())

            # Remove all None value, so we can merge this dict in with
            # defaults and configs from other sources
            result = {key: value for key, value in result.items()
                      if value is not None}
            return result

    args = Args(**get_program_arguments())

    args.process_inputs()

    input_file = Path(args.input_file).expanduser()
    output_file = Path(args.output_file).expanduser()

    # unpack template into temporary folder
    tempdir = Path(tempfile.mkdtemp())
    try:
        compression_info = unpack_template(input_file, tempdir)

        # pull template tags from content.xml file to
        # figure out what info we need
        template_info = get_info_from_template(tempdir)

        # make sure asset_tag is included in the list of tags requested
        notify('Found the following template tags in the provided template:')
        for item in template_info['template_tags']:
            notify('{{' + item + '}}')

        # get the info we need from the server
        data = get_info_from_server(args.type, args.item_num, appdata)

        if args.show_available_fields:
            print('Here are the available fields for this particular '
                  'inventory item:')
            for key, value in data.items():
                key_name = "{{{{{}}}}}".format(key)
                print("{:15} = {}".format(key_name, value))
            sys.exit(0)

        asset_data = {}
        for tag in template_info['template_tags']:
            if tag in data:
                asset_data[tag] = data[tag]
            else:
                notify(
                    "WARNING: template field {{ {0} }} not found in data "
                    "returned from server.".format(tag))

        # modify template
        generate_qr_code(args.type, args.item_num, template_info, tempdir,
                         appdata)
        render_template_info(tempdir, asset_data)

        # save template
        pack_template(tempdir, output_file, compression_info)

        notify('Done! The newly-generated asset label can be found at '
              + str(output_file))
        out_file_pdf = output_file.with_suffix('.pdf')
        out_dir = str(output_file.parent)
        if sys.platform == 'darwin':
            run(['/Applications/LibreOffice.app/Contents/MacOS/soffice',
                 '--convert-to', 'pdf', '--outdir', out_dir, str(output_file)])
        elif sys.platform == 'linux':
            run(['soffice', '--convert-to', 'pdf', '--outdir', out_dir,
                 str(output_file)])

        if sys.stdout.isatty():
            if sys.platform == 'darwin':
                run(['open', str(out_file_pdf)])
            elif sys.platform == 'linux':
                run(['xdg-open', str(out_file_pdf)])
        else:
            sys.stdout.buffer.write(out_file_pdf.read_bytes())

    finally:
        # if anything goes wrong while the tempdir exists, we want to make sure
        # the tempdir is properly removed.
        rmtree(str(tempdir))


def unpack_template(input_path, tempdir) -> dict:
    """

    Args:
        input_path: Path
        tempdir: Path

    Returns:
        a map of filenames in the input path and their compression level. Ex:
        {'Configurations2/accelerator/current.xml': 8,
         'META-INF/manifest.xml': 8,
         'Pictures/100000000000017200000172D652708C6A947391.png': 0,
         'Thumbnails/thumbnail.png': 0,
         'content.xml': 8,
         'manifest.rdf': 8,
         'meta.xml': 8,
         'mimetype': 0,
         'settings.xml': 8,
         'styles.xml': 8}


    """
    if not input_path.exists():
        prompt = 'Error: ' + str(input_path) + ' does not seem to exist. ' \
                                               'Please specify a valid path ' \
                                               'to a *.odt file \nTemplate ' \
                                               'File Path>'
        new_path = input(prompt)
        input_path = Path(new_path).expanduser()
    input_file = ZipFile(str(input_path))
    input_file.extractall(str(tempdir))
    filemap = {}
    for file in input_file.infolist():
        filemap[file.filename] = file.compress_type
    return filemap


def get_info_from_template(tempdir) -> dict:
    """

    Args:
        tempdir: Path

    Returns:
        Something like this:
        {
            'qr_code_dimensions': (370, 370),  # width and height
            'template_tags': ['asset_tag', 'serial_number', 'model_number'],
        }

    """

    info = {'qr_code': {}, 'template_tags': []}

    # get dimensions & filename of QR code placeholder
    images_in_template = sorted(tempdir.glob('Pictures/*'))
    if not len(images_in_template) == 1:
        print('Error: The template file you specified appears to have either '
              'more or less than one image in it. Please remove all but one '
              'image and try again.')
        sys.exit(2)
    qr_code_file = images_in_template[0]

    with Image.open(str(qr_code_file)) as im:
        info['qr_code_dimensions'] = (im.width, im.height)

    # get tags from template
    content_xml_path = tempdir / 'content.xml'
    with open(str(content_xml_path)) as f:
        parsed_template = pystache.parse(f.read())
        info['template_tags'] = [
            item.key for item in parsed_template._parse_tree
            if type(item) is pystache.parser._EscapeNode
        ]

    return info


def get_info_from_server(item_type,
                         item_id,
                         appdata: AppData) -> dict:
    """

    Args:
        item_type:
            One of: ['hardware', 'accessories', 'consumables', 'components']
        item_id: str
        api_key: str
        appdata: AppData

    Returns:
        Something like:
        {
            'serial_number': '83I1703F2BC',
            'asset_tag': '00400',
            'model_number': 'AP82i'
        }

    """

    def flatten(d, parent_key='', sep='_'):
        items = []
        for k, v in d.items():
            new_key = '{0}{1}{2}'.format(parent_key, sep,
                                         k) if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # apply itself to each element of the list - that's it!
                items.append((new_key, map(flatten, v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def clean(d):
        """
        Iterates a dict, removing empty keys and converting ints to strings
        Args:
            d: dict

        Returns: dict

        """
        clean_dict = {}
        for key, value in d.items():
            if value is None:
                continue
            if isinstance(value, int):
                clean_dict[key] = str(value)
            else:
                clean_dict[key] = value
        return clean_dict

    url = '{base_url}/{type}/{id}'.format(
        base_url = appdata.url + 'api/v1',
        type=item_type, id=item_id)
    headers = {
        'authorization': 'Bearer ' + appdata.api_key.strip(),
        'accept': "application/json"
    }
    data = get(url, headers=headers).json()

    if 'status' in data and data['status'] == 'error':
        sys.stderr.write('Received the following error from the Snipe-IT server: ',
              data['messages'] +'\n')
        sys.exit(1)
    else:
        data = flatten(data)
        data = clean(data)
        return data


def generate_qr_code(item_type, item_number, template_info, tempdir,
                     appdata: AppData):
    """

    Args:
        item_type: str
        item_number: int
        template_info:
            Something like this:
            {
                'qr_code_dimensions': (370, 370),  # width and height
                'template_tags': ['asset_tag', 'serial_number', 'model_number'],
            }
        tempdir:
                the temporary file location where the decompressed template
                is being staged / modified
        app_configuration:
            Something like:
            {
                'encrypted_api_key': b' encrypted bytes sequence',
                'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
                'snipe_it_url': 'https://your.company.ca/'
            }

    Side Effect:
        The first image file found within the Pictures folder inside the
        tempdir gets overwritten by a QR code image of a URL pointing to the
        asset specified by asset_number

    """
    qr_code_url = '{base_url}/{type}/{id}'
    qr_code_url = qr_code_url.format(
        base_url = appdata.url + 'api/v1',
        type = item_type,
        id = item_number
    )
    qr_code_file = sorted(tempdir.glob('Pictures/*'))[0]
    imgdata = qrcode.make(qr_code_url)
    dimensions = template_info['qr_code_dimensions']
    imgdata = imgdata.resize(dimensions)
    imgdata.save(str(qr_code_file))


def render_template_info(tempdir, asset_data):
    """

        Args:
            tempdir: Path
            asset_data:
                Something like:
                {
                    'serial_number': '83I1703F2BC',
                    'asset_tag': '00400',
                    'model_number': 'AP82i'
                }

        Side Effect:
            the content.xml file in the tempdir
            gets processed by pystache, the template tags found within it are
            replaced by the data in asset_data, and then that modified file
            gets written into the template_file

        """
    content_file = tempdir / 'content.xml'
    template_string = content_file.read_text()
    rendered_template = pystache.render(template_string, asset_data)
    with open(str(tempdir / 'content.xml'), 'w') as f:
        f.write(rendered_template)


def pack_template(tempdir, output_file, compression_info):
    """

    Args:
        tempdir: Path
        output_file: Path
        compression_info: dict

    Side Effect:
        The contents of tempdir are packed into an archive stored at output_file
    """
    if output_file.exists():
        output_file.unlink()  # unlink means delete
    with ZipFile(str(output_file), 'x', compression=ZIP_DEFLATED) as label_file:

        for file in tempdir.glob('**/*'):
            arcname = file.relative_to(tempdir)
            compress_type = compression_info.get(arcname)
            label_file.write(str(file), arcname=str(arcname),
                             compress_type=compress_type)


if __name__ == '__main__':
    main()
