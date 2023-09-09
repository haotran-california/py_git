import os 
import hashlib
import zlib
import py_git.models as models
import py_git.cache as cache
import py_git.cli as cli
import py_git.utils as utils
import tempfile
import subprocess
from py_git import SUCCESS, INIT_ERROR, F_EXIST_ERROR, F_LARGE_ERROR, HASH_EXISTS_ERROR
from py_git import DEV_NULL_FILE
from typing import Tuple, List
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

    size_in_bytes = str(os.path.getsize(file_path))

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

def commit_tree(tree_sha: str, raw_user_input: str, commit_parents= []):
    #validate sha1
    fileObject = models.ByteFile(None, None, None)
    cat_file(tree_sha, fileObject) 

    if fileObject.type != "tree": 
        return -1
    
    home_file_path = os.path.expanduser('~')
    cwd = os.getcwd()
    os.chdir(home_file_path)
    name, email = utils.extract_name_and_email(home_file_path + "/.py_git_config")
    os.chdir(cwd)

    current_date_time = datetime.now()
    formatted_date_time = current_date_time.strftime("Date:   %a %b %d %H:%M:%S %Y %z")

    parentCommit = utils.extract_commit_from_head()

    delimiter = '\x1F'
    commitString = ""
    treeLine = f"tree {tree_sha}{delimiter}"
    prevCommitLine = f"parent {parentCommit}{delimiter}"
    if commit_parents: 
        prevCommitLine = f"parent {commit_parents[0]} {commit_parents[1]}{delimiter}"
    authorLine = f"author {name} <{email}>{delimiter}"
    commitLine = f"commiter {name} <{email}>{delimiter}"
    commitString += (treeLine + prevCommitLine + authorLine + commitLine) + '\n'
    commitString += raw_user_input

    with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as temp: 
        temp.write(commitString)
        temp.flush()
        temp_file_path = os.path.join('.', temp.name)
        hash_status, hex_sha1 = hash_file(temp_file_path, "commit")


    branch_name = utils.extract_ref_from_head()
    if branch_name: 
        working_head_file_path = ".git/refs/heads/" + branch_name
        with open(working_head_file_path, 'w') as file:
            file.write(hex_sha1)
    else: 
        with open(".git/HEAD", 'w') as file: 
            file.write(hex_sha1)

    return hex_sha1

def rm(file: str, all: bool): 
    cache_handler = cache.CacheHandeler()
    result = None
    if all: 
        result = cache_handler.remove_all()
    else: 
        result = cache_handler.remove(file)

    return result

def log(): 
    current_commit_sha = utils.extract_commit_from_head()

    log_helper(current_commit_sha)

def log_helper(commit_sha: str): 
    fileObject = models.ByteFile(None, None, None)
    cat_result = cat_file(commit_sha, fileObject)
    #if cat_result == F_EXIST_ERROR: 
    #    return 0 
    input_object = (fileObject.type, fileObject.size, fileObject.content)
    cli.display_content(input_object)

    prevCommit = utils.extract_commit_from_commit(commit_sha)

    if not prevCommit: 
        return

    print("----------------------------------")
    log_helper(prevCommit)

def branch(new_branch_name: str): 
    new_branch_path = ".git/refs/heads/" + new_branch_name
    if os.path.exists(new_branch_path):
        print("branch alread exists")
        return -1

    current_commit_sha = utils.extract_commit_from_head()

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

        checkout_tree_sha = utils.extract_tree_from_commit(checkout_commit_sha)
    else: 
        #write DETACHED HEAD
        with open(".git/HEAD", "w") as file: 
            file.write(input_commit_sha)

        checkout_tree_sha = utils.extract_tree_from_commit(input_commit_sha)

    cache_handler = cache.CacheHandeler()
    current_cache = cache_handler.load_cache()
    utils.clear_working_tree(current_cache)
    cache_handler.remove_all()
    utils.load_tree_into_cache(checkout_tree_sha, "", cache_handler)
    current_cache = cache_handler.load_cache()
    utils.load_cache_into_working_tree(current_cache)


def status(): 
    #display current branch
    current_ref = utils.extract_ref_from_head()
    if current_ref: 
        print(f"On branch {current_ref}\n")
    else: 
        head_commit = utils.extract_commit_from_head()
        print(f"Detached head at {head_commit}")

    #display modified unstaged files
    modified_files = []
    cache_handler = cache.CacheHandeler()
    loaded_cache = cache_handler.load_cache()
    cache_content_array = loaded_cache.contents
    cache_file_paths_array = [x.file_path for x in cache_content_array]

    for cache_entry in cache_content_array: 
        file_path, sha1 = cache_entry.file_path, cache_entry.sha1
        fileObject = models.ByteFile(None, None, None)   
        cat_file(sha1, fileObject)

        #write cache file -> temp file 
        #compare temp file with current file
        with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as temp: 
            temp.write(fileObject.content)
            temp.flush()
            temp_file_path = os.path.join('.', temp.name)
            diff_output = utils.run_diff_with_diffstat(temp_file_path, file_path)
            
        if diff_output != " 0 files changed": 
            modified_files.append(file_path)

    if modified_files: 
        print("Changes to be commited: ")
        for file in modified_files: 
            print(f"\t{file}")
        print()

    #display untracked files
    untracked_files = []
    all_files = utils.get_all_files()
    cwd = os.getcwd()
    relative_paths = [os.path.relpath(file_path, cwd) for file_path in all_files]

    for file in relative_paths: 
        if file not in cache_file_paths_array: 
            untracked_files.append(file)

    if untracked_files: 
        print("Untracked files: ")
        for file in untracked_files: 
            print(f"\t{file}")

def merge(merge_target_branch: str): 
    #check error cases
    current_branch = utils.extract_ref_from_head()
    if not current_branch: 
        print("Cannot merge with DETACHED HEAD")
        return 0 

    merge_branch_path = ".git/refs/heads/" + merge_target_branch
    if not os.path.exists(merge_branch_path): 
        print("Merge branch does not exist")
        return 0 

    #create array of commit histories 
    with open(".git/refs/heads/" + current_branch) as file: 
        current_commit_sha = file.read()

    with open(".git/refs/heads/" + merge_target_branch) as file: 
        merge_commit_sha = file.read()

    current_commit_history = []
    merge_commit_history = []

    list_commit_history_from_commit(current_commit_sha, current_commit_history)
    list_commit_history_from_commit(merge_commit_sha, merge_commit_history)

    #check for fast forward
    for sha in merge_commit_history: 
        if sha == current_commit_sha: 
            print("Merged with fast-forward")
            with open(".git/refs/heads/" + current_branch, "w") as file: 
                file.write(merge_commit_sha)
            return 1 

    #find common ancestor
    common_ancestor = find_common_ancestor(current_commit_history, merge_commit_history)

    #create merge in working tree
    checkout("", common_ancestor)
    apply_threeway_merge(common_ancestor, current_commit_sha, merge_commit_sha)

    #create tree
    cache_handler = cache.CacheHandeler()
    cache_handler.remove_all()
    all_files = []
    get_all_files_from_three_commits(common_ancestor, current_commit_sha, merge_commit_sha, all_files)
    for file in all_files: 
        update_cache(file)
    working_tree_sha = write_tree()

    #create new commit 
    commit_parents = [current_commit_sha, merge_commit_sha]
    new_commit_sha = commit_tree(working_tree_sha, f"Merge: {current_branch} {merge_target_branch}", commit_parents)

    with open(".git/refs/heads/" + current_branch, "w") as file: 
        file.write(new_commit_sha)

    with open(".git/refs/heads/" + merge_target_branch, "w") as file: 
        file.write(new_commit_sha)


    return 1 

def list_commit_history_from_commit(commit_sha: str, history: List[str]): 
    history.append(commit_sha)
    prev_commit_sha = utils.extract_commit_from_commit(commit_sha)
    if not prev_commit_sha: 
        return

    list_commit_history_from_commit(prev_commit_sha, history)

def find_common_ancestor(array_1: List[str], array_2: List[str]): 
    s1 = set(array_1)
    s2 = set(array_2)

    intersection = s1.intersection(s2)
    for ele in array_1: 
        if ele in intersection: 
            return ele

def get_all_files_from_three_commits(a: str, b: str, c: str, all_files_list: List[str]): 
    # exclude files which are only in ancestor 
    a_tree = utils.extract_tree_from_commit(a)
    b_tree = utils.extract_tree_from_commit(b)
    c_tree = utils.extract_tree_from_commit(c)

    a_hash, b_hash, c_hash = {}, {}, {}
    load_tree_into_hash(a_tree, "", a_hash)
    load_tree_into_hash(b_tree, "", b_hash)
    load_tree_into_hash(c_tree, "", c_hash)

    for key in b_hash.keys(): 
        all_files_list.append(key)

    for key in c_hash.keys(): 
        all_files_list.append(key)

    for key in a_hash.keys(): 
        if key not in b_hash and key not in c_hash: 
            continue
        all_files_list.append(key) 


def apply_threeway_merge(ancestor_sha: str, m1_sha: str, m2_sha: str): 
    ancestor_tree = utils.extract_tree_from_commit(ancestor_sha)
    m1_tree = utils.extract_tree_from_commit(m1_sha)
    m2_tree = utils.extract_tree_from_commit(m2_sha)

    ancestor_hash, m1_hash, m2_hash = {}, {}, {}
    load_tree_into_hash(ancestor_tree, "", ancestor_hash)
    load_tree_into_hash(m1_tree, "", m1_hash)
    load_tree_into_hash(m2_tree, "", m2_hash)
    
    common_file_set = set(ancestor_hash.keys()) & set(m1_hash.keys()) & set(m2_hash.keys()) 
    for key in common_file_set: 
        apply_merge(key, m1_hash[key], m2_hash[key])
        m1_hash.pop(key)
        m2_hash.pop(key)

    # files in ancestor and current branch or ancestor and merge branch
    # but not in all three branches
    ancestor_and_current_set = set(ancestor_hash).intersection(set(m1_hash))
    for file in ancestor_and_current_set: 
        temp_file_ancestor = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        temp_file_current = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        _ancestor_sha = ancestor_hash[file]
        current_sha = m1_hash[file]
        fileObject = models.ByteFile(None, None, None)
        cat_file(_ancestor_sha, fileObject)
        temp_file_ancestor.write(fileObject.content)
        temp_file_ancestor.flush()
        cat_file(current_sha, fileObject)
        temp_file_current.write(fileObject.content)
        temp_file_current.flush()

        diff_string = utils.run_diff(temp_file_ancestor.name, temp_file_current.name, file, file)
        apply_patch(diff_string)
        print(diff_string)

        temp_file_ancestor.close()
        temp_file_current.close()
        m1_hash.pop(file)

    ancestor_and_merge_set = set(ancestor_hash).intersection(set(m2_hash))
    for file in ancestor_and_merge_set: 
        temp_file_ancestor = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        temp_file_merge = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        _ancestor_sha = ancestor_hash[file]
        merge_sha = m2_hash[file]
        fileObject = models.ByteFile(None, None, None)
        cat_file(_ancestor_sha, fileObject)
        temp_file_ancestor.write(fileObject.content)
        temp_file_ancestor.flush()
        cat_file(merge_sha, fileObject)
        temp_file_merge.write(fileObject.content)
        temp_file_merge.flush()

        diff_string = utils.run_diff(temp_file_ancestor.name, temp_file_merge.name, file, file)
        apply_patch(diff_string)

        temp_file_ancestor.close()
        temp_file_merge.close()
        m2_hash.pop(file)

    # files in both current and merge branch but not ancestor 
    # merge branch -> current branch
    conflict_file_set = set(m1_hash).intersection(set(m2_hash))
    for file in conflict_file_set: 
        temp_file_current = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        temp_file_merge = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
        current_sha = m1_hash[file]
        merge_sha = m2_hash[file]
        fileObject = models.ByteFile(None, None, None)
        cat_file(current_sha, fileObject)
        #load the current version before running the patch 
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w") as f:
            f.write(fileObject.content) 
            f.flush()
        temp_file_current.write(fileObject.content)
        temp_file_current.flush()
        cat_file(merge_sha, fileObject)
        temp_file_merge.write(fileObject.content)
        temp_file_merge.flush()

        diff_string = utils.run_diff(temp_file_merge.name, temp_file_current.name, file, file)
        apply_patch(diff_string)

        temp_file_current.close()
        temp_file_merge.close()
        m2_hash.pop(file)

    # files exclusive to current or merge branch
    for file in m1_hash.keys(): 
        file_sha = m1_hash[file]
        write_sha_into_working_tree(file, file_sha)

    for file in m2_hash.keys(): 
        file_sha = m2_hash[file]
        write_sha_into_working_tree(file, file_sha)

def apply_merge(fileA: str, fileB_sha: str, fileC_sha: str): 
    tempB = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
    tempC = tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True)
    fileObject = models.ByteFile(None, None, None)

    cat_file(fileB_sha, fileObject)
    tempB.write(fileObject.content)
    tempB.flush()
    tempB_file_path = os.path.join('.', tempB.name)
    cat_file(fileC_sha, fileObject)
    tempC.write(fileObject.content)
    tempC.flush()
    tempC_file_path = os.path.join('.', tempC.name)

    tempB_rel_file_path = utils.get_rel_path(tempB_file_path)
    tempC_rel_file_path = utils.get_rel_path(tempC_file_path)
    subprocess.run(f"merge {fileA} {tempB_rel_file_path} {tempC_rel_file_path}", shell=True)

    tempB.close()
    tempC.close()

def write_sha_into_working_tree(file_path: str, file_sha: str): 
    fileObject = models.ByteFile(None, None, None)
    cat_file(file_sha, fileObject)

    dir_path = os.path.dirname(file_path)
    if dir_path:  # Ensure the directory structure exists only if dir_path is not empty
        os.makedirs(dir_path, exist_ok=True)

    with open(file_path, "w") as file: 
        file.write(fileObject.content)

def diff(commitA: str, commitB: str): 
    diff_string = ""
    treeA_sha = utils.extract_tree_from_commit(commitA)
    treeB_sha = utils.extract_tree_from_commit(commitB)

    treeA_dict = {} 
    treeB_dict = {}
    load_tree_into_hash(treeA_sha, "", treeA_dict)
    load_tree_into_hash(treeB_sha, "", treeB_dict)
    common_files = set(treeA_dict.keys()) & set(treeB_dict.keys())

    #compare common files 
    for file in common_files: 
        shaA = treeA_dict[file]
        shaB = treeB_dict[file]
        fileObjectA = models.ByteFile(None, None, None)
        fileObjectB = models.ByteFile(None, None, None)
        cat_file(shaA, fileObjectA)
        cat_file(shaB, fileObjectB)

        with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as tempA, tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as tempB:       
            tempA.write(fileObjectA.content)
            tempB.write(fileObjectB.content)
            tempA.flush()
            tempB.flush()
            tempA_file_path = os.path.join('.', tempA.name)
            tempB_file_path = os.path.join('.', tempB.name)
            rel_file_path = utils.get_rel_path(file)
            output = utils.run_diff(tempB_file_path, tempA_file_path, rel_file_path, rel_file_path)
            #print(output)
            diff_string += output  
            diff_string += '\n'
            

        treeA_dict.pop(file)
        treeB_dict.pop(file)
        print()
        

    #diff unshared files
    #files in A but not B
    for file in treeA_dict.keys(): 
        shaA = treeA_dict[file]
        fileObjectA = models.ByteFile(None, None, None)
        cat_file(shaA, fileObjectA)

        with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as tempA: 
            tempA.write(fileObjectA.content)
            tempA.flush()
            tempA_file_path = os.path.join('.', tempA.name)
            rel_file_path = utils.get_rel_path(file)
            output = utils.run_diff(DEV_NULL_FILE, tempA_file_path, DEV_NULL_FILE.lstrip("/"), rel_file_path)
            #print(output)
            diff_string += output 
            diff_string += '\n'

    #files in B but not in A
    for file in treeB_dict.keys(): 
        shaB = treeB_dict[file]
        fileObjectB = models.ByteFile(None, None, None)
        cat_file(shaB, fileObjectB)
        with tempfile.NamedTemporaryFile(mode="w+t", dir=".", delete=True) as tempB: 
            tempB.write(fileObjectB.content)
            tempB.flush()
            tempB_file_path = os.path.join('.', tempB.name)
            rel_file_path = utils.get_rel_path(file)
            output = utils.run_diff(tempB_file_path, DEV_NULL_FILE, rel_file_path, DEV_NULL_FILE.lstrip("/"))
            #print(output)
            diff_string += output 
            diff_string += '\n'

    return diff_string


def load_tree_into_hash(tree_sha: str, dir_path: str, hash: dict): 
    fileObject = models.ByteFile(None, None, None)
    cat_file(tree_sha, fileObject)

    tree = fileObject.content.split(" ")
    n = len(tree)
    for i in range(0, n, 3):
        file_type = tree[i]
        hash_code = tree[i + 1]
        file_name = tree[i + 2]

        if file_type == "blob": 
            hash[dir_path + file_name] = hash_code

        if file_type == "tree": 
            load_tree_into_hash(hash_code, file_name + "/", hash)


def apply_patch(diff_text: str):
    # Create a temporary file to hold the patch
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmpfile:
        tmpfile.write(diff_text)
        tmpfile.flush()
        tmpfile_name = tmpfile.name

    try:
        # Run the 'patch' command to apply the patch
        subprocess.run(f"patch --batch -p1 < {tmpfile_name} > /dev/null 2>&1", check=True, shell=True)
        print(f"Patch applied successfully.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while applying the patch: {e}")
    finally:
        # Delete the temporary file
        os.remove(tmpfile_name)


#-----------------------------------

    


