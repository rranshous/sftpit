

DATA_DIR = './data'


# the goal for now is to simply upload the data via sftp
import paramiko
from findfiles import find_files_iter as find_files
import sys

# get the username and password
assert len(argv) >= 5, 'must specify host, username, password'
host,username,password = tuple(sys.argv[2:5])

print 'connecting to %s' % host

# connect to our server
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host,username,password)
sftp = ssh.get_sftp()

# create an upload folder if it doesn't exist
REMOTE_DIR = 'uploads'
sftp.mkdir(REMOTE_DIR)
sftp.chdir(REMOTE_DIR)

print 'uploading to: %s' % REMOTE_DIR

# make sure we've got the full data dir
DATA_DIR = os.path.abspath(DATA_DIR)

print 'uploading from: %s' % DATA_DIR

# go through all the files recursively
for file_path in find_files(DATA_DIR):

    # we are going to upload every file blindly
    rel_path = file_path[len(DATA_DIR)+1:]

    print 'uploading rel_path: %s' % rel_path

    # this has a callback function .. interesting
    sftp.put(file_path,rel_path)

    print 'done uploading'

print 'done'
