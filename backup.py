

DATA_DIR = './data'


# the goal for now is to simply upload the data via sftp
import paramiko
from findfiles import find_files_iter as find_files
import sys, os, random
import json


# get the username and password
assert len(sys.argv) >= 4, 'must specify host, username, password'

host,username,password = tuple(sys.argv[1:4])

print 'connecting to %s' % host

# connect to our server
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host,
            username=username,
            password=password)
sftp = ssh.open_sftp()

# create an upload folder if it doesn't exist
REMOTE_DIR = 'uploads'
try:
    sftp.mkdir(REMOTE_DIR)
except:
    pass # already there

# move into our new dir
sftp.chdir(REMOTE_DIR)

print 'uploading to: %s' % REMOTE_DIR

# make sure we've got the full data dir
DATA_DIR = os.path.abspath(DATA_DIR)

print 'uploading from: %s' % DATA_DIR

# collect up a snapshot of our state
snapshot = {}

# go through all the files recursively
for file_path in find_files(DATA_DIR):

    # where are we uploading it to ?
    rel_path = file_path[len(DATA_DIR)+1:]

    print 'uploading rel_path: %s' % rel_path

    # this has a callback function .. interesting
    sftp.put(file_path,rel_path)

    # add this to our snapshot
    snapshot[rel_path] = {}

    print 'done uploading'

print 'reading old snapshot'

# read in the old snapshot
if os.path.exists('snapshot.json'):
    with file('./snapshot.json','r') as fh:
        old_snapshot = json.loads(fh.read())
else:
    print 'old snapshot not found'
    old_snapshot = {}

# we want to delete anything from the server
# which was in our snapshot but isn't any longer
diff = set(old_snapshot.keys()) - set(snapshot.keys())
for rel_path in diff:
    print 'deleting from server: %s' % rel_path
    sftp.remove(rel_path)

# save out our snapshot
print 'writing new snapshot'
with file('snapshot.json','w') as fh:
    fh.write(json.dumps(snapshot))

print
print 'done'
