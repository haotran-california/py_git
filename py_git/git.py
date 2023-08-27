import os 
import hashlib
import zlib
import py_git.models as models
import py_git.cache as cache
import py_git.cli as cli
import tempfile
import shutil
from py_git import SUCCESS, INIT_ERROR, F_EXIST_ERROR, F_LARGE_ERROR, HASH_EXISTS_ERROR
from typing import Tuple
from collections import defaultdict
from datetime import datetime 


SIZE = 4096

def init() -> int: 
    #check whether a .git files exist already 
    git_dir = ".git"
    if os.path.exists(git_dir):
        return INIT_ERROR

    objects_dir = os.path.join(git_dir, "objects")
    refs_dir = os.path.join(git_dir, "refs")
    heads_dir = os.path.join(git_dir, "refs/heads")
    master_file = os.path.join(git_dir, "refs/heads/master")
    head_file = os.path.join(git_dir, "HEAD")

    os.makedirs(objects_dir)
    for i in range(256): 
        object_sub_dir = os.path.join(objects_dir, '{:02x}'.format(i))
        os.mkdir(object_sub_dir)
    
    os.makedirs(refs_dir)
    with open(head_file, "w") as f:
        f.write("ref: refs/heads/master")

    os.makedirs(heads_dir)
    with open(master_file, "w") as f: 
        f.write("")
    
    return SUCCESS


def cat_file(sha1_hash: str, byteObject: models.ByteFile) -> int: 
    object_dir = ".git/objects"
    folder_name = sha1_hash[:2]
    file_name = sha1_hash[2:]
    folder_path = os.path.join(object_dir, folder_name)
    file_path = os.path.join(folder_path, file_name)

    if not os.path.exists(file_path):
        return F_EXIST_ERROR 

    decompressor =  zlib.decompressobj()
    decompressed_content = b""
    with open(file_path, "rb") as file: 
        while True: 
            chunk = file.read(4086)
            if not chunk: 
                break
            decompressed_content += decompressor.decompress(chunk) #should this be += ? 

        decompressed_content += decompressor.flush()
        data = parseByteFormat(decompressed_content)
        #byteObject = models.ByteFile(data[0], data[1], data[2])
        byteObject.type = data[0]
        byteObject.size = data[1]
        byteObject.content = data[2]

    return SUCCESS 



def parseByteFormat(input_str): 
    data = input_str.decode("utf-8")
    parseNullByte = data.split('\0')
    raw_object = parseNullByte[0].split(" ")
    raw_contents = parseNullByte[1]
    object_type, size, contents = raw_object[0], raw_object[1], raw_contents 

    return (object_type, size, contents)


def hash_file(file_path: str, _type: str = "blob"): 

    if not os.path.exists(file_path): 
        return (F_EXIST_ERROR, None) 

    #cap file size to 500 megabytes 
    size_in_bytes = str(os.path.getsize(file_path))
    # size_in_mb = size_in_bytes / (1024 * 1024)
    # if size_in_mb > 500: 
    #     return F_LARGE_ERROR

    #how to handle encoding? 
    blob_string = f"{_type} {size_in_bytes}\0".encode("utf-8") 

    compressor = zlib.compressobj()
    compressed_content = compressor.compress(blob_string)
    with open(file_path, "rb") as file:
        while(True): 
            chunk = file.read(SIZE)
            if not chunk: 
                break 
            compressed_content += compressor.compress(chunk)
    compressed_content += compressor.flush()

    sha1 = hashlib.sha1()
    sha1.update(compressed_content)
    hex_sha1 = sha1.hexdigest()

    write_file = ".git/objects/" + hex_sha1[0:2] + "/" + hex_sha1[2:]
    with open(write_file, "wb") as file: 
        file.write(compressed_content)


    return (SUCCESS, hex_sha1) 

def database_add_hash(sha1_hash: str) -> int: 
    object_dir = ".git/objects"
    folder_name = sha1_hash[:2]
    folder_path = os.path.join(object_dir, folder_name)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    file_path = os.path.join(folder_path, sha1_hash[2:])
    if os.path.exists(file_path):
        return HASH_EXISTS_ERROR

    with open(file_path, "wb") as file:
        file.write(sha1_hash.encode("utf-8"))

    return SUCCESS


def update_cache(file_path: str): 
    #check filepath exists 
    if not os.path.exists(file_path): 
        return

    #ASSUME FIRST ADD
    hash_result, sha1 = hash_file(file_path)

    _type = "blob"
    mode = os.stat(file_path).st_mode 
    cache_handler = cache.CacheHandeler()
    cache_handler.insert_cache(_type, mode, sha1, file_path)
    cache_handler.printCache()
    #how to deal with the same file being added to the cache? 
    #replace the file, if the file has changed than... ? 

    #how to deal with duplicates in the .idx file? 
    #in the database the uid is the filepath / dir
    #<file-path> <mode> <type> <sha1>

def write_tree() -> str: 
    cache_handler = cache.CacheHandeler()
    current_cache = cache_handler.load_cache()
    cache_array = current_cache.contents
    numEntries = current_cache.header.numEntries

    #create nested hashmap structure
    #this data structure should be stored and serialilzed in the cache
    files_list = []
    files_hash = {}
    for cache_object in cache_array: 
        files_list.append(cache_object.file_path)
        files_hash[cache_object.file_path] = cache_object.sha1

    fileTreeHash = create_hash(files_list)
    sha1 = helper(fileTreeHash["root"], files_hash, 1, "")
    return sha1

def create_hash(files_list): 
    tree = defaultdict(dict)
    tree['root'] = {}

    for file_path in files_list:
        path_parts = file_path.split('/')
        add_path(tree['root'], path_parts)

    return tree

def add_path(tree, path_parts):
    if path_parts:
        current = path_parts[0]
        tree[current] = add_path(tree.get(current, {}), path_parts[1:])
    return tree

def helper(tree, files_hash, level: int, dirPath: str):
    treeText = ""
    for key, value in tree.items():
        obj, sha, filename = "", "", ""
        if "." in key: 
            obj = "blob"
            filename = key
            filepath = (dirPath + "/" + key).lstrip("/")
            sha = files_hash[filepath]
        
        else: 
            if isinstance(value, dict):
                obj = "tree"
                filename = (dirPath + "/" + key).lstrip("/") 
                sha = helper(value, files_hash, level + 1, filename)

        line = f"{obj} {sha} {filename} "
        treeText += (line)
            
    with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as temp: 
        temp.write(treeText.rstrip(" "))
        temp.flush()
        temp_file_path = os.path.join('.', temp.name)
        hash_status, hex_sha1 = hash_file(temp_file_path, "tree")

    return hex_sha1


def commit_tree(tree_sha: str, raw_user_input: str):
    #validate sha1
    fileObject = models.ByteFile(None, None, None)
    cat_result = cat_file(tree_sha, fileObject) 

    if fileObject.type != "tree": 
        return -1
    
    home_file_path = os.path.expanduser('~')
    cwd = os.getcwd()
    os.chdir(home_file_path)
    name, email = extract_name_and_email(home_file_path + "/.py_git_config")
    os.chdir(cwd)

    current_date_time = datetime.now()
    formatted_date_time = current_date_time.strftime("Date:   %a %b %d %H:%M:%S %Y %z")

    # with open(working_head_file_path, 'r') as file: 
    #     parentCommit = file.readline()

    parentCommit = extract_commit_from_head()

    delimiter = '\x1F'
    commitString = ""
    treeLine = f"tree {tree_sha}{delimiter}"
    prevCommitLine = f"parent {parentCommit}{delimiter}"
    authorLine = f"author {name} <{email}>{delimiter}"
    commitLine = f"commiter {name} <{email}>{delimiter}"
    commitString += (treeLine + prevCommitLine + authorLine + commitLine) + '\n'
    commitString += raw_user_input

    with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as temp: 
        temp.write(commitString)
        temp.flush()
        temp_file_path = os.path.join('.', temp.name)
        hash_status, hex_sha1 = hash_file(temp_file_path, "commit")


    branch_name = extract_ref_from_head()
    if branch_name: 
        working_head_file_path = ".git/refs/heads/" + branch_name
        with open(working_head_file_path, 'w') as file:
            file.write(hex_sha1)

    return hex_sha1

def extract_name_and_email(file_path: str):
    name = ''
    email = ''

    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('name = '):
                name = line.split(' = ')[1]
            elif line.startswith('email = '):
                email = line.split(' = ')[1]

    return name, email

def extract_ref_from_head(file_path=".git/HEAD"):
    ref_prefix = "ref: refs/heads/"
    with open(file_path, 'r') as file:
        content = file.read().strip()
        if content.startswith(ref_prefix):
            return content[len(ref_prefix):] 

    print("The file does not contain the expected prefix.")
    return None

def extract_commit_from_head(file_path=".git/HEAD"):
    content = extract_ref_from_head()

    if content == None: 
        file_path = ".git/HEAD"
        with open(file_path) as file: 
            line = file.readline().strip()
            return line

    branch_file_path = ".git/refs/heads/" + content 
    with open(branch_file_path, 'r') as file: 
        current_commit_sha = file.readline()

    return current_commit_sha

def extract_tree_from_commit(commit_sha: str): 
    delimiter = '\x1F'
    fileObject = models.ByteFile(None, None, None)
    cat_file(commit_sha, fileObject)

    raw_commit_data = fileObject.content.split(delimiter)
    treeLine = raw_commit_data[0]
    tree_sha = treeLine.split(" ")[1]
    return tree_sha

def rm(file, all): 
    cache_handler = cache.CacheHandeler()
    result = None
    if all: 
        result = cache_handler.remove_all()
    else: 
        result = cache_handler.remove(file)

    return result

def log(): 
    # branch_name = extract_ref_from_head()
    # working_head_file_path = ".git/refs/heads/" + branch_name
    # with open(working_head_file_path, 'r') as file: 
    #     current_commit_sha = file.readline()

    #TEST
    current_commit_sha = extract_commit_from_head()

    log_helper(current_commit_sha)

def log_helper(commit_sha): 
    fileObject = models.ByteFile(None, None, None)
    cat_file(commit_sha, fileObject)
    input_object = (fileObject.type, fileObject.size, fileObject.content)
    cli.display_content(input_object)


    delimiter = '\x1F'
    raw_commit_data = fileObject.content.split(delimiter)
    parent_commit_data = raw_commit_data[1].split(" ")
    prevCommit = None
    if len(parent_commit_data) == 2: 
        prevCommit = parent_commit_data[1]

    if not prevCommit: 
        return

    print("----------------------------------")
    log_helper(prevCommit)

def branch(new_branch_name): 
    new_branch_path = ".git/refs/heads/" + new_branch_name
    if os.path.exists(new_branch_path):
        print("branch alread exists")
        return -1

    #TEST
    current_commit_sha = extract_commit_from_head()
    # working_head_file_path = ".git/refs/heads/" + branch_name
    # with open(working_head_file_path, 'r') as file: 
    #     current_commit_sha = file.readline()

    with open(new_branch_path, "w") as file: 
        file.write(current_commit_sha)

    with open(".git/HEAD", "w") as file: 
        file.write(f"ref: refs/heads/{new_branch_name}")

def checkout(branch_name: str = "", input_commit_sha: str = ""): 
    if not branch_name and not input_commit_sha: 
        return 0 

    checkout_tree_sha = ""
    if branch_name: 
        branch_file_path = ".git/refs/heads/" + branch_name
        if not os.path.exists(branch_file_path):
            print("branch does not exist")
            return 0 

        with open(".git/refs/heads/" + branch_name, "r") as file: 
            checkout_commit_sha = file.readline().strip()

        #write ATTACHED HEAD
        with open(".git/HEAD", "w") as file: 
            file.write(f"ref: refs/heads/{branch_name}")

        checkout_tree_sha = extract_tree_from_commit(checkout_commit_sha)
    else: 
        #write DETACHED HEAD
        with open(".git/HEAD", "w") as file: 
            file.write(input_commit_sha)

        checkout_tree_sha = extract_tree_from_commit(input_commit_sha)

    cache_handler = cache.CacheHandeler()
    current_cache = cache_handler.load_cache()
    clear_working_tree(current_cache)
    cache_handler.remove_all()
    load_tree_into_cache(checkout_tree_sha, "", cache_handler)
    current_cache = cache_handler.load_cache()
    load_cache_into_working_tree(current_cache)

def load_tree_into_cache(tree_sha: str, dir_path: str, cache): 
    fileObject = models.ByteFile(None, None, None)
    cat_file(tree_sha, fileObject) 
    tree = fileObject.content.split(" ")

    n = len(tree)
    for i in range(0, n, 3):
        file_type = tree[i]
        hash_code = tree[i + 1]
        file_name = tree[i + 2]

        if file_type == "blob": 
            cache.insert_cache(file_type, 0000, hash_code, dir_path + file_name)

        if file_type == "tree": 
            load_tree_into_cache(hash_code, file_name + "/", cache)

def load_cache_into_working_tree(current_cache): 
    cache_array = current_cache.contents

    for entry in cache_array: 
        fileObject = models.ByteFile(None, None, None)   
        cat_file(entry.sha1, fileObject)

        directory = os.path.dirname(entry.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(entry.file_path, "w") as file: 
            file.write(fileObject.content)
        
def clear_working_tree(current_cache): 
    cache_array = current_cache.contents
    file_paths = [x.file_path for x in cache_array]
    delete_files_and_directories(file_paths)

def delete_files_and_directories(file_paths):
    # Delete files first
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)
            
    # Identify directories and sort them in reverse order
    # so that nested directories get deleted first
    directories = set(os.path.dirname(file_path) for file_path in file_paths)
    sorted_directories = sorted(directories, key=len, reverse=True)
    
    # Delete directories
    for directory in sorted_directories:
        if os.path.exists(directory):
            try:
                os.rmdir(directory)  # Remove empty directories
            except OSError:
                continue

def status(): 
    cache_handler = cache.CacheHandeler()
    cache_handler.printCache()
#-----------------------------------

    


#check for correct write_tree by copying the ls tree code
def ls_tree(): 
    pass 

