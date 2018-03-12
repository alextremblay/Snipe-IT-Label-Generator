"""
    NAME
        mkinventorylabel -- SnipeITLabelGenerator

    SYNOPSIS
        mkinventorylabel [-h] [-r] [-a asset_number] [-p password]
                     [-i input_file_path] [-o output_file_path]

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
        -p, --password _password_
            The password used to encrypt / decrypt your Snipe-IT API key
        -i, --input-file _filepath_
            The path to the odt template file you want to use to generate a
            label
        -o, --output-file _filepath_
            The path to the location you would like to save the completed label
            file to

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

import sys
import base64
import os
import argparse
import pickle
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from shutil import rmtree
from pathlib import Path
from getpass import getpass

# External library imports
import pystache
import pystache.parser
from requests import get
import qrcode
from PIL import Image
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Constants
STORED_DATA_PATH = Path.home() / '.config' / 'asset-label-generator' / 'data'
DEFAULT_IN_FILE_PATH = Path.home() / 'Asset-Template.odt'
DEFAULT_OUT_FILE_PATH = Path.home() / 'Asset-Label.odt'


def main():
    def get_program_arguments():
        """

        Returns:
            Namespace(
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
            STORED_DATA_PATH.unlink()
            print('Stored application data has been successfully deleted.',
                  'Please restart this application.')
            sys.exit()
        else:
            parser = argparse.ArgumentParser()
            parser.add_argument('-p', '--password')
            parser.add_argument('-t', '--type')
            parser.add_argument('-n', '--item-num')
            parser.add_argument('-i', '--input-file')
            parser.add_argument('-o', '--output-file')
            parser.add_argument('-s', '--show-available-fields',
                                action='store_true')
            return parser.parse_args()

    args = get_program_arguments()

    if is_first_time_running_program():
        app_configuration, password = do_first_run_setup(args.password)
    else:
        if not args.password:
            args.password = getpass(
                'Please enter the password you configured to decrypt your '
                'Snipe-IT API key \nPassword> ')
        app_configuration = get_stored_data()

    def process_inputs(arg_namespace):
        """

        Args:
            arg_namespace: Namespace

        Returns:
            Namespace

        """
        input_file_prompt = '''
Please provide the filepath where your template odt file can be found 
(ie. "~/Downloads/Asset-Template.odt")
Template File path [{}]> '''.format(str(DEFAULT_IN_FILE_PATH))
        if not arg_namespace.input_file:
            choice = input(input_file_prompt)
            if not choice:  # User pressed enter to select default file path
                if DEFAULT_IN_FILE_PATH.exists():
                    arg_namespace.input_file = str(DEFAULT_IN_FILE_PATH)
                else:
                    raise Exception(
                        'There is no template file at {}. Please check and try '
                        'again'.format(str(DEFAULT_IN_FILE_PATH)))
            else:  # User supplied file path
                arg_namespace.input_file = choice

        item_type_prompt = '''
Please specify the type of item you would like to generate a label for. 
The avaiable options are: 
    * assets
    * accessories
    * consumables
    * components
Item Type [assets]> '''
        if not arg_namespace.type:
            choice = input(item_type_prompt)
            if not choice:  # User pressed enter to select default file path
                arg_namespace.type = 'assets'
            else:  # User supplied file path
                arg_namespace.type = choice
        try:
            assert arg_namespace.type in \
                   ['assets', 'accessories', 'consumables', 'components']
        except AssertionError:
            msg = 'Sorry, {} is not a valid selection. Please try again'
            print(msg.format(arg_namespace.type))
            sys.exit(1)
        if arg_namespace.type == 'assets':
            # Snipe-IT API entry point for assets is actually hardware
            arg_namespace.type = 'hardware'

        item_number_prompt = '''
Please provide the asset numer you would like to generate a label for 
Asset Number> '''
        if not arg_namespace.item_num:
            arg_namespace.item_num = input(item_number_prompt)

        output_file_prompt = '''
Please provide the filepath where you would like the generated file to be saved 
(ie. "~/Downloads/Asset-Label.odt")
Output File Path [{}]> '''.format(str(DEFAULT_OUT_FILE_PATH))
        if not arg_namespace.output_file:
            choice = input(output_file_prompt)
            if not choice:  # User pressed enter to select default file path
                arg_namespace.output_file = str(DEFAULT_OUT_FILE_PATH)
            else:  # User supplied file path
                arg_namespace.output_file = choice

        return arg_namespace

    args = process_inputs(args)

    input_file = Path(args.input_file).expanduser()
    output_file = Path(args.output_file).expanduser()

    # get api key
    api_key = get_api_key(app_configuration, args.password)

    # unpack template into temporary folder
    tempdir = Path(tempfile.mkdtemp())
    try:
        compression_info = unpack_template(input_file, tempdir)

        # pull template tags from content.xml file to
        # figure out what info we need
        template_info = get_info_from_template(tempdir)

        # make sure asset_tag is included in the list of tags requested
        print('Found the following template tags in the provided template:')
        for item in template_info['template_tags']:
            print('{{' + item + '}}')

        # get the info we need from the server
        data = get_info_from_server(args.type, str(args.item_num), api_key,
                                    app_configuration)

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
                print(
                    "WARNING: template field {{ {0} }} not found in data "
                    "returned from server.".format(tag))

        # modify template
        generate_qr_code(args.type, args.item_num, template_info, tempdir,
                         app_configuration)
        render_template_info(tempdir, asset_data)

        # save template
        pack_template(tempdir, output_file, compression_info)

        print('Done! The newly-generated asset label can be found at '
              + str(output_file))
    finally:
        # if anything goes wrong while the tempdir exists, we want to make sure
        # the tempdir is properly removed.
        rmtree(str(tempdir))


def is_first_time_running_program() -> bool:
    """

    Returns:
        True if the file at STORED_DATA_PATH exists
        False if it doesn't

    """
    if not STORED_DATA_PATH.exists():
        return True
    else:
        return False


def do_first_run_setup(password=None) -> tuple:
    """

    Args:
        password: str

    Returns:
        (
            {
                'encrypted_api_key': b' encrypted bytes sequence',
                'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
                'snipe_it_url': 'https://your.company.ca/'
            },
            'somepassword'
        )

    """

    app_configuration = {}

    # get information from client
    print('Hello! I see that this is your first time using this application.'
          'Please answer the following questions:')
    url_prompt = 'Please enter the full URL of your Snipe-IT installation (' \
                 'ie. https://your.company.com/snipe/) \nURL> '
    app_configuration['snipe_it_url'] = input(url_prompt)
    api_prompt = '''
Please enter your personal Snipe-IT API key. A new API key can be aquired from 
the "Manage API Keys" menu in your user profile menu on your 
Snipe-IT installation
API>'''
    unencrypted_api_key = input(api_prompt)
    pass_prompt = '''
Please enter the password you would like to use to encrypt your 
Snipe-IT API key. The password can be anything you like, but should be at 
least 8 characters long. Please do not loose this password, you will not be 
able to recover your Snipe-IT API key without it. 
Password> '''
    if not password:
        password = getpass(pass_prompt)

    # encrypt api key with password
    cipher = PasswordCipher(password)

    # we need to store the cryptographic salt in order to derive the same
    # key from the same password the next time our app is run
    app_configuration['encrypted_api_key'] = cipher.encrypt(unencrypted_api_key)
    app_configuration['encryption_salt'] = cipher.salt

    # Create STORED_DATA_PATH if it doesn't exists
    STORED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # store encrypted key and other info in STORED_DATA_PATH
    with STORED_DATA_PATH.open('w+b') as f:
        pickle.dump(app_configuration, f)

    # done
    return app_configuration, password


def get_stored_data() -> dict:
    """

    Returns:
        Something like:
        {
            'encrypted_api_key': b' encrypted bytes sequence',
            'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
            'snipe_it_url': 'https://your.company.ca/'
        }

    """
    with STORED_DATA_PATH.open('r+b') as f:
        stored_data = pickle.load(f)
    return stored_data


def get_api_key(app_configuration, password) -> str:
    """

    Args:
        app_configuration:
            something like:
            {
                'encrypted_api_key': b' encrypted bytes sequence',
                'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
                'snipe_it_url': 'https://your.company.ca/'
            }
        password:
            str

    Returns:
        str

    """
    pw = password
    while True:
        try:
            cipher = PasswordCipher(pw, app_configuration['encryption_salt'])
            api_key = cipher.decrypt(app_configuration['encrypted_api_key'])
        except InvalidPassword:
            pw = getpass(
                'Error: the provided password is unable to decrypt the stored '
                'API key. Are you sure you entered the correct password? \n'
                'Please Try again. \nPassword>')
            continue  # restart the while loop, try again
        break  # break out of the while loop and complete
    return api_key


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
                         api_key,
                         app_configuration) -> dict:
    """

    Args:
        item_type:
            One of: ['hardware', 'accessories', 'consumables', 'components']
        item_id: str
        api_key: str
        app_configuration:
            Something like:
            {
                'encrypted_api_key': b' encrypted bytes sequence',
                'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
                'snipe_it_url': 'https://your.company.ca/'
            }

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
        base_url = app_configuration['snipe_it_url'] + 'api/v1',
        type=item_type, id=item_id)
    headers = {
        'authorization': 'Bearer ' + api_key,
        'accept': "application/json"
    }
    data = get(url, headers=headers).json()

    if 'status' in data and data['status'] == 'error':
        print('Received the following error from the Snipe-IT server: ',
              data['messages'])
        sys.exit(1)
    else:
        data = flatten(data)
        data = clean(data)
        return data


def generate_qr_code(item_type, item_number, template_info, tempdir,
                     app_configuration):
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
        base_url = app_configuration['snipe_it_url'] + 'api/v1',
        type = item_type,
        id = str(item_number)
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


class InvalidPassword(Exception):
    pass


class PasswordCipher(object):
    def __init__(self, password: str, salt=None):
        password = bytes(password, 'utf')
        self.salt = salt if salt else os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
            backend=default_backend()
        )
        self.key = base64.urlsafe_b64encode(kdf.derive(password))

    def encrypt(self, plaintext: str) -> bytes:
        return Fernet(self.key).encrypt(bytes(plaintext, 'utf'))

    def decrypt(self, encrypted_text: bytes) -> str:
        try:
            result = Fernet(self.key).decrypt(encrypted_text).decode('utf')
        except InvalidToken:
            raise InvalidPassword
        return result


if __name__ == '__main__':
    main()
