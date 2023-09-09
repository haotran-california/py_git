import os 
import typer 
import py_git.git as git
import py_git.models as models
import py_git.utils as utils
from typing_extensions import Annotated
from typing import List
from py_git import SUCCESS, ERRORS, INIT_ERROR, F_EXIST_ERROR, F_LARGE_ERROR, HASH_EXISTS_ERROR

app = typer.Typer()
#perhaps add a constant which is true or false if git has been init or not #perhaps add a constant which is true or false if git has been init or not #perhaps add a constant which is true or false if git has been init or not 

@app.command()
def init() -> None: 
    """Initializes the project with .git directory"""
    init_result = git.init() 
    if init_result == INIT_ERROR: 
        #typer.echo(f"Error: {ERRORS[init_result]}")
        #raise typer.Exit(1) 
        handleError(INIT_ERROR)

    if init_result == SUCCESS: 
        typer.echo("Success! Git has been initialized")

@app.command()
def cat_file(
    sha_str: Annotated[str, typer.Argument()],
    #type: Annotated[str, typer.Option()] = "",
) -> None: 
    """Prints the contents of the specified internal object"""
    fileObject = models.ByteFile(None, None, None)
    cat_result = git.cat_file(sha_str, fileObject)
    input_object = (fileObject.type, fileObject.size, fileObject.content)
    display_content(input_object)


def display_content(input_object):
    if input_object[0] == "blob": 
        print(input_object[2])
    elif input_object[0] == "tree": 
        tree = input_object[2].split(" ")
        n = len(tree)
        for i in range(0, n, 3):
            file_type = tree[i]
            hash_code = tree[i + 1]
            file_name = tree[i + 2]
            print(f"{file_type} {hash_code}\t{file_name}")
    elif input_object[0] == "commit": 
        delimiter = '\x1F'
        commit = input_object[2].split(delimiter)
        for line in commit: 
            print(line) 
    else: 
        print("not a valid object type")

@app.command()
def hash_object(
    file: Annotated[str, typer.Argument()]
) -> None: 
    """Hashes a file"""
    hash_result, sha1 = git.hash_file(file)

    if hash_result == F_EXIST_ERROR: 
        handleError(F_EXIST_ERROR)

    if hash_result == F_LARGE_ERROR: 
        handleError(F_LARGE_ERROR)
        
    if hash_result == HASH_EXISTS_ERROR: 
        handleError(HASH_EXISTS_ERROR)

    if hash_result == SUCCESS: 
        typer.echo(sha1)

@app.command()
def update_cache(
    file_paths: Annotated[List[str], typer.Argument()] = None    
) -> None: 
    """Adds object to the stagging area as well as hashes the object"""
    if file_paths[0] == ".": 
        abs_file_paths = utils.get_all_files()
        cwd = os.getcwd()
        relative_paths = [os.path.relpath(file_path, cwd) for file_path in abs_file_paths]
        file_paths = relative_paths

    for file in file_paths: 
        git.update_cache(file.lstrip("./"))

@app.command()
def write_tree() -> None: 
    """Takes files from stagging area and combines them into a tree object"""
    sha1 = git.write_tree() 
    print(sha1)

@app.command()
def commit_tree(
    tree_sha: Annotated[str, typer.Argument()], 
    message: Annotated[str, typer.Option(help="Commit message")] = "",
) -> None: 
    """Takes current working tree and commits changes"""
    while not message: 
        message = input("Enter commit message: ")
    sha1 = git.commit_tree(tree_sha, message)
    print(sha1)

@app.command()
def rm(
    file: Annotated[str, typer.Argument()],
): 
    """Removes file from stagging area"""
    all = False
    if file == ".": 
        all = True
    rm_result = git.rm(file, all)

    if rm_result: 
        print("removed")
    else: 
        print("nothing to remove")

@app.command()
def log(): 
    """Shows history of all commits on current branch"""
    git.log()

@app.command()
def branch(
    branch_name: Annotated[str, typer.Argument()],
): 
    """Set current HEAD to new branch"""
    #note: make branch name less than 40 characters to prevent bug 
    branch_result = git.branch(branch_name.lstrip("/"))

@app.command()
def checkout(
    #commit_sha: Annotated[str, typer.Argument()]
    branch: Annotated[str, typer.Option()] = "", 
    commit: Annotated[str, typer.Option()] = "", 
): 
    """Checkout a branch or commit"""
    git.checkout(branch, commit)

@app.command()
def status(): 
    """Shows files in stagging area and changes"""
    git.status()

@app.command()
def merge(
    branch: Annotated[str, typer.Argument()], 
): 
    git.merge(branch)

@app.command()
def diff(
    commit_sha: Annotated[List[str], typer.Argument()]
): 
    diff_string = git.diff(commit_sha[0], commit_sha[1])
    print(diff_string)

@app.command()
def temp(): 
    git.temp()

def handleError(errorCode) -> None: 
    print(f"Error {ERRORS[errorCode]}")
    raise typer.Exit(1)



