#!/usr/bin/python3
"""Fixed entry path for isolated Python invocation."""
import sys
sys.path.insert(0,'/opt/symphony-next-ci')
from snci.controller import main
main()
