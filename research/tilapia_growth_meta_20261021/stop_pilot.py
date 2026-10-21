"""Stop only the exact new private pilot; never kill the main application."""
import subprocess

CODE = """import pathlib,os,signal
script='/app/backend/research_runs/tilapia_growth_adaptive_20261021/pilot_service.py'
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(b'\\0')
 except (FileNotFoundError,PermissionError):continue
 if len(args)>1 and args[1].decode(errors='replace')==script:os.kill(int(p.name),signal.SIGTERM)
"""
subprocess.run(['docker','exec','aquaculture_backend','python','-c',CODE],check=True)
