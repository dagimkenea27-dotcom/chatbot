import sys
import os
import traceback

# Set working directory & Python path to application directory
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)
os.chdir(app_dir)

# Dynamic Virtual Environment Activation
activated = False

# 1. Check local virtual environments inside the project (e.g. 'venv' or 'gojoshop-chatbot/venv')
venv_paths = [
    os.path.join(app_dir, 'venv'),
    os.path.join(app_dir, 'gojoshop-chatbot', 'venv')
]

for venv in venv_paths:
    for act_dir in [os.path.join(venv, 'bin'), os.path.join(venv, 'Scripts')]:
        act_file = os.path.join(act_dir, 'activate_this.py')
        if os.path.exists(act_file):
            try:
                with open(act_file) as f:
                    code = compile(f.read(), act_file, 'exec')
                    exec(code, dict(__file__=act_file))
                activated = True
                break
            except Exception:
                pass
    if activated:
        break

# 2. Check standard cPanel virtual environment paths (~/virtualenv/<app_name>/<python_version>)
if not activated:
    try:
        home_dir = os.path.expanduser('~')
        cpanel_virtualenv_base = os.path.join(home_dir, 'virtualenv')
        if os.path.exists(cpanel_virtualenv_base):
            app_name = os.path.basename(app_dir)
            possible_venv_names = [app_name, 'Gojo_Chat_bot', 'GojoShop_Chat_bot']
            for possible_name in possible_venv_names:
                possible_path = os.path.join(cpanel_virtualenv_base, possible_name)
                if os.path.exists(possible_path):
                    # Look for bin/activate_this.py in any subdirectory (representing Python versions like 3.14, 3.10)
                    for root, dirs, files in os.walk(possible_path):
                        if 'activate_this.py' in files:
                            act_file = os.path.join(root, 'activate_this.py')
                            with open(act_file) as f:
                                code = compile(f.read(), act_file, 'exec')
                                exec(code, dict(__file__=act_file))
                            activated = True
                            break
                if activated:
                    break
    except Exception:
        pass

# 3. Fallback: Manually insert site-packages directories into sys.path
if not activated:
    for venv in venv_paths:
        # Check Linux python version subdirectories
        lib_path = os.path.join(venv, 'lib')
        if os.path.exists(lib_path):
            try:
                for pydir in os.listdir(lib_path):
                    sp = os.path.join(lib_path, pydir, 'site-packages')
                    if os.path.exists(sp):
                        sys.path.insert(0, sp)
                        activated = True
            except Exception:
                pass
        # Check Windows path
        sp_win = os.path.join(venv, 'Lib', 'site-packages')
        if os.path.exists(sp_win):
            sys.path.insert(0, sp_win)
            activated = True

# Try loading the Flask application and catch any startup exceptions
try:
    from app import app as application
except Exception as e:
    # Write the startup traceback to a file in the app directory for remote debugging
    error_log_path = os.path.join(app_dir, 'passenger_error.log')
    try:
        with open(error_log_path, 'w') as f:
            f.write("Failed to start WSGI application.\n")
            f.write(f"Activated virtualenv: {activated}\n")
            f.write(f"Python interpreter: {sys.executable}\n")
            f.write(f"sys.path: {sys.path}\n\n")
            f.write("Traceback:\n")
            traceback.print_exc(file=f)
    except Exception:
        pass
    raise e
