# QUICKSTART
This guide explains how to quickly run the **Marketing Performance Chatbot (CLI version)**.
---

## 1 Create a Virtual Environment

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```bash
py -3.11 -m venv .venv
.venv\Scripts\Activate
```

Python 3.11 is recommended.  
Python 3.12 also works.
---

## 2 Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Core dependencies include:

- pandas
- boto3
- pydantic
- python-dotenv
- rich
- bcrypt
- pyyaml
---

## 3 Configure Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
APP_TITLE=Marketing Performance Chatbot
DATASET_PATH=marketing_data.csv

LLM_PROVIDER=bedrock
AWS_REGION=eu-central-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0 | anthropic.claude-3-haiku-20240307-v1:0 

MAX_HISTORY_USER=5
MAX_HISTORY_BOT=5

ENABLE_AUTH=false
```

---

## 4 Configure AWS (Bedrock)

Make sure you have AWS CLI configured:

```bash
aws configure
```

Provide:

- AWS Access Key
- AWS Secret
- Region (e.g., eu-central-1, the one used in this project. Otherwise, change this variable and choose an available model in your aws region)

You must have permission:

```
bedrock:InvokeModel
```
---

## 5 Optional: Enable Authentication

If you want login enabled:

1. Set in `.env`:

```env
ENABLE_AUTH=true
```

2. Create `users.yaml`:

```yaml
users:
  - username: demo
    password_hash: "<bcrypt-hash>"
```

  In this project, the username is demo and the password is demo123. 
  By default, the authentication is NOT enabled.

3. To generate an encrypted password, You can use (example Python snippet):

```python
import bcrypt
print(bcrypt.hashpw(b"your_password", bcrypt.gensalt()).decode())
```

and add to the users.yaml file a new username and the corrisponding hashed password.
---

## 6 Run the CLI Application

From project root:

```bash
python -m app.main
```

You will see:

```
Marketing Performance Chatbot
Type your question (or 'exit' to quit):
```

---

## 7 Example Questions

Try:

```
Total revenue in 2022?
Top 5 campaign names by revenue last quarter
Revenue and cost trend by month in 2023
```

---

## 8 Exit the Application

Type:

```
exit
```

or

```
quit
```

Or just send a message stating you wish to end the conversation.
---
