import os
import sys
import signal
import socket
import argparse
import time
from urllib.parse import urlparse

import requests
from pype.vendor import ftrack_api
from pype.ftrack.lib import credentials
from pype.ftrack.ftrack_server import FtrackServer
import socket_thread


def check_ftrack_url(url, log_errors=True):
    if not url:
        print('ERROR: Ftrack URL is not set!')
        return None

    url = url.strip('/ ')

    if 'http' not in url:
        if url.endswith('ftrackapp.com'):
            url = 'https://' + url
        else:
            url = 'https://{0}.ftrackapp.com'.format(url)
    try:
        result = requests.get(url, allow_redirects=False)
    except requests.exceptions.RequestException:
        if log_errors:
            print('ERROR: Entered Ftrack URL is not accesible!')
        return False

    if (result.status_code != 200 or 'FTRACK_VERSION' not in result.headers):
        if log_errors:
            print('ERROR: Entered Ftrack URL is not accesible!')
        return False

    print('DEBUG: Ftrack server {} is accessible.'.format(url))

    return url


def check_mongo_url(host, port, log_error=False):
    sock = None
    try:
        sock = socket.create_connection(
            (host, port),
            timeout=1
        )
        return True
    except socket.error as err:
        if log_error:
            print("Can't connect to MongoDB at {}:{} because: {}".format(
                host, port, err
            ))
        return False
    finally:
        if sock is not None:
            sock.close()


def validate_credentials(url, user, api):
    first_validation = True
    if not user:
        print('ERROR: Ftrack Username is not set! Exiting.')
        first_validation = False
    if not api:
        print('ERROR: Ftrack API key is not set! Exiting.')
        first_validation = False
    if not first_validation:
        return False

    try:
        session = ftrack_api.Session(
            server_url=url,
            api_user=user,
            api_key=api
        )
        session.close()
    except Exception as e:
        print(
            'ERROR: Can\'t log into Ftrack with used credentials:'
            ' Ftrack server: "{}" // Username: {} // API key: {}'.format(
            url, user, api
        ))
        return False

    print('DEBUG: Credentials Username: "{}", API key: "{}" are valid.'.format(
        user, api
    ))
    return True


def process_event_paths(event_paths):
    print('DEBUG: Processing event paths: {}.'.format(str(event_paths)))
    return_paths = []
    not_found = []
    if not event_paths:
        return return_paths, not_found

    if isinstance(event_paths, str):
        event_paths = event_paths.split(os.pathsep)

    for path in event_paths:
        if os.path.exists(path):
            return_paths.append(path)
        else:
            not_found.append(path)

    return os.pathsep.join(return_paths), not_found


def main_loop(ftrack_url, username, api_key, event_paths):
    # Set Ftrack environments
    os.environ["FTRACK_SERVER"] = ftrack_url
    os.environ["FTRACK_API_USER"] = username
    os.environ["FTRACK_API_KEY"] = api_key
    os.environ["FTRACK_EVENTS_PATH"] = event_paths

    # Get mongo hostname and port for testing mongo connection
    mongo_url = os.environ["AVALON_MONGO"].strip('/ ')
    result = urlparse(mongo_url)
    url_items = result.netloc.split("@")
    mongo_url = url_items[0]
    if len(url_items) == 2:
        mongo_url = url_items[1]

    mongo_url = "://".join([result.scheme, mongo_url])
    result = urlparse(mongo_url)

    mongo_hostname = result.hostname
    mongo_port = result.port

    # Current file
    file_path = os.path.dirname(os.path.realpath(__file__))

    # Threads data
    storer_name = "StorerThread"
    storer_port = 10001
    storer_path = "{}/sub_event_storer.py".format(file_path)
    storer_thread = None

    processor_name = "ProcessorThread"
    processor_port = 10011
    processor_path = "{}/sub_event_processor.py".format(file_path)
    processor_thread = None

    ftrack_accessible = False
    mongo_accessible = False

    printed_ftrack_error = False
    printed_mongo_error = False

    # Main loop
    while True:
        # Check if accessible Ftrack and Mongo url
        if not ftrack_accessible:
            ftrack_accessible = check_ftrack_url(ftrack_url)

        if not mongo_accessible:
            mongo_accessible = check_mongo_url(mongo_hostname, mongo_port)

        # Run threads only if Ftrack is accessible
        if not ftrack_accessible or not mongo_accessible:
            if not mongo_accessible and not printed_mongo_error:
                print("Can't access Mongo {}".format(mongo_url))

            if not ftrack_accessible and not printed_ftrack_error:
                print("Can't access Ftrack {}".format(ftrack_url))

            if storer_thread is not None:
                storer_thread.stop()
                storer_thread.join()
                storer_thread = None

            if processor_thread is not None:
                processor_thread.stop()
                processor_thread.join()
                processor_thread = None

            printed_ftrack_error = True
            printed_mongo_error = True

            time.sleep(1)
            continue

        printed_ftrack_error = False
        printed_mongo_error = False

        # Run backup thread which does not requeire mongo to work
        if storer_thread is None:
            storer_thread = socket_thread.SocketThread(
                storer_name, storer_port, storer_path
            )
            storer_thread.start()

        # If thread failed test Ftrack and Mongo connection
        elif not storer_thread.isAlive():
            storer_thread.join()
            storer_thread = None
            ftrack_accessible = False
            mongo_accessible = False

        if processor_thread is None:
            processor_thread = socket_thread.SocketThread(
                processor_name, processor_port, processor_path
            )
            processor_thread.start()

        # If thread failed test Ftrack and Mongo connection
        elif processor_thread.isAlive():
            processor_thread.join()
            processor_thread = None
            ftrack_accessible = False
            mongo_accessible = False

        time.sleep(1)


def main(argv):
    '''
    There are 4 values neccessary for event server:
    1.) Ftrack url - "studio.ftrackapp.com"
    2.) Username - "my.username"
    3.) API key - "apikey-long11223344-6665588-5565"
    4.) Path/s to events - "X:/path/to/folder/with/events"

    All these values can be entered with arguments or environment variables.
    - arguments:
        "-ftrackurl {url}"
        "-ftrackuser {username}"
        "-ftrackapikey {api key}"
        "-ftrackeventpaths {path to events}"
    - environment variables:
        FTRACK_SERVER
        FTRACK_API_USER
        FTRACK_API_KEY
        FTRACK_EVENTS_PATH

    Credentials (Username & API key):
    - Credentials can be stored for auto load on next start
    - To *Store/Update* these values add argument "-storecred"
        - They will be stored to appsdir file when login is successful
    - To *Update/Override* values with enviromnet variables is also needed to:
        - *don't enter argument for that value*
        - add argument "-noloadcred" (currently stored credentials won't be loaded)

    Order of getting values:
        1.) Arguments are always used when entered.
            - entered values through args have most priority! (in each case)
        2.) Credentials are tried to load from appsdir file.
            - skipped when credentials were entered through args or credentials
                are not stored yet
            - can be skipped with "-noloadcred" argument
        3.) Environment variables are last source of values.
            - will try to get not yet set values from environments

    Best practice:
    - set environment variables FTRACK_SERVER & FTRACK_EVENTS_PATH
    - launch event_server_cli with args:
    ~/event_server_cli.py -ftrackuser "{username}" -ftrackapikey "{API key}" -storecred
    - next time launch event_server_cli.py only with set environment variables
        FTRACK_SERVER & FTRACK_EVENTS_PATH
    '''
    parser = argparse.ArgumentParser(description='Ftrack event server')
    parser.add_argument(
        "-ftrackurl", type=str, metavar='FTRACKURL',
        help=(
            "URL to ftrack server where events should handle"
            " (default from environment: $FTRACK_SERVER)"
        )
    )
    parser.add_argument(
        "-ftrackuser", type=str,
        help=(
            "Username should be the username of the user in ftrack"
            " to record operations against."
            " (default from environment: $FTRACK_API_USER)"
        )
    )
    parser.add_argument(
        "-ftrackapikey", type=str,
        help=(
            "Should be the API key to use for authentication"
            " (default from environment: $FTRACK_API_KEY)"
        )
    )
    parser.add_argument(
        "-ftrackeventpaths", nargs='+',
        help=(
            "List of paths where events are stored."
            " (default from environment: $FTRACK_EVENTS_PATH)"
        )
    )
    parser.add_argument(
        '-storecred',
        help=(
            "Entered credentials will be also stored"
            " to apps dir for future usage"
        ),
        action="store_true"
    )
    parser.add_argument(
        '-noloadcred',
        help="Load creadentials from apps dir",
        action="store_true"
    )

    ftrack_url = os.environ.get('FTRACK_SERVER')
    username = os.environ.get('FTRACK_API_USER')
    api_key = os.environ.get('FTRACK_API_KEY')
    event_paths = os.environ.get('FTRACK_EVENTS_PATH')

    kwargs, args = parser.parse_known_args(argv)

    if kwargs.ftrackurl:
        ftrack_url = kwargs.ftrackurl

    if kwargs.ftrackeventpaths:
        event_paths = kwargs.ftrackeventpaths

    if not kwargs.noloadcred:
        cred = credentials._get_credentials(True)
        username = cred.get('username')
        api_key = cred.get('apiKey')

    if kwargs.ftrackuser:
        username = kwargs.ftrackuser

    if kwargs.ftrackapikey:
        api_key = kwargs.ftrackapikey

    # Check url regex and accessibility
    ftrack_url = check_ftrack_url(ftrack_url)
    if not ftrack_url:
        return 1

    # Validate entered credentials
    if not validate_credentials(ftrack_url, username, api_key):
        return 1

    # Process events path
    event_paths, not_found = process_event_paths(event_paths)
    if not_found:
        print(
            'WARNING: These paths were not found: {}'.format(str(not_found))
        )
    if not event_paths:
        if not_found:
            print('ERROR: Any of entered paths is valid or can be accesible.')
        else:
            print('ERROR: Paths to events are not set. Exiting.')
        return 1

    if kwargs.storecred:
        credentials._save_credentials(username, api_key, True)

    main_loop(ftrack_url, username, api_key, event_paths)


if __name__ == "__main__":
    # Register interupt signal
    def signal_handler(sig, frame):
        print("You pressed Ctrl+C. Process ended.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sys.exit(main(sys.argv))
