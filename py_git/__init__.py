__app_name__ = "py-git" 
__version__ = "0.1.0"

(SUCCESS, INIT_ERROR, F_EXIST_ERROR, F_LARGE_ERROR, HASH_EXISTS_ERROR) = range(5)
ERRORS = {
    INIT_ERROR: "git has already been initialized",
    F_EXIST_ERROR: "file does not exists",
    F_LARGE_ERROR: "file is too large", 
    HASH_EXISTS_ERROR: "file has already been hashed"
}

GIT_DIR = "./git"
DEV_NULL_FILE = "/dev/null"


