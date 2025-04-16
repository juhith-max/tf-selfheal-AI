import subprocess
import time
import re
import os
import sys
import io
import ollama
import shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TERRAFORM_DIR = "./terraform"
LLM_MODEL = "codellama:7b"  # Or: "phi3", "mistral", "llama3"
MAX_CODE_CHARS = 6000  # Limit what we send to LLM

def clean_error_output(err):
    return err.encode('ascii', errors='ignore').decode()

def run_terraform():
    result = subprocess.run(["terraform.exe", "apply", "-auto-approve"], capture_output=True, text=True, cwd=TERRAFORM_DIR)
    return result.returncode, result.stderr

def extract_code_block(ai_response):
    # Extract the first code block (```...```)
    matches = re.findall(r"```(?:hcl|terraform)?\s*([\s\S]+?)```", ai_response)
    if matches:
        return matches[0].strip()
    
    # Fallback: extract from # main.tf and downward
    fallback = re.search(r"(#\s*main\.tf[\s\S]+)", ai_response)
    if fallback:
        return fallback.group(1).strip()

    # If nothing found, assume entire response is raw code
    return ai_response.strip()

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

# def run_llm_fix(error_output):
    # code_blocks = collect_terraform_code()
    # combined_code = "\n\n".join([f"// File: {fname}\n{code}" for fname, code in code_blocks])

    # prompt = f"""
    # You are a Terraform expert. The following Terraform code caused this error during apply:

    # ---BEGIN ERROR---
    # {error_output}
    # ---END ERROR---

    # The error is likely due to an invalid argument. Fix only the invalid part of the code related to the error. Do not change anything else in the code. Return only the corrected Terraform code, focusing only on the parts related to the error (e.g., removing or correcting the invalid argument).
    # Return only the fixed Terraform code. Do not include explanations or markdown code fences (like or hcl). Just the raw code.
    # Return ONLY the corrected Terraform code, without explanation or markdown formatting.
    # ---BEGIN CODE---
    # {combined_code}
    # ---END CODE---
    # """

    # response = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    # raw = response['message']['content']
    
    # print(f"Raw AI Response: {raw}")  # Debugging: Print the raw response

    # # Extract the code from AI response
    # fixed_code = extract_code_block(raw)
    
    # # Check if the fixed code is valid Terraform code
    # if not is_valid_terraform_code(fixed_code):
    #     print("AI did not return valid Terraform code. Exiting.")
    #     return None

    # print(f"\nAI Response:\n{fixed_code}\n")
    # return fixed_code
def extract_terraform_code(response):
    # Try to extract from triple backtick blocks first
    code_blocks = re.findall(r"```(?:hcl|terraform)?\s*([\s\S]+?)```", response)
    if code_blocks:
        return code_blocks[0].strip()

    # Fallback: look for anything starting with a resource block
    fallback = re.search(r'(resource\s+"[^"]+"\s+"[^"]+"\s+\{[\s\S]+?\})', response)
    if fallback:
        return fallback.group(1).strip()

    return None  # No valid code found    
def run_llm_fix(error_message):
    print("Sending prompt to AI...")

    prompt = f"""
The following Terraform validation error occurred:

{error_message}

Fix the code accordingly. Return ONLY the corrected Terraform code without explanation. Do NOT use triple backticks or markdown formatting.
"""

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    print("Raw AI Response:", response['message']['content'])

    fixed_code = extract_terraform_code(response['message']['content'])

    if not fixed_code:
        print("AI did not return valid Terraform code. Exiting.")
        return None

    return fixed_code
def overwrite_code(fixed_code, output_path="./terraform/main_fixed.tf"):
    # Backup current fixed code if it already exists
    if os.path.exists(output_path):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = f"{output_path.replace('.tf', '')}_backup_{timestamp}.tf"
        shutil.move(output_path, backup_path)
        print(f"Existing fixed file backed up at {backup_path}")

    with open(output_path, "w") as f:
        f.write(fixed_code)
        print(f"Fixed code written to {output_path}")

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
