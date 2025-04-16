import subprocess
import time
import re
import os
import sys
import io
import ollama

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TERRAFORM_DIR = "./terraform"
LLM_MODEL = "codellama:7b"  # Or: "phi3", "mistral", "llama3"
MAX_CODE_CHARS = 6000  # Limit what we send to LLM

def clean_error_output(err):
    return err.encode('ascii', errors='ignore').decode()

def run_terraform():
    result = subprocess.run(["terraform.exe", "apply", "-auto-approve"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
    return result.returncode, result.stderr

def extract_code_block(text):
    match = re.search(r"```(?:hcl)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

def collect_terraform_code():
    code_blocks = []
    for filename in os.listdir(TERRAFORM_DIR):
        full_path = os.path.join(TERRAFORM_DIR, filename)
        if os.path.isfile(full_path) and filename.endswith(".tf"):
            try:
                with open(full_path, "r", encoding="utf-8") as file:
                    content = file.read()
            except UnicodeDecodeError:
                with open(full_path, "r", encoding="latin-1") as file:
                    content = file.read()
            code_blocks.append((filename, content))
    return code_blocks

def is_valid_terraform_code(code):
    temp_file = os.path.join(TERRAFORM_DIR, "temp_validation.tf")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)
    result = subprocess.run(["terraform.exe", "validate"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
    os.remove(temp_file)
    return result.returncode == 0

def run_llm_fix(error_output):
    code_blocks = collect_terraform_code()
    combined_code = "\n\n".join([f"// File: {fname}\n{code}" for fname, code in code_blocks])

    if len(combined_code) > MAX_CODE_CHARS:
        combined_code = combined_code[:MAX_CODE_CHARS] + "\n// Code truncated..."

    prompt = f"""
You are a Terraform expert. This code failed with this error:

{error_output}

Fix only the broken lines. Do not change anything else. Return just the corrected code inside one code block.

{combined_code}
"""

    print("Sending prompt to AI...")
    response = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    raw = response['message']['content']

    print("AI response received.")
    fixed_code = extract_code_block(raw)
    if not is_valid_terraform_code(fixed_code):
        print("AI returned invalid Terraform code.")
        return None

    return fixed_code

def overwrite_code(fixed_code):
    output_path = os.path.join(TERRAFORM_DIR, "main.tf")
    backup_path = os.path.join(TERRAFORM_DIR, "main_backup.tf")

    if os.path.exists(output_path):
        os.rename(output_path, backup_path)
        print(f"Backup saved: {backup_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(fixed_code)
    print("Fixed code written to main.tf")

def validate_terraform():
    for attempt in range(5):
        result = subprocess.run(["terraform.exe", "validate"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
        if result.returncode == 0:
            print("Terraform validation passed.")
            return True
        else:
            print(f"Validation failed (Attempt {attempt + 1})")
            cleaned_error = clean_error_output(result.stderr)
            fixed_code = run_llm_fix(cleaned_error)
            if fixed_code is None:
                return False
            overwrite_code(fixed_code)
            time.sleep(2)
    return False

# Main Execution

print("Running terraform init...")
init = subprocess.run(["terraform.exe", "init"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
if init.returncode != 0:
    print("Terraform init failed.")
    print(init.stderr)
    sys.exit(1)
print("Terraform init complete.")

if not validate_terraform():
    print("Stopping: Unfixable validation error.")
    sys.exit(1)

for attempt in range(5):
    code, stderr = run_terraform()
    if code == 0:
        print("Terraform applied successfully.")
        break
    else:
        print(f"Terraform apply failed (Attempt {attempt + 1})")
        cleaned_error = clean_error_output(stderr)
        fixed_code = run_llm_fix(cleaned_error)
        if fixed_code is None:
            print("Still failing. Stopping.")
            break
        overwrite_code(fixed_code)
        time.sleep(2)
