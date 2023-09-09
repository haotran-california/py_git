import subprocess
import os
import py_git.git as git
import py_git.models as models
from typing import List
from py_git.cache import Cache, CacheHandeler

def get_all_files():
    files = []
    for root, dirs, filenames in os.walk(os.getcwd()):
        # Remove directories that start with a dot or are named 'py_git'
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'py_git']
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files

def get_rel_path(path: str): 
    cwd = os.getcwd()
    relative_path = os.path.relpath(path, cwd)
    return relative_path

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

def extract_ref_from_head(file_path: str = ".git/HEAD"):
    ref_prefix = "ref: refs/heads/"
    with open(file_path, 'r') as file:
        content = file.read().strip()
        if content.startswith(ref_prefix):
            return content[len(ref_prefix):] 

    return None

def extract_commit_from_head(file_path: str = ".git/HEAD"):
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
    git.cat_file(commit_sha, fileObject)

    raw_commit_data = fileObject.content.split(delimiter)
    treeLine = raw_commit_data[0]
    tree_sha = treeLine.split(" ")[1]
    return tree_sha

def extract_commit_from_commit(commit_sha: str): 
    prevCommit = None
    delimiter = '\x1F'
    fileObject = models.ByteFile(None, None, None)
    git.cat_file(commit_sha, fileObject)
    raw_commit_data = fileObject.content.split(delimiter)
    parent_commit_data = raw_commit_data[1].split(" ")
    if len(parent_commit_data) == 2: 
        prevCommit = parent_commit_data[1].rstrip("\n")

    return prevCommit

def load_tree_into_cache(tree_sha: str, dir_path: str, cache: CacheHandeler): 
    fileObject = models.ByteFile(None, None, None)
    git.cat_file(tree_sha, fileObject) 
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

def load_cache_into_working_tree(current_cache: Cache): 
    cache_array = current_cache.contents

    for entry in cache_array: 
        fileObject = models.ByteFile(None, None, None)   
        git.cat_file(entry.sha1, fileObject)

        directory = os.path.dirname(entry.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(entry.file_path, "w") as file: 
            file.write(fileObject.content)
        
def clear_working_tree(current_cache: Cache): 
    cache_array = current_cache.contents

    file_paths = [x.file_path for x in cache_array]
    delete_files_and_directories(file_paths)

def delete_files_and_directories(file_paths: List[str]):
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

def run_diff_with_diffstat(file1: str, file2: str):
    try:
        # Run the 'diff' command and pipe its output to 'diffstat'
        process_diff = subprocess.Popen(["diff", "-u", file1, file2], stdout=subprocess.PIPE, text=True)
        process_diffstat = subprocess.Popen(["diffstat"], stdin=process_diff.stdout, stdout=subprocess.PIPE, text=True)
        
        # Allow process_diff to receive a SIGPIPE if process_diffstat exits
        process_diff.stdout.close()
        
        # Capture the output of 'diffstat'
        output = process_diffstat.communicate()[0]
        
        return output.rstrip('\n')
    except subprocess.CalledProcessError as e:
        return e.stdout

def run_diff(file1: str, file2: str, filename1: str, filename2: str):
    try:
        # Run the 'diff' command
        process_diff = subprocess.Popen(["diff", "-u", file1, file2], stdout=subprocess.PIPE, text=True)

        # Capture the output of 'diff'
        output, _ = process_diff.communicate()

        # Remove first two lines and add custom lines 
        lines = output.splitlines()
        base = f"diff --git a/{filename1} b/{filename2}\n"
        from_file = f"-- a/{filename1}\n"
        to_file = f"++ b/{filename2}\n"
        git_line = (base + from_file + to_file)  
        modified_output = git_line + '\n'.join(lines[2:])

        return modified_output.rstrip('\n')
    except subprocess.CalledProcessError as e:
        return e.stdout

