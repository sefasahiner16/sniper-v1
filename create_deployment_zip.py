import os
import zipfile

def zip_project(output_filename='sniper_deploy.zip'):
    # Files/Dirs to EXCLUDE
    excludes = {
        'venv', '.venv', '__pycache__', '.git', '.idea', '.vscode', 
        'backtest_results', 'backtest_results_BTC', 'backtest_results_ETH',
        'sniper_deploy.zip', 'create_deployment_zip.py',
        'debug_bybit.py', 'debug_bybit_v2.py', 'debug_bybit_v3.py', 'debug_output.txt',
        'logs', '.env' # Exclude local logs and config to protect server state
    }
    
    # Get the current directory (project root)
    root_dir = os.getcwd()
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(root_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in excludes]
            
            for file in files:
                if file in excludes or file.endswith('.zip') or file.endswith('.pyc'):
                    continue
                
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, root_dir)
                
                # Double check against full path excludes just in case
                if any(x in arcname.split(os.sep) for x in excludes):
                    continue
                    
                print(f"Adding: {arcname}")
                zipf.write(file_path, arcname)
                
    print(f"\nSuccessfully created {output_filename}")

if __name__ == "__main__":
    zip_project()
