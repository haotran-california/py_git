import os
import pickle
from typing import List
import operator

git_dir = ".git"
SIGNATURE = "HAO'S GIT CLONE"

class Header(): 
    def __init__(self) -> None:
        self.numEntries = 0 
        self.signature = ""

    def __str__(self): 
        return f'Header(numEntries={self.numEntries})'

class CacheEntry():
    def __init__(self, _type, mode, sha1, file_path) -> None:
        self.sha1 = sha1
        self.type = _type
        self.mode = mode
        self.file_path = file_path

    def __str__(self): 
        return f'CacheEntry(type={self.type} file_path={self.file_path} sha1={self.sha1})'

class Cache: 
    def __init__(self) -> None:
        self.header: Header = Header()
        self.contents: List[CacheEntry] = []

class CacheHandeler: 
    def __init__(self) -> None:
        self.index_file = os.path.join(git_dir, "index")
        

    def load_cache(self) -> Cache: 
        if not os.path.exists(self.index_file): 
            self.initialize_cache()

        with open(self.index_file, "rb") as file: 
            serialized_cache = file.read()

        cache = pickle.loads(serialized_cache)
        return cache
        
    def initialize_cache(self) -> None: 
        cache = Cache()
        serialized_cache = pickle.dumps(cache)
        with open(self.index_file, "wb") as file: 
            file.write(serialized_cache)

    def insert_cache(self, _type, mode, sha1, file_path): 
        cache_entry = CacheEntry(_type, mode, sha1, file_path)
        cache = self.load_cache()

        if cache.header.numEntries == 0: 
            cache.contents.append(cache_entry)
            cache.header.numEntries += 1  
            self.save_cache(cache)
            return

        #check if file is already in index 
        for i, entry in enumerate(cache.contents): 
            if file_path == entry.file_path: 
                cache.contents[i] = cache_entry
                self.save_cache(cache)
                return
                
        #implement binary search here later
        cache.contents.append(cache_entry)
        cache.contents.sort(key=lambda entry: entry.file_path)
        cache.header.numEntries += 1 
        self.save_cache(cache)
        return

    def save_cache(self, cache: Cache) -> None: 
        with open(self.index_file, "wb") as file: 
            serialized_cache = pickle.dumps(cache)
            file.write(serialized_cache)

    def printCache(self) -> None: 
        cache = self.load_cache()
        print(cache.header)
        for entry in cache.contents: 
            print(entry.file_path)

    def remove(self, file_path: str) -> None: 
        cache = self.load_cache()
        for i, entry in enumerate(cache.contents): 
            if entry.file_path == file_path: 
                cache.contents.pop(i)
                cache.header.numEntries -= 1 
                self.save_cache(cache)
                return 1
        return 0
                
    def remove_all(self): 
        cache = self.load_cache()
        n = len(cache.contents)
        if n == 0: 
            return 0 
        cache.contents = []
        cache.header.numEntries = 0 
        self.save_cache(cache)
        return 1 

            





















