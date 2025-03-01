#!/usr/bin/env python3
"""
Module Name: VHP_ffmpeg.py

Description:
    This python script is to be used on the RIT Research Computing Cluster to analyze CVE-2015-8218
    via this commit hash:d4a731b84a08f0f3839eaaaf82e97d8d9c67da46 . This hash it the commit of the patch for 
    this vulnerability. This file will mainly depend on pydriller to locate the original commit that 
    caused this vulnerability.This vulnerability had to deal with an overlooked array of some sort.

Author: Trust-Worthy, TylerJaafari-RIT

Date: 2025-1-17 -> 2025-1-21
    
    
Notes: 
    - pydriller must be installed on the system to run this program

"""
import subprocess
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path
import os 
import pprint
import json

from pydriller import Git,ModifiedFile, Commit

"""

global vars: 
    PATCH_COMMIT_HASH (str): Commit hash of the patch to CVE-2015-8218 --> d4a731b84a08f0f3839eaaaf82e97d8d9c67da46
    VULN_COMMIT_HASH (str): Commit hash of the original commit that introduced CVE-2015-8218
    PATH_FFMPEG_REPO (str): Path to the ffmpeg repo that will be used as a test with this specific vulnerability
    PATCH_MODIFIED_FILES set[str]: Set of files modified by the patch commit.
    PATCH_FIXED_CHANGES dict[str,dict[str,str]]: The key of the outer dictionary is the name of the modified file. The value is another dictionary. The second
                                                 dictionary has two keys, either "added" or "deleted". The added section has the code that was added by the
                                                 commit and vice-versa.
    VULN_CHANGES list[str]: Changes that the initial vulnerable commit made. This is only the code for verification and debugging purposes. Thus, files in which
                            the changes occurred aren't included.
    PATH_OUTPUT_DIR (str): Path to the output directory where the json file will be written to.


"""
load_dotenv()
PATH_FFMPEG_REPO:str = os.getenv("FFMPEG_PATH")
PATH_OUTPUT_DIR:str = "" ### Fill in later

PATCH_COMMIT_HASH:str = "d4a731b84a08f0f3839eaaaf82e97d8d9c67da46" 
PATCH_MODIFIED_FILES:set[str] = set()
PATCH_FIXED_CHANGES:dict[str,dict[str,str]] = {}

VULN_COMMIT_HASH:str = ""
VULN_CHANGES:list[str] = []


def find_modified_files(commit_hash:str = PATCH_COMMIT_HASH, repo_path:str = PATH_FFMPEG_REPO) -> set[ModifiedFile]:
    """
    Given a specific commit hash and repo via a path, returns a set of ModifiedFile objects. All items in the set are modified
    by the original commit hash.

    Args:
        commit_hash (str, optional): The hash to be analyzed. Defaults to PATCH_COMMIT_HASH.
        repo_path (str, optional): Path to repo used to analyze a commit hash. Defaults to PATH_FFMPEG_REPO.

    Returns:
        set[ModifiedFile]: Set of ModifiedFile objects that were all modified by the commit.
    """
    
    # Create empty set for files that were modified by the fixed commit
    modified_file_paths_from_fix:set[ModifiedFile] = set()

    # converting path to a Git object --> ffmpeg git repo
    ffmpeg_git_repo= Git(repo_path)

    # Getting the commit object from the fixed commit hash the fixed the vulnerability
    fixed_commit:Commit = ffmpeg_git_repo.get_commit(commit_hash)

    

    # Add modified files to the set for later reference
    for modified_file in fixed_commit.modified_files:

        # Always add the old path because that is the one what won't change
        modified_file_paths_from_fix.add(modified_file)
        PATCH_MODIFIED_FILES.add(modified_file.old_path)

        PATCH_FIXED_CHANGES[modified_file.old_path] = modified_file.diff_parsed # I want to add the changes so I can look at them later
        

    return modified_file_paths_from_fix
   

def git_blame(file_path:str,line_start:int,line_end:int,repo_path:str=PATH_FFMPEG_REPO) -> str:
    """
    Executes git blame command on line_start and line_end then returns the result.

    Args:
        file_path (str): Path to the file where the vulnerability was first introduced & later fixed.
        line_start (int): Starting line where the code for the vulnerability was introduced. Used for accurate git blame output.
        line_end (int): Ending line where the code for the vulnerability was introduced. Used for accurate git blame output.
        repo_path (str, optional): _description_. Defaults to PATH_FFMPEG_REPO.

    Raises:
        Exception: if the git blame command can'ts be executed

    Returns:
        str: Returns the result from the git blame command.
    """
    
    full_path = Path(repo_path) / file_path

    result = subprocess.run(
        ['git','-C',repo_path,'blame',full_path, '-L',f'{line_start},{line_end}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.stderr:
        raise Exception(f"Git blame failed: {result.stderr.decode()}")

    return result.stdout.decode()

def extract_most_common_commit_and_author(blame_output: str, git_dir: str = PATH_FFMPEG_REPO, work_tree: str = PATH_FFMPEG_REPO) -> dict[str, str]:
    commit_hashes: list[str] = []
    authors: list[str] = []
    lines: list[str] = blame_output.splitlines()

    for line in lines:
        if not line.strip():
            continue
        parts = line.split(maxsplit=3)
        if len(parts) < 2:
            continue
        commit_hash: str = parts[0]
        author: str = parts[1].strip('()')
        commit_hashes.append(commit_hash)
        authors.append(author)

    commit_counter: Counter[str] = Counter(commit_hashes)
    most_common_partial_commit: str = commit_counter.most_common(1)[0][0] if commit_counter else None

    author_counter: Counter[str] = Counter(authors)
    most_common_author: str = author_counter.most_common(1)[0][0] if author_counter else None

    git_dir = Path(git_dir) / ".git"
    result = subprocess.run(
        ['git', '--git-dir', str(git_dir), '--work-tree', str(work_tree), 'rev-parse', most_common_partial_commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if result.returncode == 0:
        full_commit_hash: str = result.stdout.strip()
        return {
            "partial_common_partial_commit_hash": most_common_partial_commit,
            "full_commit_hash": full_commit_hash,
            "most_common_author": most_common_author,
        }
    else:
        raise Exception(f"Failed to resolve full commit hash: {result.stderr.strip()}")

    



def git_show_vuln_changes(vuln_commit_start:int,
                          vuln_commit_end:int,
                          commit_hash:str=VULN_COMMIT_HASH,
                          repo_path:str=PATH_FFMPEG_REPO
    ) -> list[str]:
    """
    Uses 'git show' command to extract code snippets that were added when the vulnerability was first introduced.


    Args:
        vuln_commit_start (int): Line number where the vulnerable code starts.
        vuln_commit_end (int): Line number where the vulnerable code ends.
        commit_hash (str, optional): Commit hash to be analyzed. Defaults to VULN_COMMIT_HASH. This should be the full commit to the original vulnerability commit.
        repo_path (str, optional): Path to repo to be analyzed. Defaults to PATH_FFMPEG_REPO.

    Raises:
        Exception: if 'git show' command fails.

    Returns:
        list[str]: Changes that the initial vulnerable commit made. This is only the code for verification and debugging purposes. Thus, files in which
                            the changes occurred aren't included.
    """


    result = subprocess.run(
        ['git','show',commit_hash], ## ,':',repo_path
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.stderr:
        raise Exception(f"Git show failed: {result.stderr.decode()}")
    
    output:str = result.stdout.decode()
    lines:list[str] = output.splitlines()

    # print("Start:", vuln_commit_start)
    # print("Start:", vuln_commit_end)

    # desired_lines:list[str] = lines[vuln_commit_start - 2:vuln_commit_end+1]
    
    return lines #desired_lines


def get_lines_changed_in_fix(modified_file:ModifiedFile)-> tuple[int,int]:
    """
    Retrieves the lines that were alterd by the patch commit.

    Args:
        modified_file (ModifiedFile): File object supplied by pydriller package that is used to locate the lines changed.

    Returns:
        tuple[int,int]: Returns the earliest added line number and the latest added line number by the patch commit.
    """

    added_lines:list[tuple[int,str]] = modified_file.diff_parsed['added']
    # deleted_lines:list[tuple[int,str]] = modified_file.diff_parsed['deleted']

    
    # Get the earlies added line number
    earliest_added_line:int = added_lines[0][0]

    # Get the earliest deleted line number
    # I know that there weren't any deleted lines. 
    ### TO-DO Add error handling in the case that no lines were added or deleted
    # earliest_deleted_line: int = deleted_lines[0][0]

    # Get the last added line number
    if added_lines:
        last_added_line:str = added_lines[-1][0] # end_line of last added tuple
    else:
        last_added_line = None

    # Get the last deleted line number
    ### TO-DO --> add error handling here
    # if deleted_lines:
    #     last_deleted_line:str = deleted_lines[-1][1] # end_line of last deleted tuple
    # else:
    #     last_deleted_line = None

   
    return (int(earliest_added_line),int(last_added_line))



def save_solution(commit_hash:str =VULN_COMMIT_HASH) -> None:
    """
    Writed the full original commit hash to a directory location.

    Args:
        commit_hash (str, optional): Commit hash that needs to be saved and written to a directory location. Defaults to VULN_COMMIT_HASH.

    """
    return None

    
         



if __name__ == "__main__":
    # Find modified files in the fixed commit
    modified_files_by_fixed_commit:set[ModifiedFile] = find_modified_files(commit_hash=PATCH_COMMIT_HASH)

    # Extract the lines that were changed in each modified file
    ### In the case of CVE-2015-8218 I happen to know that only 1 file was changed. For sake of simplicity, I won't write hypter-robust code
    ### capable of handling multiple modified files (edge cases)
    for file in modified_files_by_fixed_commit:
        # file should be of type ModifiedFile
        lines_changed:tuple[int,int] = get_lines_changed_in_fix(file)


    # Blame the line 1 above start 
    # Blame the line 1 below end
    # This will hopefully get me the original author and commit of the vulnerability
    start:int = lines_changed[0]
    end:int = lines_changed[1]
    mod_file_path = modified_files_by_fixed_commit.pop().old_path
    print(f'The modified file path is: {mod_file_path}')


    blame_ouput: str = git_blame(file_path=mod_file_path, line_start=start,line_end=end,repo_path=PATH_FFMPEG_REPO,)

    # Extract the most common commit hash and author of those commits
    original_commit_dict: dict[str, str]= extract_most_common_commit_and_author(blame_output=blame_ouput)


    VULN_COMMIT_HASH = original_commit_dict['full_commit_hash']
    partial_commit_hash = original_commit_dict['partial_common_partial_commit_hash']
    print(f'The full vulnerable commit hash is: {VULN_COMMIT_HASH}\n'
          f'The partial commit hash is {partial_commit_hash}')

    # This line is a little broken. Technically, I should iterate over every file that was changed. But in this case I 
    # know that only one file was changed by the bug patch. That still doesn't answer the question: Did the vulnerable 
    # commit change other files? But this will do. 

    ### I think the original vuln commit got erased through a merge or something
    # When I tried
    VULN_CHANGES = git_show_vuln_changes(start,end,commit_hash=VULN_COMMIT_HASH,repo_path=PATH_FFMPEG_REPO)

    


    modified_files_by_vuln_commit:set[str] = find_modified_files(commit_hash=VULN_COMMIT_HASH)


    print("Modified files:")
    pprint.pprint(PATCH_MODIFIED_FILES)
    print("__________________________________")
    print("__________________________________")

    print("Partial Commit Info:")
    print("When I run git show with this hash I can't get any info")
    pprint.pprint(partial_commit_hash)
    print("__________________________________")
    print("__________________________________")

    print("Original / Vuln Commit Info:")
    print("When I run git show with this hash I get completely different code than what's in the original patch!")
    pprint.pprint(VULN_COMMIT_HASH)
    print("__________________________________")
    print("__________________________________")

    print("Changes that were made by the patch:")
    pprint.pprint(PATCH_FIXED_CHANGES)
    print("__________________________________")
    print("__________________________________")

    # print("Changes that were made by the vuln commit:")
    # pprint.pprint(VULN_CHANGES)
    # print("__________________________________")
    # print("__________________________________")
    


    for file1,file2 in zip(modified_files_by_fixed_commit,modified_files_by_vuln_commit):
       print(f"file1: {file1}, file2: {file2}")
       
# Writing the dictionary to a JSON file
# json_path:str = "ffmpeg_vuln_changes.json"
# with open(json_path, "w") as json_file:
#     json.dump(PATCH_FIXED_CHANGES, json_file, indent=4) 

    
