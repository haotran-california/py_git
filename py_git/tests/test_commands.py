import pytest
import sys
from typer.testing import CliRunner

from py_git import git
from py_git import SUCCESS, INIT_ERROR
from pathlib import Path

runner = CliRunner()

#test init 
#by passing in the tmp_path fixture does it mean that git.init() will be done in tmp? 
#no
def test_first_call_git_init(tmp_path, capfd): 
    exit_code = git.init()
    console = capfd.readouterr()

    #check .git is setup 
    git_path =  Path(".git")
    obj_path = git_path / "objects" 
    ref_path = git_path / "refs"
    head_path = git_path / "HEAD"
    assert git_path.is_dir()
    assert obj_path.is_dir()
    assert ref_path.is_dir()
    assert head_path.is_file()

    #assert "Success! Git has been initialized" in console.out 
    assert exit_code == SUCCESS


def test_second_call_git_init(tmp_path): 
    exit_code = git.init()
    assert exit_code == INIT_ERROR

#test hash-object 

# @pytest.fixture
# def create_small_file(tmp_path): 
#     return 0

# def test_hash_object(tmp_path): 
#     return 0 






























