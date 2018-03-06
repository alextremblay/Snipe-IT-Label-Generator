"""
    NAME
        mkassetlabel -- AssetLabelGenerator

    SYNOPSIS
        mkassetlabel [-h] [-r] [-a asset_number] [-p password]
                     [-i input_file_path] [-o output_file_path]

    DESCRIPTION
        This Snipe IT Asset Label Generator script takes a template odt file
        containing a placeholder image file, fills in information in the
        template, replaces the image with a QR code, and produces a completed
        odt file for you to view and print

    COMMAND LINE OPTIONS

        -h, --help
            print this help message and exit
        -r, --reset
            delete stored application data and exit
        -a, --asset_number _number_
            The asset tag number (without any leading zeroes) of the Snipe-IT
            asset for which to make a label. (ie. 415)
        -p, --password _password_
            The password used to encrypt / decrypt your Snipe-IT API key
        -i, --input-file _filepath_
            The path to the odt template file you want to use to generate a label
        -o, --output-file _filepath_
            The path to the location you would like to save the completed label
            file to

    TEMPLATE FILE
        The template file you wish you use must have one and ONLY one image in it.
        This image can be anything and will be used as a placeholder for the
        placement of the auto-generated QR code.

        Additionally, the template file must contain, anywhere within its text,
        at least one of the following template tags:
            {{status}}
            {{order_number}}
            {{asset_tag}}
            {{last_update}}
            {{location}}
            {{manufacturer}}
            {{created_at}}
            {{assigned_to}}
            {{asset_id}}
            {{mac_address}}
            {{purchase_cost}}
            {{category_name}}
            {{notes}}
            {{model_number}}
            {{asset_name}}
            {{warranty_expires}}
            {{last_checkout}}
            {{expected_checkin}}
            {{serial_number}}
            {{supplier}}
            {{model_name}}
            {{purchase_date}}
            {{warranty}}
            {{company}}

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
        '''

        Returns:
            Namespace(
                asset_number=400,
                input_file='some/file/path.odt',
                output_file='some/other/path.odt',
                password='yourpassword'
            )
        '''

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
            parser.add_argument('-a', '--asset-number', type=int)
            parser.add_argument('-i', '--input-file')
            parser.add_argument('-o', '--output-file')
            return parser.parse_args()

    args = get_program_arguments()

    if is_first_time_running_program():
        app_configuration, password = do_first_run_setup(args.password)
    else:
        if not args.password:
            args.password = getpass('Please enter the password you configured to '
                               'decrypt your Snipe-IT API key \nPassword> ')
        app_configuration = get_stored_data()

    # process inputs
    input_file_prompt = 'Please provide the filepath where your template odt ' \
                        'file can be found (ie. "~/Downloads/Asset-Template' \
                        '.odt") \nTemplate File path ' \
                        '[{}]> '.format(str(DEFAULT_IN_FILE_PATH))
    if not args.input_file:
        choice = input(input_file_prompt)
        if not choice:  # User pressed enter to select default file path
            if DEFAULT_IN_FILE_PATH.exists():
                args.input_file = str(DEFAULT_IN_FILE_PATH)
            else:
                raise Exception(
                    'There is no template file at {}. Please check and try '
                    'again'.format(str(DEFAULT_IN_FILE_PATH)))
        else:  # User supplied file path
            args.input_file = choice

    asset_number_prompt = 'Please provide the asset numer you would like to ' \
                          'generate a label for \nAsset Number> '
    if not args.asset_number:
        args.asset_number = input(asset_number_prompt)

    output_file_prompt = 'Please provide the filepath where you would like the ' \
                         'generated file to be saved (ie. "~/Downloads/Asset-' \
                         'Label.odt") \nOutput File Path ' \
                         '[{}]> '.format(str(DEFAULT_OUT_FILE_PATH))
    if not args.output_file:
        choice = input(output_file_prompt)
        if not choice:  # User pressed enter to select default file path
            args.output_file = str(DEFAULT_OUT_FILE_PATH)
        else:  # User supplied file path
            args.output_file = choice

    input_file = Path(args.input_file).expanduser()
    output_file = Path(args.output_file).expanduser()

    # get api key
    api_key = get_api_key(app_configuration, args.password)

    # unpack template into temporary folder
    tempdir = Path(tempfile.mkdtemp())
    try:
        compression_info = unpack_template(input_file, tempdir)

        # pull template tags from content.xml file to figure out what info we need
        template_info = get_info_from_template(tempdir)

        # make sure asset_tag is included in the list of tags requested
        print('Found the following template tags in the provided template:')
        for item in template_info['template_tags']:
            print('{{' + item + '}}')

        # get the info we need from the server
        asset_data = get_info_from_server(template_info['template_tags'],
                                          args.asset_number, api_key,
                                          app_configuration)

        # modify template
        generate_qr_code(args.asset_number, template_info, tempdir,
                       app_configuration)
        render_template_info(template_info, tempdir, asset_data)

        # save template
        pack_template(tempdir, output_file, compression_info)

        print('Done! The newly-generated asset label can be found at '
              + str(output_file))
    finally:
        # if anything goes wrong while the tempdir exists, we want to make sure
        # the tempdir is properly removed.
        rmtree(str(tempdir))


def is_first_time_running_program() -> bool:
    '''

    Returns:
        True if the file at STORED_DATA_PATH exists
        False if it doesn't

    '''
    if not STORED_DATA_PATH.exists():
        return True
    else:
        return False


def do_first_run_setup(password=None) -> tuple:
    '''

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

    '''

    app_configuration = {}

    # get information from client
    print('Hello! I see that this is your first time using this application.'
          'Please answer the following questions:')
    url_prompt = 'Please enter the full URL of your Snipe-IT installation (' \
                 'ie. https://your.company.com/snipe/) \nURL> '
    app_configuration['snipe_it_url'] = input(url_prompt)
    api_prompt = 'Please enter your personal Snipe-IT API key. A new API key ' \
                 'can be aquired from the "Manage API Keys" menu in your user ' \
                 'profile menu on your Snipe-IT installation \nAPI>'
    unencrypted_api_key = input(api_prompt)
    pass_prompt = 'Please enter the password you would like to use to encrypt' \
                  ' your Snipe-IT API key. The password can be ' \
                  'anything you like, but should be at least 8 characters ' \
                  'long. Please do not loose this password, you will not be ' \
                  'able to recover your Snipe-IT API key without it. ' \
                  '\nPassword> '
    if not password:
        password = getpass(pass_prompt)

    # encrypt api key with password
    cipher = PasswordCipher(password)
    app_configuration['encrypted_api_key'] = cipher.encrypt(unencrypted_api_key)
    app_configuration['encryption_salt'] = cipher.salt
        # we need to store the cryptographic salt in order to derive the same
        # key from the same password the next time our app is run

    # Create STORED_DATA_PATH if it doesn't exists
    STORED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # store encrypted key and other info in STORED_DATA_PATH
    with STORED_DATA_PATH.open('w+b') as f:
        pickle.dump(app_configuration, f)

    #done
    return (app_configuration, password)


def get_stored_data() -> dict:
    '''

    Returns:
        Something like:
        {
            'encrypted_api_key': b' encrypted bytes sequence',
            'encryption_salt': b']C\xa3!\xaa"M\x9aNt\x1c9>h\x986',
            'snipe_it_url': 'https://your.company.ca/'
        }

    '''
    with STORED_DATA_PATH.open('r+b') as f:
        stored_data = pickle.load(f)
    return stored_data


def get_api_key(app_configuration, password) -> str:
    '''

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

    '''
    pw = password
    cipher = PasswordCipher(pw, app_configuration['encryption_salt'])
    while True:
        try:
            api_key = cipher.decrypt(app_configuration['encrypted_api_key'])
        except InvalidPassword:
            pw = getpass('Error: the provided password is unable to decrypt '
                               'the stored API key. Are you sure you entered the '
                               'correct password? \nPlease Try again. \nPassword>')
            continue  # restart the while loop, try again
        break  # break out of the while loop and complete
    return api_key


def unpack_template(input_path, tempdir) -> dict:
    '''

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


    '''
    if not input_path.exists():
        prompt = 'Error: ' + str(input_path) + ' does not seem to exist. Please ' \
                 'specify a valid path to a *.odt file \nTemplate File Path>'
        new_path = input(prompt)
        input_path = Path(new_path).expanduser()
    input_file = ZipFile(str(input_path))
    input_file.extractall(str(tempdir))
    filemap = {}
    for file in input_file.infolist():
        filemap[file.filename] = file.compress_type
    return filemap


def get_info_from_template(tempdir) -> dict:
    '''

    Args:
        tempdir: Path

    Returns:
        Something like this:
        {
            'qr_code_dimensions': (370, 370),  # width and height
            'template_tags': ['asset_tag', 'serial_number', 'model_number'],
        }

    '''

    info = {}
    info['qr_code'] = {}
    info['template_tags'] = []

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


def get_info_from_server(template_tags, asset_number, api_key, app_configuration) -> dict:
    '''

    Args:
        template_tags:
            Something like:
            ['asset_tag', 'serial_number', 'model_number']
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

    '''
    url = app_configuration['snipe_it_url'] + 'api/v1/hardware/' + str(asset_number)
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
        keys_to_delete = [key for key in data if data[key] is None]
        for key in keys_to_delete:
            del data[key]
        parsed_data = dict(
            warranty_expires=data.get('warranty_expires'),
            mac_address=data.get('custom_fields', {}).get('MAC Address',
                                                          {}).get('value'),
            model_name=data.get('model', {}).get('name'),
            notes=data.get('notes'),
            purchase_cost=data.get('purchase_cost'),
            last_checkout=data.get('last_checkout', {}).get('formatted'),
            manufacturer=data.get('manufacturer', {}).get('name'),
            supplier=data.get('supplier'),
            expected_checkin=data.get('expected_checkin'),
            category_name=data.get('category', {}).get('name'),
            asset_id=data.get('id'),
            order_number=data.get('order_number'),
            status=data.get('status_label', {}).get('name'),
            assigned_to=data.get('assigned_to', {}).get('name'),
            company=data.get('company'),
            last_update=data.get('updated_at', {}).get('formatted'),
            asset_name=data.get('name'),
            location=data.get('location'),
            serial_number=data.get('serial'),
            purchase_date=data.get('purchase_date', {}).get('formatted'),
            asset_tag=data.get('asset_tag'),
            created_at=data.get('created_at', {}).get('formatted'),
            model_number=data.get('model_number'),
            warranty=data.get('warranty')
        )
        results = {}
        for tag in template_tags:
            results[tag] = parsed_data[tag]
        return results


def generate_qr_code(asset_number, template_info, tempdir, app_configuration):
    '''

    Args:
        asset_number: int
        template_info:
            Something like this:
            {
                'qr_code_dimensions': (370, 370),  # width and height
                'template_tags': ['asset_tag', 'serial_number', 'model_number'],
            }
        output_file:
                ZipFile instance of a temporary copy of the template.odt file
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

    '''
    url_for_qr_code_to_point_to = app_configuration['snipe_it_url'] \
                                  + 'hardware/' + str(asset_number)
    qr_code_file = sorted(tempdir.glob('Pictures/*'))[0]
    imgdata = qrcode.make(url_for_qr_code_to_point_to)
    dimensions = template_info['qr_code_dimensions']
    imgdata = imgdata.resize(dimensions)
    imgdata.save(str(qr_code_file))


def render_template_info(template_info, tempdir, asset_data):
    '''

        Args:
            template_info:
                Something like this:
                {
                    'qr_code_dimensions': (370, 370),  # width and height
                    'template_tags': ['asset_tag', 'serial_number', 'model_number'],
                }
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

        '''
    content_file = tempdir / 'content.xml'
    template_string = content_file.read_text()
    rendered_template = pystache.render(template_string, asset_data)
    with open(str(tempdir / 'content.xml'), 'w') as f:
        f.write(rendered_template)


def pack_template(tempdir, output_file, compression_info):
    '''

    Args:
        tempdir: Path
        output_file: Path
        compression_info: dict

    Side Effect:
        The contents of tempdir are packed into an archive stored at output_file
    '''
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
    def __init__(self, password: str, salt = None):
        password = bytes(password, 'utf')
        self.salt = salt if salt else os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm = hashes.SHA256(),
            length = 32,
            salt = self.salt,
            iterations = 100000,
            backend = default_backend()
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