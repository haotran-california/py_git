import hashlib
from enum import Enum

# class ByteObject(Enum): 
#     _type = None 
#     _size = None 
#     _content = None 

class ByteFile(): 
    def __init__(self, _type: str, size: int, content: str) -> None:
        self.type = _type
        self.size = size
        self.content = content



class Blob:
    """Represents a blob object, which is a SHA-1 hash of file contents."""
    def __init__(self, content: bytes):
        self.content = content
        self.object_id = self._compute_object_id()

    def _compute_object_id(self):
        sha1 = hashlib.sha1()
        sha1.update(self.content)
        return sha1.hexdigest()

class Tree:
    """Represents a tree object, which is a collection of blobs and other trees."""
    def __init__(self):
        self.object_id = ""
        self.parent_id = ""
        self.entries = {}

    def add_entry(self, key, value):
        self.entries[key] = value

    def generate_id(self): 
        self.object_id = ""

class Commit:
    """Represents a commit object, which contains information about a specific version of the repository."""
    def __init__(self, tree_id: str, message: str, parent_commit_id: str = None):
        self.tree_id = tree_id
        self.message = message
        self.parent_commit_id = parent_commit_id
        self.object_id = self._compute_object_id()

    def _compute_object_id(self):
        sha1 = hashlib.sha1()
        sha1.update(self.tree_id.encode())
        sha1.update(self.message.encode())
        if self.parent_commit_id:
            sha1.update(self.parent_commit_id.encode())
        return sha1.hexdigest()


# import os
# import stat
# import time

# class FileMetadata:
#     def __init__(self, file_path):
#         self.file_path = file_path
#         self.size = self.get_size()
#         self.creation_time = self.get_creation_time()
#         self.modification_time = self.get_modification_time()
#         self.file_mode = self.get_file_mode()

#     def get_size(self):
#         return os.path.getsize(self.file_path)

#     def get_creation_time(self):
#         return time.ctime(os.path.getctime(self.file_path))

#     def get_modification_time(self):
#         return time.ctime(os.path.getmtime(self.file_path))

#     def get_file_mode(self):
#         return stat.filemode(os.stat(self.file_path).st_mode)

#     def print_metadata(self):
#         print(f"File Path: {self.file_path}")
#         print(f"Size: {self.size} bytes")
#         print(f"Creation Time: {self.creation_time}")
#         print(f"Modification Time: {self.modification_time}")
#         print(f"File Mode: {self.file_mode}")