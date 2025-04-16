### Terraform AI Self-Healing Script 🤖

This project uses AI (via Ollama + LLM) to automatically identify and fix errors in Terraform code.

## 🚀 Features

- Automatically runs `terraform init` and `terraform validate`
- Sends validation errors to AI for suggested fixes
- Applies fixes and re-runs validation until resolved or max attempts
- Backs up previous fixed files with timestamp

---

## 📦 Requirements

- Python 3.9+
- Terraform CLI
- Ollama (local LLM backend)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🛠️ How to Use

1. Make sure your Terraform code is in the `./terraform` folder
2. Run the script:

```bash
python aifixer.py
```

3. If validation fails, the script:
   - Sends the error to the AI
   - Writes a suggested fix
   - Re-validates and repeats (up to 3 attempts)

---

## ⚙️ Model Configuration

By default, uses `codellama:7b`. Change the model by updating the `LLM_MODEL` variable in `aifixer.py`.

---

## 🧠 Example AI Fix

**Before:**
```hcl
resource "aws_instance" "example" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
  test = "fail"
}
```

**After AI Fix:**
```hcl
resource "aws_instance" "example" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}
```

---

## 🧾 License

MIT - feel free to use and modify!