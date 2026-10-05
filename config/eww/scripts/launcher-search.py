#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path.home()/'.config/glyphos/scripts'))
from common import BASE, STATE, update, write
query=sys.argv[1] if len(sys.argv)>1 else ''
write(STATE/'search-request.json',{'query':query})
update(launcher_query=query,search_preview='Searching…' if query else '')
# The desktop user service notices this request and runs search in a worker.
