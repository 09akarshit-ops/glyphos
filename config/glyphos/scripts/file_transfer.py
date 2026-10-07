"""Recursive filesystem transfers with collision and self-copy guards."""
from pathlib import Path
import os,shutil

def transfer(paths,directory,move=False):
 target=Path(directory).resolve()
 if not target.is_dir():raise NotADirectoryError(target)
 jobs=[]
 for value in paths:
  source=Path(value);resolved=source.resolve();destination=target/source.name
  if resolved==destination.resolve() or (source.is_dir() and (resolved==target or resolved in target.parents)):raise ValueError('Cannot copy or move a folder into itself.')
  if destination.exists() or destination.is_symlink():raise FileExistsError('Destination already exists: '+source.name)
  if any(dst==destination for _,dst in jobs):raise ValueError('Duplicate destination file name.')
  jobs.append((source,destination))
 for source,destination in jobs:
  if move:shutil.move(str(source),str(destination))
  elif source.is_symlink():destination.symlink_to(os.readlink(source),target_is_directory=source.is_dir())
  elif source.is_dir():shutil.copytree(source,destination,symlinks=True)
  else:shutil.copy2(source,destination)
