# 2018 Peter Petrik (zilolv at gmail dot com)
# GNU General Public License 2 any later version

import argparse
import os
import sys
import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError

# inspired by
# https://github.com/dropbox/dropbox-sdk-python/blob/master/example/back-up-and-restore/backup-and-restore-example.py


class QGISUploadError(Exception):
    pass


# Uploads contents of LOCALFILE to Dropbox
# from dropbox's examples
# files < 150 MB, see https://stackoverflow.com/q/33810138/2838364
# files larger > 150 MB https://stackoverflow.com/a/40114617/2838364
def backup(local, remote):
    file_size = os.path.getsize(local)
    CHUNK_SIZE = 4 * 1024 * 1024

    with open(local, 'rb') as f:
        # We use WriteMode=overwrite to make sure that the settings in the file
        # are changed on upload
        print("Uploading " + local + " to Dropbox as " + remote + "...")
        try:
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), remote, mode=WriteMode('overwrite'))
            else:
                upload_session_start_result = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id,
                                                           offset=f.tell())
                commit = dropbox.files.CommitInfo(path=remote)

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= CHUNK_SIZE:
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE),
                                                        cursor,
                                                        commit)
                    else:
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE),
                                                           cursor)
                        cursor.offset = f.tell()

        except ApiError as err:
            # This checks for the specific error where a user doesn't have
            # enough Dropbox space quota to upload this file
            if (err.error.is_path() and
                    err.error.get_path().reason.is_insufficient_space()):
                sys.exit("ERROR: Cannot back up; insufficient space.")
            elif err.user_message_text:
                print(err.user_message_text)
                sys.exit()
            else:
                print(err)
                sys.exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload QGIS package to store')

    parser.add_argument('--package',
                        required=True,
                        help='dmg file to upload')
    parser.add_argument('--destination',
                        required=True,
                        help='full filename on dropbox where to upload file')
    parser.add_argument('--dropbox',
                        required=True,
                        type=argparse.FileType('r'),
                        help='File with dropbox APIv2 Token')

    args = parser.parse_args()

    print("QGIS PACKAGE" + args.package)
    print("OUTPUT DESTINATION: " + args.destination)

    if not os.path.exists(args.package):
        raise QGISUploadError(args.package + " does not exists")

    # parse token
    token = args.dropbox.read().strip()
    if len(token) != 64:
        sys.exit("ERROR: Looks like your dropbox access token is not valid, should be 64 char long")

    # Create an instance of a Dropbox class, which can make requests to the API.
    print("Creating a Dropbox object...")
    dbx = dropbox.Dropbox(token)

    # Check that the access token is valid
    try:
        dbx.users_get_current_account()
    except AuthError as err:
        sys.exit("ERROR: Invalid access token; try re-generating an "
            "access token from the app console on the web.")

    # Create a backup of the current settings file
    backup(local=args.package, remote=args.destination)

    # Share for public
    r = dbx.sharing_create_shared_link_with_settings(args.destination)

    print("Done! " + str(r.url))
