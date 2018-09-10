"""
Retrieves and / or generates configuration information,
stored in ~/.config/[app name]/config
"""

# Std Lib imports
from getpass import getpass
import os

# External imports
from easysettings import EasySettings


SETTINGS_FILE_ROOT = os.environ.get('XDG_CONFIG_HOME') \
    if os.environ.get('XDG_CONFIG_HOME') else '~/.config/'


def get(name, values):
    """The showrunner, where all the magic happens

    This function (this whole module really) is designed to do one thing:
    abstract away all the noise and complexity of configuration management.
    Rather than handle user input and figuring out where and how to store that
    input and wrestling with file permission (or lack thereof), just let this
    module take care of it for you!

    When you run this function for the first time, here's what happens:
        - a config file is created in a folder named after your app,
          in ~/.config (or XDG_CONFIG_HOME if set)
        - the user gets prompted to answer a set of questions defined by you
        - the answers to those questions are stored in the config file
        - If any of those questions are marked optional, the following happens:
            after the user is prompted to answer the question, they will be
            asked to save their response. If they answer yes, the value will be
            saved as normal. If they answer no, the value will not be saved,
            and they will be prompted to answer the question again the next
            time this function is called.
        - The user will be notified that a config file has been created for
          them, and reminded to set appropriate permissions for this file if it
          contains any sensitive info.
        - if we can't save the config file (due to permission errors or
          something else), we warn the user of the issue, and treat all values
          gathered as optional. The next time this function runs, the user will
          be prompted for those values again just as if this function had never
          been called before. This behaviour will continue until the problem
          preventing config file saving is resolved.
        - this function returns an object containing all the values that were
          gathered from the user

    Any time this function is called afterwards:
        - all the values specified are retrieved from the config file that was
          created the first time around.
        - any value marked as optional which wasn't saved last time will be
          prompted for again, and the user will once again be given the option
          to save it
        - this function returns an object containing all the values that were
          gathered from the user

    Args:
        name (str): The name of the application to store / retrieve config for
        values (Sequence[Dict[str, str]]):
            The values to get / set in our config file, in the form of:
            [
                {
                    value (str): The value to get / set
                    prompt (str):
                        If the value hasn't been set yet, and user input is
                        required, what question or prompt should be displayed
                        for the user to respond to?
                    optional (bool):
                        if True, prompt if user wants to save the value in
                        config file, or prompt for it every time (ie. passwords)
                    sensitive (bool):
                        if True, getpass will be used to record the answer to
                        this question (meaning that any text typed in as
                        response to this question will not be printed onto the
                        screen
                },
                ...
            ]

    Returns:
        Dict[str, str]: a dictionary of all the values that were gathered from
            either the user or the config file

    Raises:
        #TODO: flesh this out

    Examples:
        >>>values = [
        ...             {
        ...                 'value': 'url',
        ...                 'prompt': "Please enter the full URL of your "
        ...                     "phpIPAM installation including the API app_id "
        ...                     "\\nex. https://phpipam.mycompanyserver.com"
        ...                     "/api/app_id/ \\nURL> ",
        ...                 'optional': False,
        ...                 'sensitive': False
        ...             },
        ...             {
        ...                 'value': 'username',
        ...                 'prompt': "Please enter your phpIPAM username: "
        ...                           "\\nUsername> ",
        ...                 'optional': True,
        ...                 'sensitive': False
        ...             },
        ...             {
        ...                 'value': 'password',
        ...                 'prompt': "Please enter your phpIPAM password: "
        ...                           "\\nPassword> ",
        ...                 'optional': True,
        ...                 'sensitive': True
        ...             },
        ...         ]
        >>>get('phpipam', values)  # Called for the first time
        Please enter the full URL of your phpIPAM
        installation including the API app_id
        ex. https://phpipam.mycompanyserver.com/api/app_id/
        URL> >? https://my.domain.com/phpipam/api/my_app_id/
        Please enter your phpIPAM username:
        Username> >? mytestuser
        Would you like to save this for later use? (yes/no)> >? yes
        Warning: Password input may be echoed.
        Please enter your phpIPAM password:
        Password> >? mysupersecretpassword
        Would you like to save this for later use? (yes/no)> >? no
        {'password': 'mysupersecretpassword', 'username': 'mytestuser',
         'url': 'https://my.domain.com/phpipam/api/my_app_id/'}
        >>>get('phpipam', values)  # Called again
        {'password': 'mysupersecretpassword', 'username': 'mytestuser',
         'url': 'https://my.domain.com/phpipam/api/my_app_id/'}

    """
    settings_file = os.path.expanduser(SETTINGS_FILE_ROOT + name + '/config')
    if not os.path.exists(settings_file):
        os.makedirs(os.path.dirname(settings_file), mode=0o700)
    settings = EasySettings(settings_file)

    result = dict()

    for item in values:
        key_name = item['value']
        result[key_name] = settings.get(item['value'], default=None)
        if not result[key_name]:
            sensitive = item['sensitive']  # bool
            result[key_name] = get_user_input(item['prompt'], sensitive)
            if item['optional']:
                choice = get_user_input("Would you like to save this for later "
                                        "use? \n(yes/no)> ", sensitive=False)
                if choice[0] == 'y' or choice[0] == 'Y':
                    settings.setsave(key_name, result[key_name])
            else:
                settings.setsave(key_name, result[key_name])

    return result

def reset():
    os.unlink(SETTINGS_FILE_ROOT)
    print('Stored application data has been successfully deleted.')

def get_user_input(prompt: str, sensitive: bool):
    input_function = getpass if sensitive else input
    return input_function(prompt)