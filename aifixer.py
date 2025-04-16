import subprocess
import time
import re
import os
import ollama

TERRAFORM_DIR = "./terraform"  # Change this if your folder is different

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
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as file:  # Try UTF-8 encoding
                    content = file.read()
            except UnicodeDecodeError:
                with open(full_path, "r", encoding="latin-1") as file:  # Fallback to latin-1 encoding
                    content = file.read()
            code_blocks.append((filename, content))
    return code_blocks

def is_valid_terraform_code(code):
    """Validates the Terraform code by running 'terraform validate' on it."""
    temp_file = os.path.join(TERRAFORM_DIR, "temp_validation.tf")
    with open(temp_file, "w") as f:
        f.write(code)
    result = subprocess.run(["terraform.exe", "validate"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
    os.remove(temp_file)  # Clean up the temporary file
    return result.returncode == 0

def run_llm_fix(error_output):
    code_blocks = collect_terraform_code()
    combined_code = "\n\n".join([f"// File: {fname}\n{code}" for fname, code in code_blocks])

    prompt = f"""
You're a Terraform expert. The following Terraform code caused this error during apply:

---BEGIN ERROR---
{error_output}
---END ERROR---

Fix only the invalid parts of the following code without changing anything else. Do not explain. Return only the corrected Terraform code in a single code block:ode in a single code block:

---BEGIN CODE---
{combined_code}
---END CODE---
"""
    response = ollama.chat(model="phi3", messages=[{"role": "user", "content": prompt}])
    raw = response['message']['content']
    print(f"Raw AI Response: {raw}")  # Debugging: Print the raw response

    fixed_code = extract_code_block(raw)
    if not is_valid_terraform_code(fixed_code):
        print("❌ AI did not return valid Terraform code. Exiting.")
        return None

    print(f"\n🧠 AI Response:\n{fixed_code}\n")
    return fixed_code

def overwrite_code(fixed_code):
    """Overwrites the Terraform code with the fixed code and creates a backup."""
    backup_path = os.path.join(TERRAFORM_DIR, "main_backup.tf")
    output_path = os.path.join(TERRAFORM_DIR, "main_fixed.tf")
    
    # Backup the original file if it exists
    if os.path.exists(output_path):
        os.rename(output_path, backup_path)
        print(f"🔄 Backup created at {backup_path}")
    
    with open(output_path, "w") as f:
        f.write(fixed_code)
    print(f"✅ Fixed code written to {output_path}")

def validate_terraform():
    """Validates Terraform configuration and attempts to fix errors if validation fails."""
    for attempt in range(5):  # Retry up to 5 times
        result = subprocess.run(["terraform.exe", "validate"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
        if result.returncode == 0:
            print("✅ Terraform validation passed!")
            return True
        else:
            print(f"❌ Validation failed (Attempt {attempt+1}):\n{result.stderr}")
            fixed_code = run_llm_fix(result.stderr)
            if fixed_code is None:
                print("❌ Unable to fix validation errors. Exiting.")
                return False
            overwrite_code(fixed_code)
            time.sleep(3)  # Wait before retrying validation
    print("❌ Validation failed after 5 attempts.")
    return False

# Initialize Terraform
subprocess.run(["terraform.exe", "init"], check=True, cwd=TERRAFORM_DIR)

# Call validate_terraform before proceeding with init/plan/apply
if not validate_terraform():
    print("❌ Exiting due to validation errors.")
    exit(1)

for attempt in range(5):
    code, stderr = run_terraform()
    if code == 0:
        print("✅ Terraform applied successfully!")
        break
    else:
        print(f"❌ Attempt {attempt+1}: Terraform failed. Fixing...\n")
        print("🔍 Error output:\n", stderr)
        fixed_code = run_llm_fix(stderr)
        if fixed_code is None:
            print("❌ Still failing after 5 attempts.")
            break
        overwrite_code(fixed_code)
        time.sleep(3)