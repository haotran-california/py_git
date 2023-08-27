import sys
import os
import zlib
import hashlib
import re
GIT_INIT_DIRS = [".git", ".git/objects", ".git/refs"]
def git_init():
    # Make initial .git directories
    for _dir in GIT_INIT_DIRS:
        os.mkdir(_dir)
    # Make initial .git/HEAD file
    with open(".git/HEAD", "w") as file:
        file.write("ref: refs/heads/master\n")
    print("Initialised git directory")

def git_cat_file(blob_sha: str) -> str:
    path = f".git/objects/{blob_sha[:2]}/{blob_sha[2:]}"
    if os.path.exists(path):
        with open(path, "rb") as blob:
            return zlib.decompress(blob.read()).split(b"\x00")[1].decode()
    raise RuntimeError(f"Blob at {path} doesn't exist!")

def hash_object(contents, filetype):
    # Hashing file contents
    contents = b"".join(
        [
            filetype.encode(),
            b" ",
            bytes(f"{len(contents)}", encoding="utf-8"),
            b"\x00",
            contents,
        ]
    )
    sha = hashlib.sha1(contents).hexdigest().strip()
    # Create directory and object
    dir_sha, blob_sha = sha[:2], sha[2:]
    # Check whether directory exists or not first?
    if not (
        os.path.exists(f".git/objects/{dir_sha}")
        and os.path.isdir(f".git/objects/{dir_sha}")
    ):
        os.mkdir(f".git/objects/{dir_sha}")
    filename = os.path.join(f".git/objects/{dir_sha}", blob_sha)
    with open(filename, "wb") as f:
        f.write(zlib.compress(contents))
    return hashlib.sha1(contents)

def git_ls_tree(tree_sha: str) -> str:
    path = f".git/objects/{tree_sha[:2]}/{tree_sha[2:]}"
    if os.path.exists(path):
        with open(path, "rb") as file:
            uncompressed_file = zlib.decompress(file.read())
            tree_entries = uncompressed_file.split(b"\x00", 1)[1]
            objects = re.split(rb"\d{5,6} ", tree_entries)[1:]
            objects = list(map(lambda x: x.split(b"\x00")[0].decode(), objects))
        return objects
    raise RuntimeError(f"Tree with sha {tree_sha} doesn't exist!")

def write_tree(directory=os.path.curdir):
    entries = os.scandir(directory)
    contents = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            hash = write_tree(entry.path)
            contents.append(f"40000 {entry.name}\x00".encode("utf-8") + hash.digest())
        elif entry.is_file():
            with open(entry.path, "rb") as f:
                data = f.read()
            hash = hash_object(data, "blob")
            contents.append(f"100644 {entry.name}\x00".encode("utf-8") + hash.digest())
    tree_object_data = b"".join(sorted(contents, key=trim_bytes))
    return hash_object(tree_object_data, "tree")

def trim_bytes(bytestring):
    _, result = bytestring.split(None, 1)
    return result

def main():
    command = sys.argv[1]
    # print(f"command: {sys.argv}")
    if command == "init":
        git_init()
    elif command == "cat-file":
        if len(sys.argv) == 4 and sys.argv[2] == "-p":
            print(git_cat_file(sys.argv[3]), end="")
        else:
            raise RuntimeError(f"Correct usage: cat-file -p <blob_sha>")
    elif command == "hash-object":
        if sys.argv[2] == "-w":
            filename = sys.argv[3]
            with open(filename, "rb") as f:
                contents = f.read()
            sha = hash_object(contents, "blob")
            print(sha.hexdigest())
        else:
            raise RuntimeError(f"Correct usage: hash-object -w <file>")
    elif command == "ls-tree":
        if len(sys.argv) == 4 and sys.argv[2] == "--name-only":
            for _object in git_ls_tree(sys.argv[3]):
                print(_object)
        else:
            raise RuntimeError(f"Correct usage: ls-tree --name-only <tree_sha>")
    elif command == "write-tree":
        # print(sys.argv)
        print(write_tree().hexdigest())
        pass
    else:
        raise RuntimeError(f"Unknown command #{command}")
if __name__ == "__main__":
    main()