
# the goal for now is to simply upload the data via sftp
import paramiko
from findfiles import find_files_iter as find_files
import sys, os, random, errno
import json
from stat import ST_SIZE, ST_MTIME, S_ISDIR
import atexit


# get the username and password
local_bucket,remote_bucket,host,username,password = tuple(sys.argv[1:6])

print 'local_bucket:',local_bucket
print 'remote_bucket:',remote_bucket
print 'host:',host
print 'username:',username
print 'password:',len(password) * '*'

# check our lock. if it's set exit if it
# isn't set than set it and go
lock_path = '/tmp/sftpit.%s.lock' % remote_bucket.replace('/','_')
try:
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
except OSError, e:
    if e.errno == errno.EEXIST:
        # file exists, we don't have lock
        print 'failed, lock exists'
        sys.exit(1)
    # we got lock! don't actually need the file
    os.close(fd)

# setup function to delete file when done
atexit.register(lambda: os.unlink(lock_path))

print 'connecting to %s' % host

# connect to our server
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host,
            username=username,
            password=password)
sftp = ssh.open_sftp()

# create an upload folder if it doesn't exist
try:
    sftp.mkdir(remote_bucket)
except:
    pass # already there

# move into our new dir
sftp.chdir(remote_bucket)

print 'uploading to: %s' % remote_bucket

# make sure we've got the full data dir
local_bucket = os.path.abspath(local_bucket)

print 'uploading from: %s' % local_bucket

# collect up a snapshot of our state
snapshot = {}

print 'reading old snapshot'

# read in the old snapshot
if os.path.exists('snapshot.json'):
    with file('./snapshot.json','r') as fh:
        old_snapshot = json.loads(fh.read())
else:
    print 'old snapshot not found'
    old_snapshot = {}

print

# go through all the files recursively
known_folders = []
for file_path in find_files(local_bucket):

    # get some info on our to-upload file
    #stats = os.stat(file_path)

    # where are we uploading it to ?
    rel_path = file_path[len(local_bucket)+1:]
    
    print 'attempting upload uploading: %s' % rel_path

    # glean some info about our remote file
    try:
        remote_stats = sftp.stat(rel_path)
    except IOError:

        print 'does not exist remotely'

        # guess it's not there
        remote_stats = None

        # if it's not there now but it's in
        # the old snapshot that means it's since
        # been deleted from the server, lets
        # delete it locally
        if rel_path in old_snapshot:

            print 'deleting local file'
            os.unlink(file_path)

            continue

    # if we have remote stats lets see who's
    # file is newer
    if remote_stats and old_snapshot.get(rel_path):
        print 'have remote stats'

        # when were the files modified?
        mtime = old_snapshot.get(rel_path).get('mtime')
        r_mtime = remote_stats.st_mtime

        print 'mtimes: %s %s' % (mtime,r_mtime)

        # are we newer ?
        if mtime > r_mtime:
            print 'we are newer ! uploading file'

            # we are newer proceed w/ upload !

            # make sure the folder we are uploading to exists
            folder_path = '/'.join(rel_path.split('/')[:-1])
            print 'remote folder: %s' % folder_path
            if folder_path and folder_path not in known_folders:
                print 'remote folder path not known'
                try:
                    sftp.mkdir(folder_path)
                except:
                    print 'creation attempt failed, exists'
                    # already exists
                    pass

                # add this folder to our known to exists
                known_folders.append(folder_path)

            # this has a callback function .. interesting
            sftp.put(file_path,rel_path)

        elif r_mtime > mtime:
            print 'they are newer!, downloading file'

            # we must bow before the newer version
            sftp.get(rel_path,file_path)

        else:
            print 'same file, no upload or download'

    else:
        print 'new file uploading'

        # make sure the folder we are uploading to exists
        folder_path = '/'.join(rel_path.split('/')[:-1])
        print 'remote folder: %s' % folder_path
        if folder_path and folder_path not in known_folders:
            print 'remote folder path not known'
            try:
                sftp.mkdir(folder_path)
            except:
                print 'creation attempt failed, exists'
                # already exists
                pass

            # add this folder to our known to exists
            known_folders.append(folder_path)

        # no remote stats? throw it up
        sftp.put(file_path,rel_path)

        # get the remote stats back from the server
        remote_stats = sftp.stat(rel_path)

    # add this to our snapshot
    snapshot[rel_path] = {'mtime':remote_stats.st_mtime,
                          'size':remote_stats.st_size}

    print


# we want to delete anything from the server
# which was in our snapshot but isn't any longer
diff = set(old_snapshot.keys()) - set(snapshot.keys())
for rel_path in diff:
    print 'deleting from server: %s' % rel_path
    try:
        sftp.remove(rel_path)
    except IOError:
        # there is a chance it doesn't exist any
        # more on the other end
        print 'file did not exist remotely'
    print

# now that we've gone over all the files on our
# end, we need to go through all the other files
# which exist on the remote end and download them

# we are going to recursively go through all the
# files on the server. if it already exists in our
# snapshot than we can ignore it, if it does not exist
# than we need to download it
print 'searching server'

def recursive_find(dirs):

    # list of (rel) dirs which
    # we will pass back to ourself
    to_search = []

    for _dir in dirs:
        print 'searching %s' % _dir

        # list all the things in the dir
        for file_name in sftp.listdir(_dir):
            print
            print 'inspecting: %s' % file_name

            # figure out it's relative path
            rel_path = '%s/%s' % (_dir,file_name)

            #(cheat a lil) cut off ./
            if rel_path.startswith('./'):
                rel_path = rel_path[2:]

            # see if we already know about it
            if rel_path in snapshot:
                continue # no need to reinvestigate

            # get it's stats
            remote_stats = sftp.stat(rel_path)

            # if it's a dir than we need to another
            # recursive lvl
            if S_ISDIR(remote_stats.st_mode):
                print 'is dir'
                to_search.append(rel_path)

            else:
                # if it's a file download it
                abs_path = os.path.join(local_bucket,rel_path)

                # make sure the folder exists
                folder_path = os.path.dirname(abs_path)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                print 'getting file: %s => %s' % (rel_path,abs_path)
                sftp.get(rel_path,abs_path)

                # add it to snapshot
                snapshot[rel_path] = {'mtime':remote_stats.st_mtime,
                                      'size':remote_stats.st_size}


    # keep on keepin' on
    if to_search:
        recursive_find(to_search)

recursive_find(['.'])

# save out our snapshot
print
print 'writing new snapshot'
with file('snapshot.json','w') as fh:
    fh.write(json.dumps(snapshot))

print
print 'done'
